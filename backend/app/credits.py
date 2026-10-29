"""Credit allocation is serialized by account row locks; all timestamps are UTC."""
import calendar
import hashlib
import math
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from .models import User, CreditGrant, CreditReservation, Payment
from .config import settings


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def identity(email):
    local, domain=email.strip().casefold().split('@',1)
    if domain in {'gmail.com','googlemail.com'}:
        domain='gmail.com';local=local.split('+',1)[0].replace('.','')
    return hashlib.sha256(f'{local}@{domain}'.encode()).hexdigest()


def month(anchor, n):
    year, m=divmod(anchor.year*12+anchor.month-1+n,12)
    return anchor.replace(year=year,month=m+1,day=min(anchor.day,calendar.monthrange(year,m+1)[1]))


def grant(db, key, user, kind, seconds, expiry, now):
    g=db.scalar(select(CreditGrant).where(CreditGrant.id==key).execution_options(populate_existing=True))
    if g is None:
        g=CreditGrant(id=key,user_id=user.id,kind=kind,seconds=seconds,remaining=seconds,expires_at=expiry,created_at=now)
        db.add(g);db.flush()
    return g


def sync(db, user, now=None):
    now=utc(now or datetime.now(timezone.utc))
    user=db.scalar(select(User).where(User.id==user.id).with_for_update().execution_options(populate_existing=True))
    # Old accounts are mapped once; known aliases share one free-credit entitlement.
    if not user.credit_identity:
        key=identity(user.email)
        owner=db.scalar(select(User).where(User.credit_identity==key))
        if not owner: user.credit_identity=key;db.flush()
    eligible=bool(user.credit_identity)
    activation=utc(user.created_at)
    trial_end=activation+timedelta(days=7)
    current=None; refresh=trial_end
    if eligible and now<trial_end:
        current=grant(db,f'trial:{user.id}',user,'trial',5400,trial_end,now)
    elif eligible:
        n=max(0,(now.year-trial_end.year)*12+now.month-trial_end.month)
        if month(trial_end,n)>now:n-=1
        start=month(trial_end,n);refresh=month(trial_end,n+1)
        current=grant(db,f'free:{user.id}:{start.isoformat()}',user,'free',3600,refresh,now)
    if not user.credit_initialized:
        # Preserve pre-ledger usage without carrying it into future monthly grants.
        legacy=max(0,user.used_seconds)
        old_paid=list(db.scalars(select(Payment).where(Payment.user_id==user.id,Payment.status=='success').order_by(Payment.created_at)))
        if current:
            debit=min(current.remaining,legacy);current.remaining-=debit;legacy-=debit
        for payment in old_paid:
            g=grant(db,'payment:'+payment.reference,user,'paid',payment.minutes*60,utc(payment.paid_at or payment.created_at)+timedelta(days=365),utc(payment.paid_at or payment.created_at))
            debit=min(g.remaining,legacy);g.remaining-=debit;legacy-=debit
        user.credit_initialized=True
    db.flush()
    return user,now,trial_end,refresh


def balance(db,user,now=None):
    user,now,trial_end,refresh=sync(db,user,now)
    buckets=list(db.scalars(select(CreditGrant).where(CreditGrant.user_id==user.id,CreditGrant.expires_at>now,CreditGrant.remaining>0).execution_options(populate_existing=True)))
    amounts={kind:sum(g.remaining for g in buckets if g.kind==kind) for kind in ['trial','free','paid']}
    unlimited=user.id in settings().unlimited_user_ids
    return {'plan':'Unlimited' if unlimited else '7-day trial' if now<trial_end and user.credit_identity else 'Free Forever',
        'unlimited':unlimited,'trial_seconds':amounts['trial'],'free_seconds':amounts['free'],'paid_seconds':amounts['paid'],
        'available_seconds':None if unlimited else sum(amounts.values()),'trial_expires_at':trial_end,
        'next_refresh_at':refresh,'monthly_minutes':60,'eligible':bool(user.credit_identity),
        'paid_grants':[{'remaining_seconds':g.remaining,'expires_at':g.expires_at} for g in buckets if g.kind=='paid']}


def reserve(db,p,duration,now=None):
    if not math.isfinite(duration) or duration<=0:raise ValueError('Invalid source duration')
    user,now,_,_=sync(db,db.get(User,p.user_id),now)
    r=db.get(CreditReservation,p.id)
    if r and r.status in {'reserved','complete'}:return
    if p.quota_reserved:return # pre-ledger running job
    duration=math.ceil(duration*1000)/1000
    allocations=[]
    if user.id not in settings().unlimited_user_ids:
        grants=list(db.scalars(select(CreditGrant).where(CreditGrant.user_id==user.id,CreditGrant.expires_at>now,CreditGrant.remaining>0).execution_options(populate_existing=True)))
        grants.sort(key=lambda g:({'trial':0,'free':1,'paid':2}[g.kind],utc(g.expires_at),g.id))
        if sum(g.remaining for g in grants)+1e-7<duration:raise ValueError('This video exceeds your available processing credits. Choose a shorter video or add minutes.')
        left=duration
        for g in grants:
            take=min(left,g.remaining)
            if take>0:
                g.remaining=max(0,g.remaining-take);allocations.append({'grant_id':g.id,'seconds':take});left-=take
            if left<=1e-7:break
    if r is None:
        r=CreditReservation(project_id=p.id,user_id=user.id,name=p.name,seconds=duration,allocations=allocations,status='reserved',created_at=now);db.add(r)
    else:r.seconds=duration;r.allocations=allocations;r.status='reserved';r.created_at=now
    user.used_seconds+=duration;p.quota_reserved=duration


def refund(db,p):
    user=db.scalar(select(User).where(User.id==p.user_id).with_for_update().execution_options(populate_existing=True))
    r=db.get(CreditReservation,p.id)
    if r and r.status=='reserved':
        for a in r.allocations:
            g=db.scalar(select(CreditGrant).where(CreditGrant.id==a['grant_id']).execution_options(populate_existing=True));g.remaining=min(g.seconds,g.remaining+a['seconds'])
        r.status='refunded'
    elif r:return
    if p.quota_reserved:
        user.used_seconds=max(0,user.used_seconds-p.quota_reserved);p.quota_reserved=0


def complete(db,p):
    r=db.get(CreditReservation,p.id)
    if r:r.status='complete'


def purchase(db,p,paid_at):
    user,now,_,_=sync(db,db.get(User,p.user_id))
    key='payment:'+p.reference
    if db.get(CreditGrant,key):return
    bonus=0
    if p.pack_id=='creator':
        previous=db.scalar(select(func.count()).select_from(Payment).where(Payment.user_id==user.id,Payment.pack_id=='creator',Payment.status=='success',Payment.reference!=p.reference))
        if previous<2:bonus=50
    p.minutes+=bonus;p.paid_at=utc(paid_at)
    grant(db,key,user,'paid',p.minutes*60,p.paid_at+timedelta(days=365),p.paid_at)


def export_account(db, export, name="Manual export"):
    """Use the shared reservation ledger, keyed by the unique export UUID."""
    from types import SimpleNamespace
    r = db.get(CreditReservation, export.id)
    return SimpleNamespace(id=export.id, user_id=export.user_id, name=name[:200],
                           quota_reserved=r.seconds if r and r.status == 'reserved' else 0)


def export_seconds(edits):
    from .edit_timing import timeline_seconds
    return math.ceil(timeline_seconds(edits) / edits.get("speed", 1) * 1000) / 1000


def can_remove_watermark(db, user):
    """A verified purchase unlocks watermark removal for its 365-day term."""
    if user.id in settings().unlimited_user_ids:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    return db.scalar(select(Payment.reference).where(
        Payment.user_id == user.id, Payment.status == "success",
        func.coalesce(Payment.paid_at, Payment.created_at) > cutoff
    ).limit(1)) is not None


def export_edits(db, user, edits):
    from .schemas import EditDecision
    payload = EditDecision.model_validate(edits).model_dump()
    payload["watermark_version"] = 7
    if not can_remove_watermark(db, user):
        payload["watermark"] = True
    return payload
