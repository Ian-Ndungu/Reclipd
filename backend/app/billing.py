"""Paystack sandbox integration. Live keys are deliberately rejected."""
import hashlib
import hmac
import json
import uuid
from datetime import datetime
from . import credits
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import Payment, User
from .security import current_user

router = APIRouter(prefix='/api/billing')

class Checkout(BaseModel):
    pack_id: str = Field(max_length=40)

CATALOG = [
    {"id":"starter","name":"Starter","amount_usd":10,"minutes":100},
    {"id":"creator","name":"Creator","amount_usd":20,"minutes":250,"bonus_minutes":50,"bonus_purchases":2},
    {"id":"pro","name":"Pro","amount_usd":40,"minutes":600},
    {"id":"studio","name":"Studio","amount_usd":80,"minutes":1500},
]

def enabled():
    # Locked until currency support, sandbox end-to-end and merchant configuration are verified.
    return False

def allowance(db, user):
    value=credits.balance(db,user)['available_seconds']
    return user.used_seconds+(value if value is not None else 0)

def provider(method, path, **kwargs):
    key = settings().paystack_secret_key
    if not key.startswith('sk_test_'):
        raise HTTPException(503, 'Configure a Paystack test secret key. Live payments are not enabled.')
    try:
        with httpx.Client(timeout=20, trust_env=False) as client:
            response = client.request(method, 'https://api.paystack.co' + path,
                headers={'Authorization': 'Bearer ' + key}, **kwargs)
        response.raise_for_status()
        result = response.json()
        if result.get('status') is not True or not isinstance(result.get('data'), dict):
            raise ValueError()
        return result['data']
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, 'Paystack could not confirm this request. Check payment history before retrying.')

def payment_out(p):
    return {'reference':p.reference,'amount':p.amount / 100,'currency':p.currency,'minutes':p.minutes,'status':p.status,'created_at':p.created_at,'mode':'test','provider':p.provider}

@router.get('')
def summary(db: Session = Depends(get_db), user: User = Depends(current_user)):
    from .paypal import enabled as paypal_enabled
    return {'enabled':enabled(), 'paypal_enabled':paypal_enabled(), 'mode':'test', 'packs':CATALOG,
        'payments':[payment_out(p) for p in db.scalars(select(Payment).where(Payment.user_id==user.id).order_by(Payment.created_at.desc()).limit(50))]}

@router.post('/checkout')
def checkout(data: Checkout, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not enabled(): raise HTTPException(503,'Test checkout is not configured yet')
    pack = next((p for p in CATALOG if p['id'] == data.pack_id), None)
    if not pack: raise HTTPException(422,'Unknown package')
    if user.id in settings().unlimited_user_ids: raise HTTPException(409,'Your account already has unlimited processing')
    p = Payment(reference=uuid.uuid4().hex,user_id=user.id,amount=pack['amount_usd']*100,minutes=pack['minutes'],currency='USD',pack_id=pack['id'])
    db.add(p);db.commit()
    result = provider('POST','/transaction/initialize',json={'email':user.email,'amount':p.amount,'currency':p.currency,'reference':p.reference,
        'callback_url':settings().billing_return_url,'channels':['card','mobile_money']})
    url = result.get('authorization_url','')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'checkout.paystack.com' or parsed.username or parsed.password or parsed.port not in (None,443):
        raise HTTPException(502,'Unexpected checkout destination')
    return {'authorization_url':url,'reference':p.reference}

def reconcile(db, reference):
    p = db.scalar(select(Payment).where(Payment.reference==reference).with_for_update().execution_options(populate_existing=True))
    if not p or p.provider != 'paystack': raise HTTPException(404,'Payment not found')
    if p.status == 'success': return payment_out(p)
    data = provider('GET','/transaction/verify/' + p.reference)
    user = db.get(User,p.user_id)
    if (data.get('reference') != p.reference or data.get('amount') != p.amount or data.get('currency') != p.currency
        or data.get('domain') != 'test' or (data.get('customer') or {}).get('email','').casefold() != user.email.casefold()):
        raise HTTPException(409,'Payment details do not match this purchase')
    if data.get('status') == 'success':
        try: paid_at=datetime.fromisoformat(data['paid_at'].replace('Z','+00:00'))
        except (KeyError,ValueError,TypeError): raise HTTPException(409,'Missing payment timestamp')
        if paid_at.tzinfo is None: raise HTTPException(409,'Invalid payment timestamp')
        credits.purchase(db,p,paid_at)
        p.status='success'
    elif data.get('status') in {'failed','abandoned','reversed'}: p.status=data['status']
    db.commit()
    return payment_out(p)

@router.post('/verify/{reference}')
def verify(reference: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p=db.get(Payment,reference)
    if not p or p.user_id != user.id: raise HTTPException(404,'Payment not found')
    return reconcile(db,reference)

@router.post('/webhook')
async def webhook(request: Request, db: Session = Depends(get_db)):
    key=settings().paystack_secret_key
    if not key.startswith('sk_test_'): raise HTTPException(503,'Test payments not configured')
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>262144: raise HTTPException(413,'Event too large')
    signature=request.headers.get('x-paystack-signature','')
    if not hmac.compare_digest(hmac.new(key.encode(),body,hashlib.sha512).hexdigest(),signature):
        raise HTTPException(401,'Invalid signature')
    try:
        event=json.loads(body)
        if not isinstance(event,dict): raise ValueError()
        data=event.get('data') or {}
        if not isinstance(data,dict): raise ValueError()
    except (ValueError,TypeError): raise HTTPException(400,'Invalid event')
    if event.get('event') == 'charge.success':
        ref=data.get('reference')
        if isinstance(ref,str) and db.get(Payment,ref): reconcile(db,ref)
    return {'received':True}
