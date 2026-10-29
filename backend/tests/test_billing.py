import hashlib,hmac,json
from app import billing
from app.config import settings
from app.models import Payment,User

def test_verified_payment_is_idempotent_and_owner_scoped(signed,db,monkeypatch):
    uid=signed.get('/api/me').json()['id']
    p=Payment(reference='abc',user_id=uid,amount=10000,minutes=60)
    db.add(p);db.commit()
    original=billing.allowance(db,db.get(User,uid))
    result={'reference':'abc','amount':10000,'currency':'KES','domain':'test','customer':{'email':'creator@example.com'},'status':'success','paid_at':'2026-10-12T00:00:00Z'}
    monkeypatch.setattr(billing,'provider',lambda *a,**k:result)
    result['amount']=1
    assert signed.post('/api/billing/verify/abc').status_code==409
    assert billing.allowance(db,db.get(User,uid))==original
    result['amount']=10000
    for _ in range(2): assert signed.post('/api/billing/verify/abc').status_code==200
    assert billing.allowance(db,db.get(User,uid))==original+3600
    assert signed.post('/api/billing/verify/missing').status_code==404

def test_webhook_signature_and_disabled_live_keys(signed,db,monkeypatch):
    monkeypatch.setattr(settings(),'paystack_secret_key','sk_live_not_allowed')
    assert signed.post('/api/billing/checkout',json={'pack_id':'x'}).status_code==503
    monkeypatch.setattr(settings(),'paystack_secret_key','sk_test_example')
    payload=json.dumps({'event':'charge.success','data':{'reference':'unknown'}}).encode()
    assert signed.post('/api/billing/webhook',content=payload).status_code==401
    signature=hmac.new(b'sk_test_example',payload,hashlib.sha512).hexdigest()
    assert signed.post('/api/billing/webhook',content=payload,headers={'x-paystack-signature':signature}).status_code==200

def test_checkout_stays_disabled_even_with_test_credentials(signed,monkeypatch):
    monkeypatch.setattr(settings(),'paystack_secret_key','sk_test_example')
    assert signed.post('/api/billing/checkout',json={'pack_id':'creator'}).status_code==503
    catalog=signed.get('/api/billing').json()
    assert catalog['enabled'] is False
    assert [(p['amount_usd'],p['minutes']) for p in catalog['packs']]==[(10,100),(20,250),(40,600),(80,1500)]
