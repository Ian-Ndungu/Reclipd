import json
import pytest
from app import videoscale as v
from app.config import settings
from app.media import MediaError

def formats():
    return [
        dict(protocol="https", format_id="137", vcodec="avc1.1", acodec="none", height=1080, ext="mp4", filesize=1000),
        dict(protocol="https", format_id="136", vcodec="avc1.1", acodec="none", height=720, ext="mp4", filesize=500),
        dict(protocol="https", format_id="140", vcodec="none", acodec="mp4a.40.2", abr=128, filesize=100),
    ]

def test_quality_audio_and_size():
    selected, limits = v.select_formats(formats(), 2000)
    assert [f["format_id"] for f in selected] == ["137", "140"]
    assert limits == [1250, 125]
    with pytest.raises(MediaError, match="size limit"):
        v.select_formats(formats(), 1000)
    with pytest.raises(MediaError, match="audio"):
        v.select_formats(formats()[:2], 2000)
    bad = formats()
    bad[0]["has_drm"] = True
    assert v.select_formats(bad, 2000)[0][0]["height"] == 720

def test_budget_persistent_and_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings(), "storage_root", str(tmp_path))
    monkeypatch.setattr(settings(), "videoscale_budget_bytes", 100)
    v.reserve_bandwidth(70)
    with pytest.raises(MediaError, match="allowance"):
        v.reserve_bandwidth(31)
    v.reserve_bandwidth(30)
    with pytest.raises(MediaError):
        v.reserve_bandwidth(1)

@pytest.mark.parametrize("url", ["https://127.0.0.1/file", "https://evil.example/file",
    "https://s3.fr-par.scw.cloud@evil.example/file", "https://s3.fr-par.scw.cloud:8443/file"])
def test_download_rejects_untrusted_destinations(tmp_path, url):
    with pytest.raises(MediaError, match="destination"):
        v.download_file(url, tmp_path/"file", 100, 100, lambda *a: None)

def test_provider_failure_hides_secrets():
    import httpx
    class Client:
        def request(self, *a, **k):
            return httpx.Response(403, json={"error": "secret-token"})
    with pytest.raises(MediaError) as e:
        v.request(Client(), "/api/formats")
    assert "secret-token" not in str(e.value)

def test_retrieval_merges_and_validates(tmp_path, monkeypatch):
    from app import imports
    cfg = settings()
    monkeypatch.setattr(cfg, "videoscale_enabled", True)
    monkeypatch.setattr(cfg, "videoscale_auth_header", "Basic test")
    monkeypatch.setattr(imports, "metadata", lambda _: dict(public_unrestricted=True, duration=20))
    responses = iter([formats(), {"task_id":"video"}, {"status":"completed"}, {"download_url":"video"},
                       {"task_id":"audio"}, {"status":"completed"}, {"download_url":"audio"}])
    monkeypatch.setattr(v, "request", lambda *a, **k: next(responses))
    reserved=[]
    monkeypatch.setattr(v, "reserve_bandwidth", reserved.append)
    monkeypatch.setattr(v, "download_file", lambda u,p,*a: p.write_bytes(b"stream"))
    commands=[]
    def run(args, **kwargs):
        commands.append(args)
        from pathlib import Path
        Path(args[-1]).write_bytes(b"merged")
    monkeypatch.setattr(v, "run", run)
    monkeypatch.setattr(v, "probe", lambda p: {"has_audio":True})
    target=tmp_path/"final.mp4"
    v.retrieve("abcdefghijk", target, lambda *a: None)
    assert target.read_bytes()==b"merged"
    assert reserved==[1375]
    assert "copy" in commands[0] and "1:a:0" in commands[0]
    assert list(tmp_path.iterdir())==[target]

def test_private_metadata_blocks_before_provider(tmp_path, monkeypatch):
    from app import imports
    monkeypatch.setattr(settings(), "videoscale_enabled", True)
    monkeypatch.setattr(settings(), "videoscale_auth_header", "Basic test")
    monkeypatch.setattr(imports, "metadata", lambda _: dict(public_unrestricted=False, duration=20))
    monkeypatch.setattr(v,"request",lambda *a: pytest.fail("must not contact provider"))
    with pytest.raises(MediaError, match="public"):
        v.retrieve("abcdefghijk",tmp_path/"file",lambda *a: None)

def test_concurrent_budget_never_overallocates(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(settings(), "storage_root", str(tmp_path))
    monkeypatch.setattr(settings(), "videoscale_budget_bytes", 100)
    v.reserve_bandwidth(0)
    def reserve(_):
        try:
            v.reserve_bandwidth(60)
            return True
        except MediaError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(4))) == 1

def test_failed_download_cleans_partial_without_publishing(tmp_path, monkeypatch):
    from app import imports
    monkeypatch.setattr(settings(), "videoscale_enabled", True)
    monkeypatch.setattr(settings(), "videoscale_auth_header", "Basic test")
    monkeypatch.setattr(imports, "metadata", lambda _: dict(public_unrestricted=True, duration=20))
    responses=iter([formats(),{"task_id":"video"},{"status":"completed"},{"download_url":"video"}])
    monkeypatch.setattr(v,"request",lambda *a,**k: next(responses))
    monkeypatch.setattr(v,"reserve_bandwidth",lambda *a: None)
    def fail(url,path,*args):
        path.write_bytes(b"partial")
        raise MediaError("Download failed")
    monkeypatch.setattr(v,"download_file",fail)
    with pytest.raises(MediaError):
        v.retrieve("abcdefghijk", tmp_path/"source.mp4", lambda *a: None)
    assert not list(tmp_path.iterdir())

@pytest.mark.parametrize("status", [200, 201, 202])
def test_download_creation_accepts_async_success(status):
    import httpx
    calls=[]
    class Client:
        def request(self, method, url, **kwargs):
            calls.append(method)
            return httpx.Response(status,json={"task_id":"queued-task","status":"queued"})
    assert v.request(Client(),"/api/download",{"url":"test","format_id":"137"})["task_id"]=="queued-task"
    assert calls==["POST"]

def test_empty_task_response_is_not_success():
    import httpx
    class Client:
        def request(self,*a,**k): return httpx.Response(204)
    with pytest.raises(MediaError):
        v.request(Client(),"/api/download",{"url":"test"})

def test_storage_tries_other_validated_addresses(monkeypatch):
    calls=[]
    class Socket:
        def close(self): pass
    result=Socket()
    def connect(address, **kwargs):
        calls.append(address[0])
        if len(calls)==1: raise OSError("unreachable")
        return result
    class TLS:
        def wrap_socket(self,sock,server_hostname):
            assert server_hostname==v.STORAGE_HOST
            return sock
    monkeypatch.setattr(v.socket,"create_connection",connect)
    monkeypatch.setattr(v.ssl,"create_default_context",TLS)
    assert v.connect_storage(["2001:4860:4860::8888","8.8.8.8","1.1.1.1"]) is result
    assert calls==["8.8.8.8","1.1.1.1"]
