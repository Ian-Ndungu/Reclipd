"""Run in the API container against PostgreSQL. Uses and removes only a generated QA account."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime, timezone, timedelta
import uuid
from sqlalchemy import select, delete, func
from app.db import SessionLocal
from app.models import User,Project,Payment,CreditGrant,CreditReservation
from app import credits

uid=str(uuid.uuid4())
try:
    with SessionLocal() as db:
        u=User(id=uid,email=f'credit-qa-{uid}@example.test',name='Credit concurrency QA',password_hash='disabled')
        db.add(u);db.flush();credits.sync(db,u)
        ps=[Project(user_id=uid,name='Credit concurrency QA',rights_confirmed=True,status='ready') for _ in range(2)]
        db.add_all(ps);db.commit();ids=[p.id for p in ps]
    barrier=Barrier(2)
    def spend(pid):
        with SessionLocal() as db:
            p=db.get(Project,pid);barrier.wait()
            try:credits.reserve(db,p,4000);db.commit();return True
            except ValueError:db.rollback();return False
    with ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(spend,ids))
    assert sorted(outcomes)==[False,True]
    with SessionLocal() as db:
        assert credits.balance(db,db.get(User,uid))['available_seconds']==1400
        db.commit()
    print('PASS concurrent spending cannot overspend trial balance',flush=True)
    refs=[uuid.uuid4().hex for _ in range(3)]
    with SessionLocal() as db:
        for ref in refs:db.add(Payment(reference=ref,user_id=uid,pack_id='creator',amount=2000,currency='USD',minutes=250))
        db.commit()
    barrier=Barrier(3)
    def buy(ref):
        with SessionLocal() as db:
            p=db.get(Payment,ref);barrier.wait();credits.purchase(db,p,datetime.now(timezone.utc));p.status='success';db.commit()
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(buy,refs))
    with SessionLocal() as db:
        values=list(db.scalars(select(Payment.minutes).where(Payment.user_id==uid)))
        assert sorted(values)==[250,300,300]
        u=db.get(User,uid);u.created_at=datetime.now(timezone.utc)-timedelta(days=40);db.commit()
    print('PASS concurrent Creator purchases award exactly two bonuses',flush=True)
    barrier=Barrier(4)
    def refresh(_):
        with SessionLocal() as db:
            u=db.get(User,uid);barrier.wait();credits.balance(db,u);db.commit()
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(refresh,range(4)))
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(CreditGrant).where(CreditGrant.user_id==uid,CreditGrant.kind=='free'))==1
    print('PASS concurrent monthly refresh creates one grant',flush=True)
finally:
    with SessionLocal() as db:
        for model in [CreditReservation,CreditGrant,Payment,Project]:db.execute(delete(model).where(model.user_id==uid))
        db.execute(delete(User).where(User.id==uid));db.commit()
