from app.models import Project

def test_cancel_and_retry_queued_project(signed, db):
    uid = signed.get('/api/me').json()['id']
    p = Project(user_id=uid,name='Cancel test',rights_confirmed=True,status='queued')
    db.add(p); db.commit()
    assert signed.post(f'/api/projects/{p.id}/cancel').json()['status'] == 'cancelled'
    assert signed.post(f'/api/projects/{p.id}/retry').json()['status'] == 'queued'
    p.status='processing'; db.commit()
    assert signed.post(f'/api/projects/{p.id}/cancel').json()['status'] == 'cancelling'
    assert signed.delete(f'/api/projects/{p.id}').status_code == 409
    assert signed.post(f'/api/projects/{p.id}/retry').status_code == 409
    p.status='ready'; db.commit()
    assert signed.post(f'/api/projects/{p.id}/cancel').status_code == 409

def test_worker_acknowledges_cancellation_and_refunds(signed, db, monkeypatch):
    from app import worker
    from app.models import User
    from app.storage import storage
    uid = signed.get('/api/me').json()['id']
    u=db.get(User,uid);u.used_seconds=100
    p=Project(user_id=uid,name='Worker cancellation',rights_confirmed=True,status='queued',source_key='sources/cancel-test.mp4',quota_reserved=100)
    db.add(p);db.commit();pid=p.id
    source=storage.path(p.source_key);source.write_bytes(b'test')
    def probe(_):
        p.status='cancelling';db.commit()
        return {'duration':100}
    monkeypatch.setattr(worker,'SessionLocal',lambda:db)
    monkeypatch.setattr(worker,'probe',probe)
    worker.process_project.run(pid)
    saved=db.get(Project,pid)
    assert saved.status=='cancelled'
    assert saved.quota_reserved==0
    assert db.get(User,uid).used_seconds==0
    assert source.exists()
