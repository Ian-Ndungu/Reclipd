from contextlib import contextmanager
from sqlalchemy import select
from app import credits, worker
from app.models import User, Project, Clip, Export, CreditReservation, CreditGrant
from app.schemas import EditDecision


def setup_clip(db):
    user = db.scalar(select(User))
    project = Project(user_id=user.id, name='Manual', rights_confirmed=True, config={'workflow':'manual'}, status='ready', media={'duration':120}, source_key='sources/manual.mp4')
    db.add(project); db.flush()
    clip = Clip(project_id=project.id, title='Manual', start=0, end=60, score=0, description='Manual', edits=EditDecision(segments=[{'start':0,'end':60}],speed=2).model_dump())
    db.add(clip); db.commit()
    return user, project, clip


def test_manual_export_reservation_reuse_quote_and_refund(signed,db,monkeypatch):
    user, project, clip = setup_clip(db)
    monkeypatch.setattr(worker.render_export,'delay',lambda _: None)
    before=credits.balance(db,user)['available_seconds'];db.commit()
    quote=signed.post(f'/api/clips/{clip.id}/export-quote',json=clip.edits)
    assert quote.json()['seconds']==30
    first=signed.post(f'/api/clips/{clip.id}/exports')
    assert first.status_code==201,first.text
    e=db.get(Export,first.json()['id'])
    e.edits={k:v for k,v in e.edits.items() if k not in {'transition','transition_duration'}}
    db.commit()
    second=signed.post(f'/api/clips/{clip.id}/exports')
    assert first.json()['id']==second.json()['id']
    assert credits.balance(db,user)['available_seconds']==before-30
    assert signed.post(f'/api/clips/{clip.id}/export-quote',json=clip.edits).json()['seconds']==0
    e=db.get(Export,first.json()['id'])
    credits.refund(db,credits.export_account(db,e));db.commit()
    credits.refund(db,credits.export_account(db,e));db.commit()
    assert credits.balance(db,user)['available_seconds']==before


def test_manual_queue_failure_refunds_and_insufficient_credit(signed,db,monkeypatch):
    user,project,clip=setup_clip(db)
    def fail(_):raise RuntimeError('offline')
    monkeypatch.setattr(worker.render_export,'delay',fail)
    before=credits.balance(db,user)['available_seconds'];db.commit()
    response=signed.post(f'/api/clips/{clip.id}/exports')
    assert response.json()['status']=='failed'
    assert credits.balance(db,user)['available_seconds']==before
    for grant in db.scalars(select(CreditGrant)):grant.remaining=0
    db.commit()
    assert signed.post(f'/api/clips/{clip.id}/exports').status_code==402


def test_manual_upload_allowed_without_credits_and_skips_ai(signed,db,monkeypatch):
    user=db.scalar(select(User));credits.sync(db,user)
    for grant in db.scalars(select(CreditGrant)):grant.remaining=0
    db.commit()
    response=signed.post('/api/projects/upload',data={'name':'Manual','rights_confirmed':'true','config':'{"workflow":"manual","resolution":720}'},files={'file':('test.mp4',b'fixture','video/mp4')})
    assert response.status_code==201,response.text
    @contextmanager
    def session():yield db
    monkeypatch.setattr(worker,'SessionLocal',session)
    monkeypatch.setattr(worker,'probe',lambda _: {'duration':240,'has_audio':True,'width':640,'height':360})
    def fail(*a,**k):raise AssertionError('Manual workflow must not transcribe or rank')
    monkeypatch.setattr(worker,'transcribe',fail)
    monkeypatch.setattr(worker,'rank_candidates',fail)
    worker.process_project(response.json()['id'])
    project=db.get(Project,response.json()['id'])
    assert project.status=='ready'
    clip=db.scalar(select(Clip).where(Clip.project_id==project.id))
    assert clip.end==180 and clip.edits['words']==[]
    assert clip.edits['resolution']==720
    assert db.get(CreditReservation,project.id) is None
    assert user.used_seconds==0


def test_successful_manual_export_and_changed_edit_charged(signed,db,monkeypatch):
    from app.storage import storage
    user,project,clip=setup_clip(db)
    monkeypatch.setattr(worker.render_export,'delay',lambda _: None)
    @contextmanager
    def session():yield db
    monkeypatch.setattr(worker,'SessionLocal',session)
    def render(source,output,*a,**k):output.write_bytes(b'finished')
    monkeypatch.setattr(worker,'render',render)
    before=credits.balance(db,user)['available_seconds'];db.commit()
    first=signed.post(f'/api/clips/{clip.id}/exports').json()
    worker.render_export(first['id'])
    assert db.get(CreditReservation,first['id']).status=='complete'
    assert signed.post(f'/api/clips/{clip.id}/exports').json()['id']==first['id']
    clip.edits={**clip.edits,'speed':1};db.commit()
    second=signed.post(f'/api/clips/{clip.id}/exports').json()
    assert second['id']!=first['id']
    assert credits.balance(db,user)['available_seconds']==before-90
    def fail(*a,**k):raise RuntimeError('render error')
    monkeypatch.setattr(worker,'render',fail)
    worker.render_export(second['id'])
    assert credits.balance(db,user)['available_seconds']==before-30
    assert db.get(Export,second['id']).status=='failed'


def test_stale_manual_export_refunds(signed,db,monkeypatch):
    from datetime import datetime,timezone,timedelta
    user,project,clip=setup_clip(db)
    monkeypatch.setattr(worker.render_export,'delay',lambda _: None)
    before=credits.balance(db,user)['available_seconds'];db.commit()
    result=signed.post(f'/api/clips/{clip.id}/exports').json()
    e=db.get(Export,result['id']);e.updated_at=datetime.now(timezone.utc)-timedelta(hours=3);db.commit()
    @contextmanager
    def session():yield db
    monkeypatch.setattr(worker,'SessionLocal',session)
    worker.cleanup()
    assert e.status=='failed'
    assert credits.balance(db,user)['available_seconds']==before
