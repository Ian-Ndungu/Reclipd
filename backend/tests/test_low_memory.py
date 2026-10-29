import sys
from types import SimpleNamespace
import pytest
from app import media
from app.config import settings

@pytest.mark.parametrize("fail",[False,True])
def test_transcription_releases_model_without_changing_quality(monkeypatch,fail,tmp_path):
    calls={}
    class Model:
        def __init__(self,model,**kwargs):
            calls["model"]=model
        def transcribe(self,path,**kwargs):
            calls.update(kwargs)
            def segments():
                if fail: raise RuntimeError("transcription failure")
                yield SimpleNamespace(end=1,words=[SimpleNamespace(start=0,end=1,word="Hello")])
            return segments(),SimpleNamespace(language="en")
    monkeypatch.setitem(sys.modules,"faster_whisper",SimpleNamespace(WhisperModel=Model))
    monkeypatch.setattr(settings(),"low_memory_mode",True)
    monkeypatch.setattr(media,"_whisper",None)
    if fail:
        with pytest.raises(RuntimeError):
            media.transcribe(tmp_path/"audio.wav",1,None,lambda x:None)
    else:
        words,language=media.transcribe(tmp_path/"audio.wav",1,None,lambda x:None)
        assert words==[{"word":"Hello","start":0,"end":1}]
        assert language=="en"
    assert media._whisper is None
    assert calls["model"]==settings().whisper_model
    assert calls["beam_size"]==settings().whisper_beam_size
    assert calls["word_timestamps"] is True

def test_shared_slot_blocks_preview_and_releases_on_failure(monkeypatch,tmp_path):
    from app.processing_gate import processing_slot,ProcessingBusy
    monkeypatch.setattr(settings(),"low_memory_mode",True)
    monkeypatch.setattr(settings(),"storage_root",str(tmp_path))
    with pytest.raises(ValueError):
        with processing_slot():
            with pytest.raises(ProcessingBusy):
                with processing_slot(wait=False):
                    pass
            raise ValueError("job failed")
    with processing_slot(wait=False):
        pass
