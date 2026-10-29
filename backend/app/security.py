import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import jwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from .config import settings
from .db import get_db
from .models import User

passwords = PasswordHash.recommended()


def token(user_id: str, version: int = 0):
    return jwt.encode(
        {"sub": user_id, "version": version, "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
        settings().secret_key,
        algorithm="HS256",
    )


def current_user(request: Request, db: Session = Depends(get_db)):
    raw = request.cookies.get("session", "")
    try:
        payload = jwt.decode(raw, settings().secret_key, algorithms=["HS256"])
        query=select(User).where(User.id==payload["sub"]).execution_options(populate_existing=True)
        if request.method not in {"GET","HEAD","OPTIONS"}:
            query=query.with_for_update()
        user=db.scalar(query)
        if not user or user.deleted or payload.get("version", 0) != user.session_version:
            raise ValueError()
        return user
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Please sign in")


def validate_url(url: str) -> tuple[str, list[str]]:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        raise ValueError("Invalid URL port")
    if (
        parts.scheme != "https"
        or parts.username
        or parts.password
        or port not in (None, 443)
        or parts.fragment
    ):
        raise ValueError(
            "Only HTTPS media URLs without credentials or fragments are supported"
        )
    if host not in settings().import_allowed_hosts:
        raise ValueError(
            "This host is not approved for direct media import. Upload a file you own instead. YouTube video downloads are not supported."
        )
    addresses = sorted(
        {x[4][0] for x in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    )
    if not addresses or any(
        not ipaddress.ip_address(addr).is_global for addr in addresses
    ):
        raise ValueError("Private, reserved, and local destinations are not allowed")
    return host, addresses
