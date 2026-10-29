"""Account lifecycle: password-protected writes and one-use recovery links."""
import hashlib
import secrets
import smtplib
import ssl
import shutil
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User, Project, Clip, SourceConnection, Export, Asset, BrandKit, CreditGrant, CreditReservation
from .schemas import CAPTION_PRESETS, AuthIn
from .security import current_user, passwords
from .storage import storage

router=APIRouter()
class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1,max_length=128)
    new_password: str = Field(min_length=10,max_length=128)
class RecoveryIn(BaseModel):
    email: str = Field(min_length=5,max_length=254,pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
class ResetIn(BaseModel):
    token: str = Field(min_length=32,max_length=200)
    new_password: str = Field(min_length=10,max_length=128)
class DeleteIn(BaseModel):
    password: str = Field(min_length=1,max_length=128)
    confirmation: Literal["DELETE"]
class Preferences(BaseModel):
    onboarding_completed: bool = False
    caption_preset: str = "bold"
    resolution: Literal[720,1080] = 1080
    theme: Literal["light","dark","system"] = "light"
    @field_validator("caption_preset")
    @classmethod
    def preset(cls,value):
        if value not in CAPTION_PRESETS: raise ValueError("Unknown caption preset")
        return value

def locked(db,user):
    row=db.scalar(select(User).where(User.id==user.id).with_for_update().execution_options(populate_existing=True))
    if row.deleted: raise HTTPException(401,"Please sign in")
    return row

def limit(request):
    from .main import auth_rate_limit
    auth_rate_limit(request)

def revoke(user):
    user.session_version += 1
    user.reset_digest=None
    user.reset_expires=None

@router.put("/api/me/preferences")
def preferences(data:Preferences, db:Session=Depends(get_db), user:User=Depends(current_user)):
    user=locked(db,user)
    user.preferences={**user.preferences, **data.model_dump(exclude_unset=True)}
    db.commit()
    return user.preferences

@router.post("/api/auth/change-password")
def change_password(data:PasswordChange,request:Request,response:Response,db:Session=Depends(get_db),user:User=Depends(current_user)):
    limit(request)
    user=locked(db,user)
    if not passwords.verify(data.current_password,user.password_hash):
        raise HTTPException(400,"Current password is incorrect")
    if data.current_password==data.new_password:
        raise HTTPException(422,"Choose a different new password")
    user.password_hash=passwords.hash(data.new_password)
    revoke(user)
    db.commit()
    from .main import session_response
    session_response(response,user)
    return {"ok":True}

def send_reset(email,raw):
    cfg=settings()
    msg=EmailMessage()
    msg["Subject"]="Reset your RECLIPD password"
    msg["From"]=cfg.smtp_from
    msg["To"]=email
    # Fragment keeps the secret out of server access logs and referrer headers.
    url=cfg.app_url.rstrip("/")+"/reset-password#"+raw
    msg.set_content(f"Reset your RECLIPD password:\n\n{url}\n\nThis link expires in 30 minutes and can be used once. If you did not request it, ignore this email.")
    with smtplib.SMTP(cfg.smtp_host,cfg.smtp_port,timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(cfg.smtp_username,cfg.smtp_password)
        smtp.send_message(msg)

@router.post("/api/auth/forgot-password")
def forgot(data:RecoveryIn,request:Request,db:Session=Depends(get_db)):
    limit(request)
    cfg=settings()
    if not all([cfg.smtp_host,cfg.smtp_username,cfg.smtp_password,cfg.smtp_from]):
        raise HTTPException(503,"Password recovery email is not configured yet. Contact the studio owner.")
    email=data.email.strip().lower()
    user=db.scalar(select(User).where(User.email==email,User.deleted==False).with_for_update())
    if user:
        # Per-account cooldown prevents mail flooding from multiple IP addresses.
        now=datetime.now(timezone.utc)
        if user.reset_expires:
            expires=user.reset_expires.replace(tzinfo=timezone.utc)
            if expires > now+timedelta(minutes=29):
                return {"message":"If an account matches, a reset link will be emailed shortly."}
        raw=secrets.token_urlsafe(32)
        user.reset_digest=hashlib.sha256(raw.encode()).hexdigest()
        user.reset_expires=now+timedelta(minutes=30)
        try:
            send_reset(user.email,raw)
        except (OSError,smtplib.SMTPException):
            db.rollback()
            # Do not expose mailbox existence or SMTP credentials.
            import logging
            logging.getLogger("reclipd").error("password_reset_email_delivery_failed")
        else:
            db.commit()
    return {"message":"If an account matches, a reset link will be emailed shortly."}

@router.post("/api/auth/reset-password")
def reset(data:ResetIn,request:Request,response:Response,db:Session=Depends(get_db)):
    limit(request)
    digest=hashlib.sha256(data.token.encode()).hexdigest()
    user=db.scalar(select(User).where(User.reset_digest==digest,User.deleted==False).with_for_update().execution_options(populate_existing=True))
    if not user or not user.reset_expires or user.reset_expires.replace(tzinfo=timezone.utc)<=datetime.now(timezone.utc):
        raise HTTPException(400,"This reset link is invalid or expired. Request a new one.")
    user.password_hash=passwords.hash(data.new_password)
    revoke(user)
    db.commit()
    response.delete_cookie("session",path="/")
    return {"ok":True}

@router.delete("/api/me")
def delete_account(data:DeleteIn,request:Request,response:Response,db:Session=Depends(get_db),user:User=Depends(current_user)):
    limit(request)
    user=locked(db,user)
    if not passwords.verify(data.password,user.password_hash):
        raise HTTPException(400,"Password is incorrect")
    projects=list(db.scalars(select(Project).where(Project.user_id==user.id).with_for_update()))
    active=db.scalar(select(Export.id).where(Export.user_id==user.id,Export.status.in_(["queued","processing"])).limit(1))
    if active or any(p.status not in {"ready","failed","cancelled"} for p in projects):
        raise HTTPException(409,"Cancel clipping and wait for active processing or exports to stop before deleting your account.")
    project_ids=[p.id for p in projects]
    clip_ids=list(db.scalars(select(Clip.id).where(Clip.project_id.in_(project_ids))))
    keys=list(db.scalars(select(Export.output_key).where(Export.user_id==user.id,Export.output_key.is_not(None))))
    keys+=list(db.scalars(select(Asset.key).where(Asset.user_id==user.id)))
    for project in projects:
        if project.source_key and not db.scalar(select(Project.id).where(
                Project.source_key==project.source_key,Project.user_id!=user.id).limit(1)):
            keys.append(project.source_key)
    db.execute(delete(SourceConnection).where(SourceConnection.user_id==user.id))
    db.execute(delete(Export).where(Export.user_id==user.id))
    db.execute(delete(Clip).where(Clip.id.in_(clip_ids)))
    db.execute(delete(Project).where(Project.user_id==user.id))
    db.execute(delete(Asset).where(Asset.user_id==user.id))
    db.execute(delete(BrandKit).where(BrandKit.user_id==user.id))
    db.execute(delete(CreditGrant).where(CreditGrant.user_id==user.id))
    db.execute(delete(CreditReservation).where(CreditReservation.user_id==user.id))
    # Retain an anonymous identity hash to prevent deletion/re-registration trials,
    # and payment rows for transaction reconciliation. No password/email remains.
    user.email=f"deleted-{user.id}@deleted.invalid"
    user.name="Deleted account"
    user.password_hash=passwords.hash(secrets.token_urlsafe(48))
    user.preferences={}
    user.is_admin=False
    user.deleted=True
    user.deletion_keys=keys
    revoke(user)
    db.commit()
    cleanup_deleted_media(db,user)
    response.delete_cookie("session",path="/")
    return {"deleted":True}


def cleanup_deleted_media(db,user):
    remaining=[]
    for key in user.deletion_keys:
        try: storage.delete(key)
        except OSError: remaining.append(key)
    user.deletion_keys=remaining
    folder=storage.path(f"previews/{user.id}")
    if folder.exists(): shutil.rmtree(folder,ignore_errors=True)
    db.commit()
