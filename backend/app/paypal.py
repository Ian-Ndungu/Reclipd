"""PayPal Orders v2, sandbox only. Prices and credits are always server-owned."""
import json
import re
import uuid
from datetime import datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from urllib.parse import urlsplit, urlencode
import httpx
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from .billing import CATALOG,Checkout,payment_out
from .config import settings
from .db import get_db
from .models import Payment,User,CreditGrant
from .security import current_user
from . import credits

router=APIRouter(prefix="/api/billing/paypal")
BASE="https://api-m.sandbox.paypal.com"

def enabled():
    s=settings()
    return s.paypal_sandbox_enabled and all([s.paypal_client_id,s.paypal_client_secret,s.paypal_merchant_id])

def provider(method,path,**kwargs):
    s=settings()
    if not re.fullmatch(r"[A-Z0-9]{13}", s.paypal_merchant_id):
        raise HTTPException(503,"PayPal sandbox seller merchant ID is invalid. Enter the seller account’s 13-character merchant ID, not the app client ID or secret, then restart the API.")
    if not enabled():raise HTTPException(503,"PayPal sandbox is not configured. Live payments are disabled.")
    try:
        with httpx.Client(timeout=20,trust_env=False) as client:
            auth=client.post(BASE+"/v1/oauth2/token",auth=(s.paypal_client_id,s.paypal_client_secret),data={"grant_type":"client_credentials"})
            auth.raise_for_status()
            access=auth.json()["access_token"]
            headers={"Authorization":"Bearer "+access,"Content-Type":"application/json",**kwargs.pop("headers",{})}
            response=client.request(method,BASE+path,headers=headers,**kwargs)
            if response.status_code == 422:
                error=response.json()
                details=error.get("details",[]) if isinstance(error,dict) else []
                if any(isinstance(item,dict) and item.get("issue")=="PAYEE_ACCOUNT_INVALID" for item in details):
                    raise HTTPException(503,"PayPal rejected the sandbox seller account. Configure the merchant ID of the sandbox Business account linked to your app, not your live account or sandbox buyer account, then restart the API.")
            response.raise_for_status()
            data=response.json()
            if not isinstance(data,dict):raise ValueError()
            return data
    except (httpx.HTTPError,ValueError,KeyError):
        raise HTTPException(502,"PayPal could not confirm the request. Check payment history before starting another purchase.")

def order_id(value):
    if not isinstance(value,str) or not value.isalnum() or not 5<=len(value)<=64:
        raise HTTPException(502,"PayPal returned an invalid order identifier")
    return value

def approval(data):
    url=next((l.get("href","") for l in data.get("links",[]) if l.get("rel") in {"approve","payer-action"}),"")
    parsed=urlsplit(url)
    try: port=parsed.port
    except ValueError:raise HTTPException(502,"PayPal returned an invalid checkout destination")
    if parsed.scheme!="https" or parsed.hostname!="www.sandbox.paypal.com" or parsed.username or parsed.password or port not in (None,443):
        raise HTTPException(502,"PayPal returned an unexpected checkout destination")
    return url

@router.post("/checkout")
def checkout(data:Checkout,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    from .main import auth_rate_limit
    auth_rate_limit(request)
    if not enabled():raise HTTPException(503,"PayPal sandbox is not configured. No real payments are available.")
    if user.id in settings().unlimited_user_ids:raise HTTPException(409,"Your account already has unlimited processing")
    pack=next((p for p in CATALOG if p["id"]==data.pack_id),None)
    if not pack:raise HTTPException(422,"Unknown package")
    p=db.scalar(select(Payment).where(Payment.user_id==user.id,Payment.provider=="paypal",
        Payment.pack_id==pack["id"],Payment.status=="pending",
        Payment.created_at>datetime.now(timezone.utc)-timedelta(minutes=20)).order_by(Payment.created_at.desc()).limit(1))
    if p is None:
        p=Payment(reference=uuid.uuid4().hex,user_id=user.id,provider="paypal",
            amount=pack["amount_usd"]*100,currency="USD",minutes=pack["minutes"],pack_id=pack["id"])
        db.add(p);db.commit()
    p=db.scalar(select(Payment).where(Payment.reference==p.reference).with_for_update().execution_options(populate_existing=True))
    if p.provider_order_id:
        result=provider("GET","/v2/checkout/orders/"+order_id(p.provider_order_id))
        if result.get("status") in {"COMPLETED","APPROVED"}:
            return {"reference":p.reference,"needs_verification":True}
    else:
        callback=settings().billing_return_url
        sep="&" if "?" in callback else "?"
        result=provider("POST","/v2/checkout/orders",headers={"PayPal-Request-Id":"create-"+p.reference},json={
            "intent":"CAPTURE","purchase_units":[{"reference_id":p.reference,"custom_id":p.reference,
                "invoice_id":p.reference,"payee":{"merchant_id":settings().paypal_merchant_id},
                "description":"RECLIPD "+pack["name"]+" minutes (sandbox)",
                "amount":{"currency_code":"USD","value":f"{p.amount/100:.2f}"}}],
            "payment_source":{"paypal":{"experience_context":{"brand_name":"RECLIPD AI Studio",
                "user_action":"PAY_NOW","shipping_preference":"NO_SHIPPING",
                "return_url":callback+sep+urlencode({"paypal_reference":p.reference}),
                "cancel_url":callback+sep+urlencode({"paypal_cancelled":"1"})}}}})
        p.provider_order_id=order_id(result.get("id"))
        db.commit()
    return {"reference":p.reference,"authorization_url":approval(result)}

def match_order(p,data):
    units=data.get("purchase_units",[])
    if data.get("id")!=p.provider_order_id or len(units)!=1:
        raise HTTPException(409,"PayPal order does not match this purchase")
    unit=units[0]
    try:
        amount=unit["amount"]
        valid=(unit.get("custom_id")==p.reference and unit.get("reference_id")==p.reference
            and unit.get("payee",{}).get("merchant_id")==settings().paypal_merchant_id
            and amount["currency_code"]==p.currency and Decimal(amount["value"])==Decimal(p.amount)/100)
    except (KeyError,InvalidOperation,TypeError):
        valid=False
    if not valid:raise HTTPException(409,"PayPal amount, currency or merchant does not match")
    return unit

def reconcile(db,reference,capture=False):
    p=db.get(Payment,reference)
    if not p or p.provider!="paypal":raise HTTPException(404,"Payment not found")
    # Same user -> payment lock ordering as authenticated checkout; bonus claims serialize.
    user=db.scalar(select(User).where(User.id==p.user_id).with_for_update().execution_options(populate_existing=True))
    p=db.scalar(select(Payment).where(Payment.reference==reference).with_for_update().execution_options(populate_existing=True))
    if p.status in {"success","refunded","reversed"}:return payment_out(p)
    if not p.provider_order_id:raise HTTPException(409,"Checkout has not opened yet. Retry the package.")
    data=provider("GET","/v2/checkout/orders/"+order_id(p.provider_order_id))
    unit=match_order(p,data)
    if capture and data.get("status")=="APPROVED":
        provider("POST","/v2/checkout/orders/"+p.provider_order_id+"/capture",
                 headers={"PayPal-Request-Id":"capture-"+p.reference},json={})
        data=provider("GET","/v2/checkout/orders/"+p.provider_order_id)
        unit=match_order(p,data)
    if data.get("status")!="COMPLETED":return payment_out(p)
    captures=unit.get("payments",{}).get("captures",[])
    if len(captures)!=1:raise HTTPException(409,"Unexpected PayPal capture details")
    cap=captures[0]
    if cap.get("status")!="COMPLETED":return payment_out(p)
    try:
        valid=cap["amount"]["currency_code"]==p.currency and Decimal(cap["amount"]["value"])==Decimal(p.amount)/100
        paid_at=datetime.fromisoformat(cap["create_time"].replace("Z","+00:00"))
        if not valid or paid_at.tzinfo is None:raise ValueError()
        capture_id=order_id(cap["id"])
    except (KeyError,ValueError,TypeError,InvalidOperation):
        raise HTTPException(409,"PayPal capture amount or timestamp is invalid")
    p.provider_capture_id=capture_id
    if not user.deleted:credits.purchase(db,p,paid_at)
    p.status="success";p.paid_at=paid_at
    db.commit()
    return payment_out(p)

@router.post("/verify/{reference}")
def verify(reference:str,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    from .main import auth_rate_limit
    auth_rate_limit(request)
    p=db.get(Payment,reference)
    if not p or p.user_id!=user.id or p.provider!="paypal":raise HTTPException(404,"Payment not found")
    return reconcile(db,reference,capture=True)

@router.post("/webhook")
async def webhook(request:Request,db:Session=Depends(get_db)):
    if not enabled() or not settings().paypal_webhook_id:raise HTTPException(503,"PayPal webhook is not configured")
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>262144:raise HTTPException(413,"Event too large")
    try:
        event=json.loads(body)
        if not isinstance(event,dict):raise ValueError()
    except (ValueError,TypeError):raise HTTPException(400,"Invalid event")
    names={"auth_algo":"paypal-auth-algo","cert_url":"paypal-cert-url","transmission_id":"paypal-transmission-id",
           "transmission_sig":"paypal-transmission-sig","transmission_time":"paypal-transmission-time"}
    headers={key:request.headers.get(value,"") for key,value in names.items()}
    if not all(headers.values()):raise HTTPException(401,"Missing PayPal signature")
    result=provider("POST","/v1/notifications/verify-webhook-signature",
        json={**headers,"webhook_id":settings().paypal_webhook_id,"webhook_event":event})
    if result.get("verification_status")!="SUCCESS":raise HTTPException(401,"Invalid PayPal signature")
    resource=event.get("resource") or {}
    if not isinstance(resource,dict):raise HTTPException(400,"Invalid resource")
    kind=event.get("event_type")
    supplemental=resource.get("supplementary_data") or {}
    related=supplemental.get("related_ids") or {} if isinstance(supplemental,dict) else {}
    if not isinstance(related,dict):raise HTTPException(400,"Invalid related payment identifiers")
    oid=related.get("order_id")
    if kind=="PAYMENT.CAPTURE.COMPLETED" and isinstance(oid,str):
        p=db.scalar(select(Payment).where(Payment.provider=="paypal",Payment.provider_order_id==oid))
        if p:reconcile(db,p.reference)
    elif kind in {"PAYMENT.CAPTURE.REFUNDED","PAYMENT.CAPTURE.REVERSED"}:
        cid=related.get("capture_id") or (resource.get("id") if kind.endswith("REVERSED") else None)
        if not cid:
            # Refund objects can identify the original capture through an "up" link.
            # Only parse a known PayPal URL; never fetch an event-supplied URL.
            for link in resource.get("links",[]):
                if not isinstance(link,dict) or link.get("rel")!="up":continue
                url=urlsplit(link.get("href",""))
                prefix="/v2/payments/captures/"
                if url.scheme=="https" and url.hostname=="api-m.sandbox.paypal.com" and url.path.startswith(prefix):
                    candidate=url.path[len(prefix):]
                    if candidate.isalnum():cid=candidate
        if cid:
            p=db.scalar(select(Payment).where(Payment.provider=="paypal",Payment.provider_capture_id==cid))
            if p:
                db.scalar(select(User).where(User.id==p.user_id).with_for_update())
                db.refresh(p,with_for_update=True)
                # Conservative: revoke the package on any refund; never remove free credits.
                grant=db.get(CreditGrant,"payment:"+p.reference)
                if grant:grant.remaining=0;grant.expires_at=datetime.now(timezone.utc)
                p.status="refunded" if kind.endswith("REFUNDED") else "reversed"
                db.commit()
    return {"received":True}
