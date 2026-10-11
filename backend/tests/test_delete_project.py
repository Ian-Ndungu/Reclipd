from app.models import Project, Clip, Export, SourceConnection, User
from app.storage import storage


def test_delete_project_ownership_busy_and_shared_media(signed, db):
    user_id = signed.get('/api/me').json()['id']
    other = User(email='other-delete@example.test', name='Other', password_hash='unused')
    db.add(other); db.flush()
    p = Project(user_id=user_id, name='Delete me', rights_confirmed=True, status='processing', source_key='sources/delete-test.mp4')
    foreign = Project(user_id=other.id, name='Other', rights_confirmed=True, status='ready')
    db.add_all([p, foreign]); db.commit()
    assert signed.delete(f'/api/projects/{foreign.id}').status_code == 404
    assert signed.delete(f'/api/projects/{p.id}').status_code == 409
    p.status = 'ready'
    c = Clip(project_id=p.id, title='Clip', start=0, end=10, score=1, description='Test')
    db.add(c); db.flush()
    e = Export(user_id=user_id, clip_id=c.id, edits={}, status='processing', output_key='exports/delete-test.mp4')
    db.add(e); db.commit()
    assert signed.delete(f'/api/projects/{p.id}').status_code == 409
    e.status = 'complete'
    shared = Project(user_id=user_id, name='Keep original', rights_confirmed=True, status='ready', source_key=p.source_key)
    db.add_all([shared, SourceConnection(user_id=user_id, video_id='abcdefghijk', project_id=p.id)])
    db.commit()
    source = storage.path(p.source_key); source.write_bytes(b'original')
    output = storage.path(e.output_key); output.write_bytes(b'export')
    pid, cid, eid, sid = p.id, c.id, e.id, shared.id
    assert signed.delete(f'/api/projects/{pid}').json() == {'deleted': True}
    assert db.get(Project, pid) is None and db.get(Clip, cid) is None and db.get(Export, eid) is None
    assert db.get(SourceConnection, (user_id, 'abcdefghijk')) is None
    assert source.exists() and not output.exists()
    assert signed.delete(f'/api/projects/{sid}').status_code == 200
    assert not source.exists()
    assert signed.delete(f'/api/projects/{pid}').status_code == 404
