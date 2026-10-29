from datetime import datetime,timezone,timedelta
import pytest
from sqlalchemy import select,func
from app.models import User,Project,CreditGrant,Payment,CreditReservation
from app import credits,billing

T=datetime(2026,1,24,12,tzinfo=timezone.utc)
def user(db):
    u=User(email='credits@example.test',name='Credits',password_hash='unused',created_at=T)
    db.add(u);db.commit();return u

def test_trial_expiry_month_boundaries_and_no_duplicate_grants(db):
    u=user(db)
    assert credits.balance(db,u,T)['available_seconds']==5400
    for _ in range(3):credits.balance(db,u,T)
    assert db.scalar(select(func.count()).select_from(CreditGrant))==1
    end=T+timedelta(days=7)
    b=credits.balance(db,u,end)
    assert b['trial_seconds']==0 and b['free_seconds']==3600
    assert b['next_refresh_at']==datetime(2026,2,28,12,tzinfo=timezone.utc)
    g=db.scalar(select(CreditGrant).where(CreditGrant.kind=='free'));g.remaining=60;db.commit()
    b=credits.balance(db,u,datetime(2026,2,28,12,tzinfo=timezone.utc))
    assert b['free_seconds']==3600
    assert b['next_refresh_at']==datetime(2026,3,31,12,tzinfo=timezone.utc)
    b=credits.balance(db,u,datetime(2027,3,31,12,tzinfo=timezone.utc))
    assert b['free_seconds']==3600 # missed periods never accumulate

def test_consumption_order_idempotent_refund_and_expired_refund(db):
    u=user(db);credits.sync(db,u,T)
    trial=db.get(CreditGrant,'trial:'+u.id);trial.remaining=10
    credits.grant(db,'free-extra',u,'free',20,T+timedelta(days=10),T)
    credits.grant(db,'paid-late',u,'paid',100,T+timedelta(days=365),T)
    credits.grant(db,'paid-soon',u,'paid',100,T+timedelta(days=20),T)
    p=Project(user_id=u.id,name='Example',rights_confirmed=True);db.add(p);db.commit()
    credits.reserve(db,p,50,T);db.commit()
    r=db.get(CreditReservation,p.id)
    assert [a['grant_id'] for a in r.allocations]==['trial:'+u.id,'free-extra','paid-soon']
    assert [a['seconds'] for a in r.allocations]==[10,20,20]
    credits.reserve(db,p,50,T);db.commit()
    assert u.used_seconds==50
    credits.refund(db,p);db.commit();credits.refund(db,p);db.commit()
    assert u.used_seconds==0 and trial.remaining==10
    assert credits.balance(db,u,T+timedelta(days=8))['trial_seconds']==0
    with pytest.raises(ValueError):credits.reserve(db,p,999999,T)
    db.rollback()
    assert db.get(CreditGrant,'paid-soon').remaining==100

def test_creator_bonus_first_two_verified_purchases_and_paid_expiry(db,monkeypatch):
    now=datetime.now(timezone.utc)
    u=user(db)
    for i in range(3):
        p=Payment(reference=f'purchase{i}',user_id=u.id,amount=2000,currency='USD',pack_id='creator',minutes=250)
        db.add(p);db.commit()
        payload={'reference':p.reference,'amount':2000,'currency':'USD','domain':'test','customer':{'email':u.email},'status':'success','paid_at':now.isoformat()}
        monkeypatch.setattr(billing,'provider',lambda *a,**k:payload)
        billing.reconcile(db,p.reference);billing.reconcile(db,p.reference)
        assert p.minutes==(300 if i<2 else 250)
    b=credits.balance(db,u,now)
    assert b['paid_seconds']==850*60
    assert credits.balance(db,u,now+timedelta(days=365))['paid_seconds']==0

def test_canonical_mailbox_cannot_claim_second_trial(signed):
    body={'email':'demo.name@gmail.com','name':'Demo','password':'secure-test-password'}
    assert signed.post('/api/auth/register',json=body).status_code==201
    assert signed.post('/api/auth/register',json={**body,'email':'demoname+again@googlemail.com'}).status_code==409

def test_expired_credit_never_spent_and_failed_job_refund_keeps_expiry(db):
    u=user(db);credits.sync(db,u,T)
    p=Project(user_id=u.id,name='Late failure',rights_confirmed=True);db.add(p);db.commit()
    credits.reserve(db,p,100,T);db.commit()
    expiry=db.get(CreditGrant,'trial:'+u.id).expires_at
    credits.refund(db,p);db.commit()
    assert db.get(CreditGrant,'trial:'+u.id).expires_at==expiry
    assert credits.balance(db,u,T+timedelta(days=7))['available_seconds']==3600

def test_webhook_retry_cannot_duplicate_grant_or_creator_bonus(signed,db,monkeypatch):
    import json,hmac,hashlib
    from app.config import settings
    uid=signed.get('/api/me').json()['id']
    p=Payment(reference='webhook-once',user_id=uid,amount=2000,currency='USD',pack_id='creator',minutes=250)
    db.add(p);db.commit()
    data={'reference':p.reference,'amount':2000,'currency':'USD','domain':'test','customer':{'email':'creator@example.com'},'status':'success','paid_at':datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(settings(),'paystack_secret_key','sk_test_mock')
    monkeypatch.setattr(billing,'provider',lambda *a,**k:data)
    raw=json.dumps({'event':'charge.success','data':data}).encode()
    sig=hmac.new(b'sk_test_mock',raw,hashlib.sha512).hexdigest()
    for _ in range(3):assert signed.post('/api/billing/webhook',content=raw,headers={'x-paystack-signature':sig}).status_code==200
    assert p.minutes==300
    assert db.scalar(select(func.count()).select_from(CreditGrant).where(CreditGrant.kind=='paid'))==1
    assert signed.get('/api/usage').json()['paid_seconds']==18000


def test_legacy_usage_deducted_once_not_every_refresh(db):
    u=user(db);u.used_seconds=600;db.commit()
    assert credits.balance(db,u,T)['trial_seconds']==4800
    assert credits.balance(db,u,T)['trial_seconds']==4800
    assert credits.balance(db,u,T+timedelta(days=7))['free_seconds']==3600
