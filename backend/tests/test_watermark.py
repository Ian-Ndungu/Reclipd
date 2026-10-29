from datetime import datetime, timezone, timedelta
from app import credits, worker
from app.models import Payment, Export
from app.media import watermark_filter, run
from test_manual import setup_clip


def test_free_cannot_bypass_and_legacy_export_not_reused(signed, db, monkeypatch):
    user, project, clip = setup_clip(db)
    clip.edits = {**clip.edits, "watermark": False}
    old = Export(user_id=user.id, clip_id=clip.id, edits={k:v for k,v in clip.edits.items() if k != "watermark"})
    db.add(old); db.commit()
    monkeypatch.setattr(worker.render_export, 'delay', lambda _: None)
    quote = signed.post(f'/api/clips/{clip.id}/export-quote', json=clip.edits).json()
    assert not quote['can_remove_watermark'] and not quote['reused']
    response = signed.post(f'/api/clips/{clip.id}/exports')
    assert response.status_code == 201
    assert response.json()['id'] != old.id
    assert db.get(Export, response.json()['id']).edits['watermark'] is True


def test_paid_can_opt_out_and_expired_or_pending_cannot(signed, db, monkeypatch):
    user, project, clip = setup_clip(db)
    payment = Payment(reference='watermark-test', user_id=user.id, amount=1000, minutes=100,
                      status='pending', paid_at=datetime.now(timezone.utc))
    db.add(payment); db.commit()
    assert not credits.can_remove_watermark(db, user)
    payment.status='success'; db.commit()
    assert credits.can_remove_watermark(db, user)
    assert credits.export_edits(db, user, clip.edits)['watermark'] is True
    clip.edits={**clip.edits, 'watermark':False}; db.commit()
    monkeypatch.setattr(worker.render_export, 'delay', lambda _: None)
    response=signed.post(f'/api/clips/{clip.id}/exports')
    assert db.get(Export,response.json()['id']).edits['watermark'] is False
    payment.paid_at=datetime.now(timezone.utc)-timedelta(days=366); db.commit()
    assert not credits.can_remove_watermark(db,user)


def test_watermark_renders_pixels(tmp_path):
    plain=tmp_path/'plain.rgb'; marked=tmp_path/'marked.rgb'
    for output, vf in [(plain,'null'),(marked,watermark_filter(360,640,tmp_path/"mark.ass"))]:
        run(['ffmpeg','-v','error','-f','lavfi','-i','color=black:s=360x640:d=2',
             '-vf',vf,'-ss','1.2','-frames:v','1','-pix_fmt','rgb24','-threads','1','-f','rawvideo',str(output)])
    assert plain.read_bytes() != marked.read_bytes()
    assert len(plain.read_bytes()) == len(marked.read_bytes())


def test_watermark_animation_top_left_and_settles(tmp_path):
    vf=watermark_filter(360,640,tmp_path/"animated.ass")
    frames=[]
    for moment in [2.3,4.0,4.3]:
        output=tmp_path/f"{moment}.rgb"
        run(['ffmpeg','-v','error','-f','lavfi','-i','color=black:s=360x640:d=5',
             '-vf',vf,'-ss',str(moment),'-frames:v','1','-pix_fmt','rgb24',
             '-threads','1','-f','rawvideo',str(output)])
        frames.append(output.read_bytes())
    assert frames[0] != frames[1]
    assert frames[1] == frames[2]
    # Branding occupies the top-left safe area, not the caption region.
    assert any(frames[1][:360*80*3])
    assert not any(frames[1][360*100*3:])


def test_long_watermark_replays_only_once(tmp_path):
    path=tmp_path/"long.ass"
    watermark_filter(720,1280,path,32)
    text=path.read_text()
    assert "0:00:16.00" in text
    assert "0:00:18.00" in text
    assert "0:00:32.00" in text
    watermark_filter(720,1280,path,15)
    assert "0:00:16.00" not in path.read_text()


def test_flip_and_dashed_cut_sequence(tmp_path):
    path=tmp_path/"flip.ass"
    watermark_filter(720,1280,path,10)
    text=path.read_text()
    assert "0:00:03.80" in text
    assert "Style: Mark,Montserrat," in text
    assert "\\frx360.00" in text
    assert "\\1c&HFFD17D&" in text
