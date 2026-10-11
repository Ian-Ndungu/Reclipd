from app import worker
from app.models import Project, User, Clip
from sqlalchemy import select


def seed(db):
    user = User(email="test@example.com", name="Test", password_hash="unused")
    db.add(user)
    db.flush()
    project = Project(
        user_id=user.id,
        name="Test",
        rights_confirmed=True,
        source_key="sources/example.mp4",
        config={"clip_count": 2, "min_duration": 5, "max_duration": 10},
    )
    db.add(project)
    db.commit()
    return user, project


class SessionContext:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *args):
        pass


def test_task_persists_results_and_duplicate_delivery_is_idempotent(db, monkeypatch):
    user, p = seed(db)
    monkeypatch.setattr(worker, "SessionLocal", lambda: SessionContext(db))
    monkeypatch.setattr(
        worker,
        "probe",
        lambda p: {"duration": 20, "width": 640, "height": 360, "has_audio": False},
    )
    monkeypatch.setattr(worker, "detect_scenes", lambda p: [0, 10])
    worker.process_project.run(p.id)
    db.refresh(p)
    db.refresh(user)
    assert p.status == "ready" and p.progress == 100
    assert user.used_seconds == 20
    assert len(list(db.scalars(select(Clip)))) == 2
    worker.process_project.run(p.id)
    assert len(list(db.scalars(select(Clip)))) == 2
    assert user.used_seconds == 20


def test_failure_refunds_quota(db, monkeypatch):
    user, p = seed(db)
    monkeypatch.setattr(worker, "SessionLocal", lambda: SessionContext(db))
    monkeypatch.setattr(
        worker,
        "probe",
        lambda p: {"duration": 20, "width": 640, "height": 360, "has_audio": True},
    )
    monkeypatch.setattr(
        worker,
        "extract_audio",
        lambda *a: (_ for _ in ()).throw(RuntimeError("failed")),
    )
    worker.process_project.run(p.id)
    db.refresh(p)
    db.refresh(user)
    assert p.status == "failed" and p.error
    assert user.used_seconds == 0 and p.quota_reserved == 0


def test_reservation_rejects_excess_without_charging(db, monkeypatch):
    user, p = seed(db)
    user.used_seconds = 7190
    db.commit()
    monkeypatch.setattr(worker, "SessionLocal", lambda: SessionContext(db))
    monkeypatch.setattr(
        worker,
        "probe",
        lambda p: {"duration": 20, "width": 640, "height": 360, "has_audio": False},
    )
    worker.process_project.run(p.id)
    db.refresh(p)
    db.refresh(user)
    assert p.status == "failed"
    assert user.used_seconds == 7190
