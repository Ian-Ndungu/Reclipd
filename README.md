# RECLIPD AI Studio

A local-first, production-oriented video clipping application: React + TypeScript + Vite + Tailwind, FastAPI, PostgreSQL/Alembic, Redis/Celery, faster-whisper, PySceneDetect, OpenCV, and FFmpeg.

This is a working development release, not a claim of audited production readiness. See [FEATURE_STATUS.md](FEATURE_STATUS.md) for implemented features, optional integrations, validation, and remaining limits.

## Start

Requirements: Docker Engine/Desktop with Compose, about 8 GB of available RAM, 5 GB of initial free disk space plus media storage, and internet access for images and the first Whisper model download.

```sh
python3 scripts/bootstrap.py
docker compose up --build -d
```

Open **http://localhost:5173** and register an account. The API is at **http://localhost:8000**, with typed OpenAPI documentation at **http://localhost:8000/docs**.

1. Create a project and upload a video you own or are authorized to use.
2. Set clip count and duration range. Confirm usage rights.
3. Watch persisted worker progress. The first transcription downloads the configured model and may take several minutes.
4. Review ranked highlights and the explanation for each score.
5. Open a clip; trim/split/remove segments, revise captions and timing, set framing, and apply a brand kit.
6. Save and export. Download the finished MP4 from Export history.

No seeded analytics, fake clips, or precomputed AI scores are shown. Empty workspaces are genuinely empty. The decorative landing/dashboard artwork is a design illustration.

```sh
docker compose logs -f worker
docker compose ps
docker compose down  # preserves named data volumes
```

The supplied Compose binds the web/API ports to loopback. It does not expose PostgreSQL or Redis to the host. Do not use `down -v` unless you intend to delete stored projects/media/database contents.

## Configuration

`bootstrap.py` copies `.env.example` and generates a random session secret without printing it. `.env` is ignored by Git. Alternatively copy `.env.example`, replace `SECRET_KEY` with at least 32 random characters, and set the database password consistently in `POSTGRES_PASSWORD` and `DATABASE_URL`.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Signs 12-hour HttpOnly session cookies. Keep server-side. |
| `DATABASE_URL` | PostgreSQL via psycopg; SQLite is used only for unit tests/local experiments. |
| `REDIS_URL` | Celery broker/results and distributed authentication rate limiting. |
| `STORAGE_ROOT` | Local storage root shared between API and workers. |
| `MAX_UPLOAD_MB`, `MAX_MEDIA_SECONDS` | Default 2048 MB and 60 minutes. Nginx allows 2049 MB including multipart overhead; align this limit when changing size. The upload UI reads limits from the API. |
| `FREE_MINUTES` | Lifetime development allowance, default 120 minutes per user. |
| `WHISPER_MODEL` | `base` by default; `tiny` is faster for smoke tests. First use downloads model files. A local model directory is also supported. |
| `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE` | Defaults to CPU/int8. GPU deployment requires an appropriate runtime/image. |
| `IMPORT_ALLOWED_HOSTS` | JSON list of exact operator-approved HTTPS hostnames for direct media files. Empty by default. |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | Optional trusted local OpenAI-compatible service; base URL typically ends in `/v1`. Never passed to the browser. |
| `SPEAKER_MODEL_PATH` | Optional provisioned local Pyannote pipeline; see below. |
| `COOKIE_SECURE`, `CORS_ORIGINS` | Set secure cookies and the exact HTTPS origins for a production deployment. |

Redis is required for registration/login; auth fails closed if the rate limiter is unavailable. Imports resolve and validate every address, pin the connection, verify TLS for the original host, disallow redirects, limit bytes/time, and reject non-public destinations. The allowlist is **operator controlled**, not user controlled. The optional YouTube public-video adapter is separate from direct imports; see its limits below. DRM bypass and browser cookie extraction are not implemented.

### Optional local models

The default ranking is deterministic and explicitly labeled. A local LLM can contribute a bounded contextual assessment and generate headline suggestions. Failed/unavailable LLM calls fall back to transcript-based templates. Template headlines are labeled as templates. LLM suggestions are labeled for editorial review; generated copy still needs human fact checking.

Real speaker diarization is optional because the model and its license/access requirements vary. Install `backend/requirements-diarization.txt` in a custom worker image, provision a compatible Pyannote pipeline and its weights locally, mount them read-only, and set `SPEAKER_MODEL_PATH`. The default image does not include Pyannote/Torch. Missing/unavailable speaker analysis is reported and excluded from scores. This adapter is not validated against a downloaded speaker model in the default test suite.

## Architecture

```text
React/Vite ── same-origin Nginx ── FastAPI ── PostgreSQL
                                      │
                                      ├── Redis / Celery ── media worker
                                      │                       ├── FFprobe / FFmpeg
                                      │                       ├── faster-whisper
                                      │                       ├── scenes / audio / faces
                                      │                       └── optional local models
                                      └── shared local storage volume
```

- `backend/app/main.py`: authenticated typed API, ownership authorization, uploads, edits, exports, brands, operations.
- `backend/app/models.py` and `backend/alembic/versions/`: durable accounts, projects, transcript/analysis, clips, export snapshots, brand kits, assets.
- `backend/app/worker.py`: atomic queue claims, processing state, quota reservation/refund, exports, and stale-job recovery.
- `backend/app/media.py`: bounded subprocess argument arrays, inspection, audio, transcription, scene/face analysis, ASS caption generation, non-destructive rendering.
- `backend/app/ranking.py`: deterministic signal ranking and pluggable language model protocol.
- `backend/app/storage.py`: storage contract with local implementation. A future S3 implementation needs staging/presigned download support; do not point `STORAGE_ROOT` at an S3 URI.
- `frontend/src/Editor.tsx`: source preview, word editing, edit timeline, styling, undo/redo, revision-aware save, export.

Edit decisions use **absolute source timestamps**. Each saved segment is rendered and concatenated in list order. Word intervals are clipped to retained segments and retimed for the output. Export requests snapshot the current saved edit decisions, so subsequent edits cannot change an in-flight render. Revision checks reject stale saves from other tabs.

### Ranking and framing

The default score is a documented heuristic, **not a probability of virality**:

- Speech coverage: 30%
- Lexical variety: 20%
- Relative audio RMS intensity: 20%
- Scene-change density: 10%
- Sentence-boundary completeness: 20%

Available diarization changes add 10% weight, reducing speech and lexical weights by 5% each. If a local LLM assesses an excerpt, its contextual score contributes 25% of that candidate’s final score and its reasoning is disclosed. Overlapping suggestions are suppressed. Short videos can yield fewer clips than requested.

Automatic reframing tracks the largest frontal face sampled every two seconds and interpolates the crop focus. Without a face it uses the manual center fallback. It is not a semantic subject tracker, nor an active-speaker detector. Use manual focus or fit mode when needed. The editor shows an approximate preview; final renders use FFmpeg/libass. Headline text is stored as metadata; it is not burned into the video.

Exports use H.264/AAC MP4 with fast-start. Output is exactly 9:16 with even dimensions; up to 1080×1920 when the available crop supports that resolution. Lower-resolution landscape sources produce smaller vertical exports rather than being silently upscaled.

### Fonts and brand assets

Workers include 19 font families across DejaVu, Liberation, Lato, GNU FreeFont, Carlito, Caladea, Inter, Poppins, Montserrat, Anton, Bebas Neue, Oswald and DM Sans, with accompanying license files. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Caption controls include family, regular/bold, size, fill/accent, stroke, shadow, placement, and highlight/fade/no animation.

Users may upload TTF/OTF fonts and raster logos after confirming rights. Fonts with restricted embedding flags are rejected; family names are constrained before use in ASS. Logos are decoded and re-encoded to PNG. Assets are size-limited, owned, and served through authenticated routes. Logos currently render at a fixed top-right placement. Custom fonts are loaded for the browser preview and made available to libass during export.

## Tests

```sh
# Full backend tests, including actual FFmpeg-generated fixture / split / caption render
# Run after building the current image.
docker compose run --rm --no-deps -e SECRET_KEY=test-secret-at-least-32-characters -e DATABASE_URL=sqlite:// -e STORAGE_ROOT=/tmp/reclipd-tests api pytest -q

# Frontend behavioral tests and production type/build checks
cd frontend
npm ci
npm test
npm run build
```

Local Python development requires Python 3.11+:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
```

Host tests skip the three FFmpeg integration checks when FFmpeg/FFprobe are absent; the Docker tests run them. Core worker lifecycle tests isolate model invocation while checking persistence, duplicate delivery, and quota refunds. Real transcription requires a model download and is an additional smoke test, not part of every unit run.

To develop the frontend against the Compose API, stop the Compose web service and run `npm run dev` in `frontend`; Vite proxies `/api` to port 8000.

## Operations and limits

Promote an existing account with the operator-only CLI:

```sh
docker compose exec api python -m app.admin your-email@example.com
# Revoke:
docker compose exec api python -m app.admin your-email@example.com --revoke
```

No default administrator password or public promotion endpoint exists. Admin operations show recent jobs and allow retries through an admin-guarded API.

One worker runs by default. Two active source projects and three active exports are allowed per user. Quota reservations lock the user row in PostgreSQL; unsuccessful work refunds the reservation. Retry does not double-charge a successful source. Celery has prefetch one, late acknowledgments, task timeouts, and atomic database claims. Beat recovers jobs stalled for two hours and removes old scratch directories, never completed user media.

Before public production use: terminate TLS; set secure cookies/origins; add account recovery and email verification; define privacy, retention/deletion, and abuse policies; add storage quotas/antivirus or sandbox scanning as appropriate; establish database/media backups; use external secrets, restricted worker networking and resource limits; instrument metrics/alerts; pin and scan release images; validate GPU/CPU capacity and representative languages/content; provision payment-provider integration only if needed. There is no payment collection in this release.

### Preview and CPU processing performance
Clip cards and the editor request cached, short H.264/AAC MP4 previews (maximum 180 seconds per range), rather than seeking repeatedly through the entire upload. The first preview takes a few seconds to encode; later requests reuse it and support byte ranges. Export still uses the original source. Previews approximate the editor's framing and captions, not a final render. Two preview encodes may run concurrently per API process; retry is available if capacity is busy.

`WHISPER_BEAM_SIZE=1` defaults to faster greedy decoding with word timestamps. Set `5` for slower beam-search decoding if transcription quality requires it. `WHISPER_CPU_THREADS=2` matches the local worker's CPU limit. Long videos still require minutes on CPU; the earlier 58-minute source took 15 minutes with beam size 5. No full-length speedup is guaranteed from a short benchmark.

### YouTube links and authorized imports
New Project defaults to **Paste Video Link**; **Upload Video** remains available. Supported references are HTTPS `youtube.com/watch?v=ID`, `youtu.be/ID`, and `youtube.com/shorts/ID` (11-character IDs). Metadata comes only from the official [YouTube Data API videos.list](https://developers.google.com/youtube/v3/docs/videos/list), using `snippet` and `contentDetails`.

Set `YOUTUBE_API_KEY` in the backend `.env` to a key for a Google project with YouTube Data API v3 enabled. Restrict the key to that API and appropriate server access. Restart API after configuration (`docker compose up -d --force-recreate api`). The key is never sent to the frontend. Missing credentials, private/deleted videos and API/quota failures are shown explicitly; they are not replaced by invented metadata.

Metadata permission is not audiovisual permission. The optional public-video yt-dlp adapter can attempt retrieval when enabled; cookie extraction, restricted-content access and DRM bypass are not implemented. If public retrieval is disabled or unavailable, supply the corresponding original file's authorized direct HTTPS URL from an operator-approved host, or choose **Upload authorized source file**. Configure exact source hosts with `IMPORT_ALLOWED_HOSTS=["media.example.com"]`; only trusted media hosts should be approved. The allowlist permits connections; the user's rights confirmation covers their intended use of that particular source. It does not prove ownership or grant YouTube access.

Preflight checks source reachability, content type and advertised size via HEAD; hosts must support HEAD and GET without redirects. Private IPs, unsafe destinations and unapproved hosts remain blocked. The background worker revalidates DNS/address safety, downloads with byte/time limits and uses FFprobe to validate the actual file. Signed URL expiry or later source errors are recoverable project errors. Import hands the resolved source to the existing Whisper/ranking/editor/export pipeline. Existing scores remain explainable editorial signals, not predictions of real-world engagement.


### Appearance and connected originals
Light is the default. Settings → Appearance offers Light, Dark and System, persisted locally and applied before React loads. The selector appears only in Settings.

YouTube references can be connected to an already uploaded, ready original belonging to the signed-in account. The New Project source panel records that association after rights confirmation; subsequent imports reuse the original through the existing worker. This is local RECLIPD storage, not a connected Google Drive or YouTube download service. `YouTubeMediaProvider` in `backend/app/imports.py` is the extension point for an approved future integration. Metadata keys do not grant footage access.

Guest link drafts survive login. New projects support clip count/duration, source language, caption presets and a clipping brief. The deterministic ranker uses keyword relevance; a configured local LLM can interpret the brief. Exports remain 9:16 and captions remain in the source language. The editor adds headline overlays, volume, stroke/background colors and letter spacing. Custom line-height and translated output are not implemented.

### Optional public YouTube retrieval (updated scope)
Set `YOUTUBE_DOWNLOAD_ENABLED=true` and rebuild API/worker to enable the pinned yt-dlp adapter. This is unofficial extraction, not an approved YouTube footage API. Explicit user rights confirmation remains required. Connected originals and explicit source URLs take priority. Preview indicates an attempt can be queued, not a successful download. The worker rejects non-public, age-restricted, live/upcoming, DRM-marked and over-duration sources, permits only direct HTTPS Google video CDN formats, and uses no cookies, account credentials, proxy rotation or geo bypass. Failed/blocked extraction offers retry or original-file upload. The existing FFmpeg/Whisper processing and quotas run after retrieval.

Downloads run in a separate process group with a configurable timeout (default 600 seconds), byte/storage limits, received-byte status updates, and temporary-file cleanup. No extraction errors containing signed media URLs are exposed. yt-dlp compatibility can change; not every public video is retrievable. The user-supplied public test video completed retrieval, transcription, highlight generation and MP4 export; see VERIFICATION.md. Existing direct-import DNS pinning remains separate from yt-dlp’s network stack.

### Better headlines
The headline workspace offers editable drafts, 3–10 options, 60/90/140-character limits, retained-transcript review, and explicit copy/overlay feedback. Generation excludes words outside retained edits. Without a model, suggestions are labeled transcript templates; these now vary source sentences and respect the length limit.

For semantic rewriting, configure the existing trusted local OpenAI-compatible service via `LLM_BASE_URL`, `LLM_MODEL`, and optional `LLM_API_KEY` in backend `.env`, then recreate API and worker. The endpoint must support `/chat/completions`; the base URL normally includes `/v1`. No model is provisioned automatically. Prompts ask for distinct, specific, modest angles with no invented outcomes. Duplicate, overlong or novel-numeric model responses fall back to templates. These checks do not prove factual accuracy: correct transcription errors, retain a self-contained clip, and review names, claims and context before publishing. Model requests send the retained transcript to the configured service.
