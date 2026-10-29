import pytest
from fastapi import HTTPException
from app.config import settings
from app.main import admission
from app.worker import reserve_quota
from app.models import User, Project
from app.media import MediaError

def test_unlimited_account_still_meters_and_other_accounts_capped(signed, db, monkeypatch):
    uid = signed.get('/api/me').json()['id']
    user = db.get(User, uid)
    user.used_seconds = settings().free_minutes * 60
    from app.models import CreditGrant
    from sqlalchemy import select
    for g in db.scalars(select(CreditGrant).where(CreditGrant.user_id==uid)): g.remaining=0
    db.commit()
    with pytest.raises(HTTPException): admission(db, user)
    monkeypatch.setattr(settings(), 'unlimited_user_ids', [uid])
    admission(db, user)
    assert signed.get('/api/usage').json()['limit_seconds'] is None
    p = Project(user_id=uid, name='Unlimited', rights_confirmed=True, status='ready')
    db.add(p); db.commit()
    before = user.used_seconds
    reserve_quota(db, p, 100)
    assert user.used_seconds == before + 100
    other = User(email='limited@example.test',name='Limited',password_hash='unused',used_seconds=before)
    db.add(other); db.flush()
    q = Project(user_id=other.id,name='Limited',rights_confirmed=True)
    db.add(q); db.commit()
    with pytest.raises(MediaError): reserve_quota(db, q, 100)
