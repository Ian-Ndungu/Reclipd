from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from app import accounts
from app.models import User,Project,Clip,Asset,BrandKit,CreditGrant
from app.config import settings
from app.storage import storage

def test_password_change_revokes_old_session(signed,db):
    old=signed.cookies.get('session')
    assert signed.post('/api/auth/change-password',json={'current_password':'wrong','new_password':'another-secure-password'}).status_code==400
    response=signed.post('/api/auth/change-password',json={'current_password':'secure-test-password','new_password':'another-secure-password'})
    assert response.status_code==200
    new=signed.cookies.get('session')
    assert new != old
    assert signed.get('/api/me').status_code==200
    signed.cookies.set('session',old)
    assert signed.get('/api/me').status_code==401
    assert signed.post('/api/auth/login',json={'email':'creator@example.com','password':'secure-test-password'}).status_code==401
    assert signed.post('/api/auth/login',json={'email':'creator@example.com','password':'another-secure-password'}).status_code==200

def test_preferences_persist_and_patch(signed,db):
    assert signed.put('/api/me/preferences',json={'resolution':720,'caption_preset':'minimal','theme':'dark'}).status_code==200
    signed.put('/api/me/preferences',json={'theme':'system'})
    signed.post('/api/auth/logout')
    signed.post('/api/auth/login',json={'email':'creator@example.com','password':'secure-test-password'})
    assert signed.get('/api/me').json()['preferences']=={'resolution':720,'caption_preset':'minimal','theme':'system','onboarding_completed':False}
    assert signed.put('/api/me/preferences',json={'resolution':999}).status_code==422
    assert signed.put('/api/me/preferences',json={'caption_preset':'invented'}).status_code==422

def configure_mail(monkeypatch):
    for key,value in {'smtp_host':'smtp.example.test','smtp_username':'test','smtp_password':'test','smtp_from':'test@example.test'}.items():
        monkeypatch.setattr(settings(),key,value)

def test_recovery_single_use_expiry_and_no_enumeration(signed,db,monkeypatch):
    configure_mail(monkeypatch)
    sent=[]
    monkeypatch.setattr(accounts,'send_reset',lambda email,token:sent.append((email,token)))
    generic=signed.post('/api/auth/forgot-password',json={'email':'nobody@example.test'})
    found=signed.post('/api/auth/forgot-password',json={'email':'creator@example.com'})
    assert generic.json()==found.json()
    assert len(sent)==1
    raw=sent[0][1]
    user=db.scalar(select(User))
    assert raw not in str(found.json()) and user.reset_digest!=raw
    signed.post('/api/auth/forgot-password',json={'email':'creator@example.com'})
    assert len(sent)==1
    old=signed.cookies.get('session')
    assert signed.post('/api/auth/reset-password',json={'token':raw,'new_password':'recovered-password'}).status_code==200
    assert signed.post('/api/auth/reset-password',json={'token':raw,'new_password':'recovered-password'}).status_code==400
    signed.cookies.set('session',old)
    assert signed.get('/api/me').status_code==401
    signed.post('/api/auth/forgot-password',json={'email':'creator@example.com'})
    user.reset_expires=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert signed.post('/api/auth/reset-password',json={'token':sent[-1][1],'new_password':'recovered-password'}).status_code==400

def test_recovery_unconfigured_and_delivery_failure(signed,db,monkeypatch):
    monkeypatch.setattr(settings(),'smtp_host','')
    assert signed.post('/api/auth/forgot-password',json={'email':'creator@example.com'}).status_code==503
    configure_mail(monkeypatch)
    def fail(*args):raise OSError("offline")
    monkeypatch.setattr(accounts,'send_reset',fail)
    assert signed.post('/api/auth/forgot-password',json={'email':'creator@example.com'}).status_code==200
    assert db.scalar(select(User)).reset_digest is None

def test_delete_requires_password_blocks_active_and_removes_content(signed,db):
    user=db.scalar(select(User));old=signed.cookies.get('session')
    project=Project(user_id=user.id,name='Private',rights_confirmed=True,status='processing',source_key='sources/deletion.mp4')
    db.add(project);db.commit()
    storage.path(project.source_key).write_bytes(b'original')
    data={'password':'secure-test-password','confirmation':'DELETE'}
    assert signed.request('DELETE','/api/me',json={**data,'password':'wrong'}).status_code==400
    assert signed.request('DELETE','/api/me',json=data).status_code==409
    project.status='ready'
    db.add(Clip(project_id=project.id,title='private',start=0,end=1,score=0,description='private',edits={}))
    db.add(BrandKit(user_id=user.id,name='brand',config={}))
    db.commit()
    assert signed.request('DELETE','/api/me',json=data).status_code==200
    assert db.scalar(select(Project)) is None and db.scalar(select(Clip)) is None
    assert db.scalar(select(BrandKit)) is None and db.scalar(select(CreditGrant)) is None
    assert not storage.path('sources/deletion.mp4').exists()
    assert user.deleted and user.email.endswith('@deleted.invalid') and user.credit_identity
    signed.cookies.set('session',old)
    assert signed.get('/api/me').status_code==401
    assert signed.post('/api/auth/login',json={'email':'creator@example.com','password':'secure-test-password'}).status_code==401
    assert signed.post('/api/auth/register',json={'email':'creator@example.com','password':'secure-test-password'}).status_code==409

def test_onboarding_completion_survives_login_and_preference_updates(signed):
    assert signed.get('/api/me').json()['preferences']['onboarding_completed'] is False
    assert signed.put('/api/me/preferences',json={'onboarding_completed':True}).status_code==200
    signed.put('/api/me/preferences',json={'theme':'dark'})
    assert signed.get('/api/me').json()['preferences']['onboarding_completed'] is True
