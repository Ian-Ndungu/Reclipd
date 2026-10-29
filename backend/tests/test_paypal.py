from datetime import datetime,timezone
import copy
import json
import pytest
from sqlalchemy import select
from app import paypal,credits
from app.config import settings
from app.models import Payment,User,CreditGrant

@pytest.fixture
def configured(monkeypatch):
    for name,value in {'paypal_sandbox_enabled':True,'paypal_client_id':'sandbox-client','paypal_client_secret':'sandbox-secret',
                       'paypal_merchant_id':'MERCHANT123','paypal_webhook_id':'WEBHOOK123'}.items():
        monkeypatch.setattr(settings(),name,value)

def payment(db,pack='creator'):
    user=db.scalar(select(User))
    p=Payment(reference='testpaypalref',user_id=user.id,provider='paypal',provider_order_id='ORDER12345',
              amount=2000,currency='USD',minutes=250,pack_id=pack)
    db.add(p);db.commit()
    return p

def order(p,status='COMPLETED'):
    return {'id':p.provider_order_id,'status':status,'purchase_units':[{
        'reference_id':p.reference,'custom_id':p.reference,'payee':{'merchant_id':'MERCHANT123'},
        'amount':{'currency_code':'USD','value':'20.00'},
        'payments':{'captures':[{'id':'CAPTURE123','status':'COMPLETED','amount':{'currency_code':'USD','value':'20.00'},
                                'create_time':datetime.now(timezone.utc).isoformat()}]}}]}

def test_disabled_without_configuration_and_prices_owned_by_server(signed,db,monkeypatch,configured):
    monkeypatch.setattr(settings(),'paypal_sandbox_enabled',False)
    assert signed.post('/api/billing/paypal/checkout',json={'pack_id':'creator'}).status_code==503
    monkeypatch.setattr(settings(),'paypal_sandbox_enabled',True)
    seen=[]
    def provider(method,path,**kw):
        seen.append(kw)
        if method=='GET':return {'id':'ORDER12345','status':'CREATED','links':[{'rel':'approve','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER12345'}]}
        return {'id':'ORDER12345','links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER12345'}]}
    monkeypatch.setattr(paypal,'provider',provider)
    r=signed.post('/api/billing/paypal/checkout',json={'pack_id':'creator','amount':1})
    assert r.status_code==200,r.text
    assert seen[0]['json']['purchase_units'][0]['amount']=={'currency_code':'USD','value':'20.00'}
    ref=r.json()['reference']
    assert signed.post('/api/billing/paypal/checkout',json={'pack_id':'creator'}).json()['reference']==ref
    assert len(list(db.scalars(select(Payment))))==1

def test_capture_and_credit_only_once(signed,db,monkeypatch,configured):
    p=payment(db);calls=[]
    def provider(method,path,**kw):
        calls.append((method,path,kw))
        if method=='POST':return {}
        return order(p,'APPROVED' if len(calls)==1 else 'COMPLETED')
    monkeypatch.setattr(paypal,'provider',provider)
    for _ in range(2):
        result=signed.post('/api/billing/paypal/verify/'+p.reference)
        assert result.status_code==200,result.text
    assert db.get(CreditGrant,'payment:'+p.reference).seconds==300*60
    assert p.minutes==300
    assert sum(method=='POST' for method,_,_ in calls)==1
    assert calls[1][2]['headers']['PayPal-Request-Id']=='capture-'+p.reference

@pytest.mark.parametrize('mutation',['amount','merchant','currency','capture','reference'])
def test_rejects_tampered_purchase(signed,db,monkeypatch,configured,mutation):
    p=payment(db);data=order(p);unit=data['purchase_units'][0]
    if mutation=='amount':unit['amount']['value']='1.00'
    if mutation=='merchant':unit['payee']['merchant_id']='ATTACKER'
    if mutation=='currency':unit['amount']['currency_code']='EUR'
    if mutation=='capture':unit['payments']['captures'][0]['amount']['value']='1.00'
    if mutation=='reference':unit['custom_id']='other'
    monkeypatch.setattr(paypal,'provider',lambda *a,**k:data)
    assert signed.post('/api/billing/paypal/verify/'+p.reference).status_code==409
    assert db.get(CreditGrant,'payment:'+p.reference) is None

def test_pending_no_credit_other_user_denied(signed,db,monkeypatch,configured):
    p=payment(db)
    monkeypatch.setattr(paypal,'provider',lambda *a,**k:order(p,'CREATED'))
    assert signed.post('/api/billing/paypal/verify/'+p.reference).json()['status']=='pending'
    assert db.get(CreditGrant,'payment:'+p.reference) is None
    signed.post('/api/auth/register',json={'email':'other@example.test','password':'another-password'})
    assert signed.post('/api/billing/paypal/verify/'+p.reference).status_code==404

def test_webhook_signature_replay_and_refund(signed,db,monkeypatch,configured):
    p=payment(db)
    headers={k:'test' for k in ['paypal-auth-algo','paypal-cert-url','paypal-transmission-id','paypal-transmission-sig','paypal-transmission-time']}
    payload={'event_type':'PAYMENT.CAPTURE.COMPLETED','resource':{'supplementary_data':{'related_ids':{'order_id':p.provider_order_id}}}}
    monkeypatch.setattr(paypal,'provider',lambda *a,**k:{'verification_status':'FAILURE'})
    assert signed.post('/api/billing/paypal/webhook',json=payload,headers=headers).status_code==401
    def provider(method,path,**kw):
        if path.endswith('verify-webhook-signature'):return {'verification_status':'SUCCESS'}
        return order(p)
    monkeypatch.setattr(paypal,'provider',provider)
    for _ in range(2):assert signed.post('/api/billing/paypal/webhook',json=payload,headers=headers).status_code==200
    assert db.get(CreditGrant,'payment:'+p.reference).seconds==18000
    refund={'event_type':'PAYMENT.CAPTURE.REFUNDED','resource':{'supplementary_data':{'related_ids':{'capture_id':'CAPTURE123'}}}}
    assert signed.post('/api/billing/paypal/webhook',json=refund,headers=headers).status_code==200
    assert db.get(CreditGrant,'payment:'+p.reference).remaining==0
    signed.post('/api/billing/paypal/webhook',json=payload,headers=headers)
    assert p.status=='refunded'
    assert db.get(CreditGrant,'payment:'+p.reference).remaining==0

def test_unexpected_checkout_host_rejected():
    with pytest.raises(Exception):
        paypal.approval({'links':[{'rel':'approve','href':'https://evil.example/checkout'}]})

def test_invalid_merchant_configuration_has_actionable_error(configured,monkeypatch):
    monkeypatch.setattr(settings(),'paypal_merchant_id','x'*80)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        paypal.provider('POST','/v2/checkout/orders')
    assert error.value.status_code==503
    assert '13-character merchant ID' in error.value.detail

def test_invalid_payee_is_actionable_without_exposing_provider_data(configured,monkeypatch):
    import httpx
    from fastapi import HTTPException
    monkeypatch.setattr(settings(),'paypal_merchant_id','MERCHANT12345')
    def handler(request):
        if request.url.path=='/v1/oauth2/token':
            return httpx.Response(200,json={'access_token':'private-token'})
        return httpx.Response(422,json={'details':[{'issue':'PAYEE_ACCOUNT_INVALID','value':'private-value'}]})
    original=httpx.Client
    monkeypatch.setattr(paypal.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler)))
    with pytest.raises(HTTPException) as error:
        paypal.provider('POST','/v2/checkout/orders')
    assert error.value.status_code==503
    assert 'sandbox Business account' in error.value.detail
    assert 'private' not in error.value.detail
