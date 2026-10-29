"""Synthetic upload/export smoke test, run inside the API container.
No existing user data is accessed. Leaves a labelled QA project for diagnosis.
"""
import json,secrets,time
from pathlib import Path
import httpx
from app.media import probe
base="http://api:8000"
with httpx.Client(base_url=base,timeout=120) as client:
    r=client.post("/api/auth/register",json={"name":"Micro deployment test","email":"micro-"+secrets.token_hex(8)+"@example.test","password":secrets.token_urlsafe(32)})
    r.raise_for_status()
    # Internal HTTP smoke test only; public secure cookies remain enabled.
    for cookie in client.cookies.jar:
        cookie.secure=False
    start=time.monotonic()
    with Path("/data/qa-micro.mp4").open("rb") as f:
        r=client.post("/api/projects/upload",data={"name":"Micro QA synthetic speech","rights_confirmed":"true","config":json.dumps({"clip_count":1,"min_duration":5,"max_duration":15})},files={"file":("qa.mp4",f,"video/mp4")})
    r.raise_for_status()
    project_id=r.json()["id"]
    deadline=time.monotonic()+3500
    last=None
    while time.monotonic()<deadline:
        r=client.get("/api/projects/"+project_id);r.raise_for_status();project=r.json()
        state=(project["status"],project["progress"])
        if state!=last:print(json.dumps({"stage":project["stage"],"progress":state[1]}),flush=True);last=state
        if state[0]=="failed":raise RuntimeError(project.get("error"))
        if state[0]=="ready":break
        time.sleep(5)
    else:raise TimeoutError("Processing deadline reached")
    assert project["transcript"] and project["clips"],"Speech or clips missing"
    print(json.dumps({"processing_seconds":round(time.monotonic()-start),"words":len(project["transcript"])}),flush=True)
    clip=project["clips"][0]
    start=time.monotonic()
    r=client.post("/api/clips/"+clip["id"]+"/exports");r.raise_for_status();eid=r.json()["id"]
    deadline=time.monotonic()+1750
    while time.monotonic()<deadline:
        r=client.get("/api/exports");r.raise_for_status()
        export=next(item for item in r.json() if item["id"]==eid)
        if export["status"]=="failed":raise RuntimeError(export.get("error"))
        if export["status"]=="complete":break
        time.sleep(5)
    else:raise TimeoutError("Export deadline reached")
    r=client.get("/api/exports/"+eid+"/download");r.raise_for_status()
    output=Path("/data/qa-micro-export.mp4");output.write_bytes(r.content)
    info=probe(output)
    print(json.dumps({"result":"PASS","export_seconds":round(time.monotonic()-start),"bytes":len(r.content),"media":info}),flush=True)
