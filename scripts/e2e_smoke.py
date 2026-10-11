"""Run in API container against running API/worker to exercise real services.
Creates an explicitly labeled local QA account/project using generated media.
"""

import json
import secrets
import time
from pathlib import Path
import httpx

base = "http://api:8000"
credentials = {
    "email": f"qa-{secrets.token_hex(4)}@example.test",
    "name": "QA Creator",
    "password": secrets.token_urlsafe(24),
}
with httpx.Client(base_url=base, timeout=60) as client:
    response = client.post("/api/auth/register", json=credentials)
    response.raise_for_status()
    print("PASS register and secure-cookie session", flush=True)
    source = Path("/data/qa-fixtures/reclipd-synthetic.mp4")
    with source.open("rb") as file:
        response = client.post(
            "/api/projects/upload",
            data={
                "name": "QA · synthetic speech workflow",
                "rights_confirmed": "true",
                "config": json.dumps(
                    {"clip_count": 2, "min_duration": 5, "max_duration": 12}
                ),
            },
            files={"file": ("qa-demo.mp4", file, "video/mp4")},
        )
    response.raise_for_status()
    project_id = response.json()["id"]
    deadline = time.monotonic() + 600
    last = None
    while time.monotonic() < deadline:
        response = client.get("/api/projects/" + project_id)
        response.raise_for_status()
        p = response.json()
        if (p["status"], p["progress"]) != last:
            print(
                json.dumps(
                    {
                        "project": p["status"],
                        "progress": p["progress"],
                        "stage": p["stage"],
                    }
                ),
                flush=True,
            )
            last = (p["status"], p["progress"])
        if p["status"] == "failed":
            raise RuntimeError(p["error"])
        if p["status"] == "ready":
            break
        time.sleep(2)
    else:
        raise TimeoutError("Project did not finish")
    assert p["transcript"] and p["clips"]
    clip = p["clips"][0]
    edits = clip["edits"]
    segment = edits["segments"][0]
    midpoint = (segment["start"] + segment["end"]) / 2
    edits["segments"] = [
        {"start": segment["start"], "end": midpoint - 0.2},
        {"start": midpoint + 0.2, "end": segment["end"]},
    ]
    edits["captions"]["preset"] = "neon"
    edits["captions"]["emphasis_color"] = "#75B5FF"
    edits["captions"].update(font="Inter", background=True, background_color="#152030", letter_spacing=2, stroke_color="#112233")
    edits.update(show_headline=True, headline="Synthetic workflow verification", volume=0.5)
    response = client.put(
        "/api/clips/" + clip["id"], json={"revision": clip["revision"], "edits": edits}
    )
    response.raise_for_status()
    print("PASS save non-destructive split and caption edits", flush=True)
    response = client.post(
        "/api/clips/" + clip["id"] + "/headlines",
        json={"tone": "informative", "count": 3},
    )
    response.raise_for_status()
    assert len(response.json()) == 3
    response = client.post("/api/clips/" + clip["id"] + "/exports")
    response.raise_for_status()
    export_id = response.json()["id"]
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        response = client.get("/api/exports")
        response.raise_for_status()
        export = next(e for e in response.json() if e["id"] == export_id)
        if export["status"] == "failed":
            raise RuntimeError(export["error"])
        if export["status"] == "complete":
            break
        time.sleep(2)
    else:
        raise TimeoutError("Export did not finish")
    response = client.get("/api/exports/" + export_id + "/download")
    response.raise_for_status()
    assert len(response.content) > 1000
    result = Path("/data/qa-fixtures/e2e-export.mp4")
    result.write_bytes(response.content)
    usage = client.get("/api/usage").json()
    assert abs(usage["used_seconds"] - p["media"]["duration"]) < 0.1
    print(
        json.dumps(
            {
                "result": "PASS",
                "project_id": project_id,
                "clips": len(p["clips"]),
                "words": len(p["transcript"]),
                "export_id": export_id,
                "export_bytes": len(response.content),
                "charged_seconds": usage["used_seconds"],
            }
        ),
        flush=True,
    )
    # Connect this synthetic original to a syntactically valid reference; no YouTube footage is fetched.
    reference = "https://youtu.be/QAfixture01"
    response = client.put("/api/imports/connection", json={"url": reference, "project_id": project_id, "rights_confirmed": True})
    response.raise_for_status()
    preview = client.post("/api/imports/preview", json={"url": reference})
    preview.raise_for_status()
    assert preview.json()["available"] and preview.json()["provider"] == "connected-original"
    imported = client.post("/api/projects/import", json={"name": "QA · connected original", "url": reference, "rights_confirmed": True, "config": {"clip_count": 1, "min_duration": 5, "max_duration": 12}})
    imported.raise_for_status()
    imported_id = imported.json()["id"]
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        result = client.get("/api/projects/" + imported_id)
        result.raise_for_status()
        connected = result.json()
        if connected["status"] == "failed":
            raise RuntimeError(connected["error"])
        if connected["status"] == "ready":
            break
        time.sleep(2)
    else:
        raise TimeoutError("Connected original did not finish")
    assert connected["clips"] and connected["transcript"]
    print("PASS connected original → URL preview → import → real transcription and clips", flush=True)
