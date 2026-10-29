from app.tracking import SubjectTracker, simplify, deduplicate


def test_first_detection_no_drift_from_center():
    tracker=SubjectTracker()
    assert tracker.update([(.7,.2,.2,.3)],0)==.8


def test_larger_bystander_does_not_steal_subject():
    tracker=SubjectTracker()
    tracker.update([(.1,.2,.2,.3)],0)
    for i in range(1,9):
        assert tracker.update([(.11,.2,.2,.3),(.65,.1,.3,.5)],i*.25)<.3


def test_temporary_occlusion_holds_then_reacquires():
    tracker=SubjectTracker()
    tracker.update([(.1,.2,.2,.3)],0)
    assert tracker.update([(.7,.2,.2,.3)],.5)==.2
    assert tracker.update([(.7,.2,.2,.3)],1.75)>.2


def test_cut_resets_and_jitter_does_not_pan():
    tracker=SubjectTracker()
    tracker.update([(.1,.2,.2,.3)],0)
    assert tracker.update([(.104,.2,.2,.3)],.25)==.2
    assert tracker.update([(.7,.2,.2,.3)],.5,cut=True)==.8


def test_missing_faces_return_to_fallback_and_bound_path():
    tracker=SubjectTracker(.5)
    tracker.update([(.7,.2,.2,.3)],0)
    assert .5<tracker.update([],4)<.8
    assert len(deduplicate([(.1,.1,.2,.2),(.11,.1,.2,.2)]))==1
    points=[(i*.25,.5+(i%2)*.1) for i in range(720)]
    reduced=simplify(points)
    assert len(reduced)<=256 and reduced[0]==points[0] and reduced[-1]==points[-1]


def test_linear_motion_compression():
    points=[(i*.25,.1+i*.001) for i in range(100)]
    assert simplify(points)==[points[0],points[-1]]


def test_crop_filter_holds_initial_focus_before_first_point():
    from app.media import crop_filter
    value=crop_filter({'width':640,'height':360},180,320,'auto',.5,[(0,.2),(.25,.8)])
    assert '0.25' in value and 'max(0,min(iw-ow' in value


def test_real_ffmpeg_bounded_tracking_expression(tmp_path):
    import shutil
    import pytest
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg integration runs in Docker')
    from app.media import run, probe, crop_filter, face_track
    source=tmp_path/'source.mp4';output=tmp_path/'crop.mp4'
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=gray:size=640x360:rate=30','-t','3','-c:v','libx264',str(source)])
    # Fractional start, no faces: stable fallback and valid clip-relative times.
    points=face_track(source,.375,1.625,.3)
    assert points[0]==(0,.3) and points[-1]==(1.25,.3)
    trajectory=[(i*3/255,.2 if i%2 else .8) for i in range(256)]
    vf=crop_filter(probe(source),180,320,'auto',.5,trajectory)
    run(['ffmpeg','-v','error','-y','-i',str(source),'-vf',vf,'-c:v','libx264',str(output)])
    assert probe(output)['width']==180
