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
| `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET` | Optional server-only OAuth credentials for user-authorized Google Drive video imports. |
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

YouTube references can be connected to an already uploaded, ready original belonging to the signed-in account. The New Project source panel records that association after rights confirmation; subsequent imports reuse the original through the existing worker. This local-original workflow is separate from the opt-in Google Drive connector below and is not a YouTube download service. `YouTubeMediaProvider` in `backend/app/imports.py` is the extension point for an approved future integration. Metadata keys do not grant footage access.

### Google Drive source imports

RECLIPD can import a video selected from the signed-in user's Google Drive after the user authorizes the application. The app lists video files only, downloads the selected file in the background through the Google Drive API, checks the configured size limit, then sends it through the existing FFprobe, transcription, ranking, editing, and export pipeline. OAuth tokens are encrypted in the database and are never sent to the browser. Disconnecting Drive deletes the stored connection.

To enable it, create a **Web application** OAuth client in Google Cloud, enable the Google Drive API, and add this exact authorized redirect URI:

```text
https://YOUR_PUBLIC_RECLIPD_HOST/api/integrations/google-drive/callback
```

Set `APP_URL` to the same HTTPS public origin and set `GOOGLE_DRIVE_CLIENT_ID` and `GOOGLE_DRIVE_CLIENT_SECRET` only in the server `.env`; rebuild/recreate the API and worker afterward. During Google OAuth consent-screen testing, add each tester's Google account as a test user. The feature uses the read-only `drive.readonly` scope and requires the user to select media they own or are authorized to use. It is a connected-storage workflow, not a YouTube access bypass.

Guest link drafts survive login. New projects support clip count/duration, source language, caption presets and a clipping brief. The deterministic ranker uses keyword relevance; a configured local LLM can interpret the brief. Exports remain 9:16 and captions remain in the source language. The editor adds headline overlays, volume, stroke/background colors and letter spacing. Custom line-height and translated output are not implemented.

### Optional public YouTube retrieval (updated scope)
Set `YOUTUBE_DOWNLOAD_ENABLED=true` and rebuild API/worker to enable the pinned yt-dlp adapter. This is unofficial extraction, not an approved YouTube footage API. Explicit user rights confirmation remains required. Connected originals and explicit source URLs take priority. Preview indicates an attempt can be queued, not a successful download. The worker rejects non-public, age-restricted, live/upcoming, DRM-marked and over-duration sources, permits only direct HTTPS Google video CDN formats, and uses no cookies, account credentials, proxy rotation or geo bypass. Failed/blocked extraction offers retry or original-file upload. The existing FFmpeg/Whisper processing and quotas run after retrieval.

Downloads run in a separate process group with a configurable timeout (default 600 seconds), byte/storage limits, received-byte status updates, and temporary-file cleanup. No extraction errors containing signed media URLs are exposed. yt-dlp compatibility can change; not every public video is retrievable. The user-supplied public test video completed retrieval, transcription, highlight generation and MP4 export; see VERIFICATION.md. Existing direct-import DNS pinning remains separate from yt-dlp’s network stack.

### Better headlines
The headline workspace offers editable drafts, 3–10 options, 60/90/140-character limits, retained-transcript review, and explicit copy/overlay feedback. Generation excludes words outside retained edits. Without a model, suggestions are labeled transcript templates; these now vary source sentences and respect the length limit.

For semantic rewriting, configure the existing trusted local OpenAI-compatible service via `LLM_BASE_URL`, `LLM_MODEL`, and optional `LLM_API_KEY` in backend `.env`, then recreate API and worker. The endpoint must support `/chat/completions`; the base URL normally includes `/v1`. No model is provisioned automatically. Prompts ask for distinct, specific, modest angles with no invented outcomes. Duplicate, overlong or novel-numeric model responses fall back to templates. These checks do not prove factual accuracy: correct transcription errors, retain a self-contained clip, and review names, claims and context before publishing. Model requests send the retained transcript to the configured service.

## Paystack sandbox billing

The billing page supports one-time KES minute packs, hosted Paystack checkout,
owner-scoped verification and payment history. This version accepts `sk_test_`
keys only; it cannot charge real money. Test credits increase the development
allowance without changing the account's unlimited exemption.

Set `PAYSTACK_SECRET_KEY` privately in `.env`, `BILLING_PACKS` to a JSON array of
objects with `id`, `name`, positive integer `amount_kes` and `minutes`, and
`BILLING_RETURN_URL` to your frontend `/studio/billing` URL. No prices are enabled
by default. Recreate API/worker services after changing environment settings.
Never commit the secret or add it to a VITE variable.

Configure Paystack's test webhook as `https://YOUR_API_HOST/api/billing/webhook`.
It requires public HTTPS; localhost cannot receive provider webhooks. The return
page and payment-history Check payment action can verify from a local session.
Both paths recheck Paystack's transaction status, reference, amount, currency,
test domain and purchaser email. Only a confirmed success grants minutes, once.
Webhook signatures use HMAC-SHA512 of the raw body. Amounts are sent in KES subunits.

Not enabled: live charging, recurring subscriptions, automatic refunds/dispute
reconciliation, tax invoices and a live/test ledger migration. Those must be
implemented before accepting live payments. A test payment is not a tax receipt.

## Credit policy (supersedes development allowance / configurable KES packs)

- Activation is successful account registration (`users.created_at`, UTC). Eligible
  accounts receive 90 minutes until activation + 7 days, without a card.
- After that instant, Free Forever grants 60 minutes for each monthly anniversary
  of trial expiry. Month-end dates clamp to that month's last day (Jan 31 → Feb 28
  → Mar 31). Expired/missed periods never accumulate. Grants are materialized on
  the next usage/admission/reservation request, so no scheduler delay affects eligibility.
- Fixed advertised USD packs: Starter $10/100 min; Creator $20/250 min, with 50 extra
  minutes on each of the first two successful Creator purchases; Pro $40/600 min;
  Studio $80/1500 min. Purchase grants expire exactly 365 days from provider payment time.
- Checkout is hard-disabled until merchant currency capability and end-to-end payment
  integration have been verified. BILLING_PACKS and FREE_MINUTES no longer determine
  the new credit policy. Existing pending KES payments retain their original currency.
- Account row locks serialize grants and spending; stable grant keys prevent duplicate
  trial/monthly/payment allocations. Reservations are keyed by project and charge source
  duration rounded up to a millisecond. Order: trial, free, paid by nearest expiry.
  Refunds restore original grants without changing their expiry. Paid ledger entries
  and processing history survive project deletion. Unlimited account exemptions persist.
- Existing accounts retain their original activation date. On first ledger access,
  historical tracked usage is deducted once from the current free/trial bucket and then
  legacy successful purchases. Future monthly allocations start fresh. Existing test
  purchases remain test credits; this is not a live-payment migration.
- Anti-abuse: normalized unique account emails, hashed canonical Gmail/Googlemail
  identities (dots/+aliases), one identity entitlement, existing authentication rate
  limits and 10 signup attempts per observed network per UTC day, failing closed if
  Redis is unavailable. Reverse-proxy client IP handling must be configured for a
  public deployment; behind an untrusted proxy the limit is shared by proxy traffic.
  Email ownership verification, disposable-address detection, and person-level identity
  checks are not implemented; these controls do not claim to prevent all multi-account abuse.

### Editorial briefs and picture adjustments
Clipping instructions now prioritize literal transcript topic coverage (60% of heuristic score), support explicit `01:00–05:00` source ranges, and exclude topics with `Avoid sponsorships.` Keep exclusion sentences separate from positive requests. Without a configured LLM, this is lexical matching, not general natural-language understanding. The optional LLM receives full candidate transcripts for instruction-aware reranking. Impossible constraints produce recoverable errors. Clip count, duration, captions and language remain controlled by structured settings.

The editor's Frame panel includes brightness, contrast, saturation, Natural/Vivid/Soft/Black & white presets, horizontal mirroring and mute. Picture edits are saved non-destructively, support existing undo/redo, and apply to every cut during FFmpeg export before captions and logos. Browser color previews approximate FFmpeg output. Multi-track overlays, transitions, keyframes, music uploads and speed ramps are not implemented.

Speed & fades: the editor Frame panel supports global 0.25×–4× playback/export speed with pitch-preserving audio. Captions are burned before time scaling so their timing follows the footage. Transport displays finished playback time while trimming/splitting uses source timestamps. Fade in/out (0–2 seconds each, capped at half the output duration) apply to video, overlays and audio during export; browser preview does not yet simulate fades. These controls use existing save and undo/redo.

### Manual editing and shared credits
Before upload, choose AI Clips or Manual Editor. Manual Editor uploads an authorized file and creates a ready-to-edit clip after FFprobe inspection, without transcription or AI ranking and without charging source minutes. The first selection contains up to 180 seconds; trim controls can select other parts of the original. Automatic captions are not generated; use Add caption at playhead and edit its text/timing.

Both workflows share the existing trial, monthly free and prepaid balance. AI jobs still charge source duration. Manual exports reserve finished duration (selected seconds divided by playback speed), rounded up to the millisecond. Preview/edit time is free. Identical queued, processing or completed exports with retained files are reused without a second charge; changed edits create a new charge. Queue failures, rendering failures and stale jobs refund the original grant allocations. Downloads do not charge. Existing unlimited accounts remain exempt. The export button fetches the cost before enabling export. Credit history labels manual reservations as Manual export.

This is a single-source vertical editor, not full CapCut parity: multi-track compositing and automated manual-project transcription remain unavailable. Existing 180-second selected-source export and preview limits still apply (speed can change the final duration).


Between-cut transitions: Crossfade, Dissolve, Slide left/right, and Wipe left/right apply to every adjacent cut at export, with audio crossfades. Transition length (0.1–1 seconds) is capped at half the shortest cut. Caption offsets and manual-export credits subtract overlap before applying playback speed. Browser editing previews currently show hard cuts; render an export to view transitions. This is a global transition, not independently configured per boundary.

### Automatic face tracking
Auto reframing samples at 4 Hz from the exact trim start, with frontal and mirrored profile Haar detections at 640px width and local contrast normalization. Geometry-based association keeps the same nearby subject instead of always selecting the largest face. A dead zone and time-based smoothing reduce jitter; brief missed detections hold the previous subject before reacquisition or gradual fallback. Large scene changes reset association. Paths are simplified to at most 256 points and compiled as balanced FFmpeg expressions to avoid parser depth failures.

This is not face recognition or active-speaker detection. Haar detection can still miss tiny, occluded, strongly angled or poorly lit faces; geometry association can switch between overlapping people. The editor preview is approximate, and exports apply the tracking. Manual crop and Fit entire frame remain available. Automated tests check tracking continuity and crop rendering; no representative real-footage accuracy percentage has been established.

### Caption studio, brand library, and settings
Caption Studio supports searching by style/font, filtering background or animated presets, custom preview text, and carrying a chosen preset into the next AI project. Previews approximate export typography; animations require timed captions in the actual clip.

Brand Library supports creating and editing owned kits, all built-in fonts, size/color/placement controls, export resolution, logo/custom-font selections and a live typography preview. Asset uploads refresh the selectors. Deletion requires an inline confirmation; existing clips retain their saved edits when a kit changes or is deleted. PUT /api/brands/{id} enforces ownership and asset access validation.

Settings saves account-scoped, browser-local defaults for caption presets and export resolution. New projects copy the defaults; existing projects and explicit drafts are unchanged. Manual projects continue to start with captions off. These preferences do not sync across devices. Theme selection remains in Settings.

### RECLIPD export watermark
New exports include a white vector scissors icon that accelerates across the top-left safe area with dissipating smoke, revealing the RECLIPD wordmark before settling. Clips over 15 seconds replay this two-second sequence once at the midpoint, applied after captions, logos and fades. Trial and Free Forever accounts cannot disable it; the API enforces this independently of the editor checkbox. A verified successful prepaid purchase unlocks removal for 365 days from payment (independent of remaining minutes); configured unlimited accounts also qualify. Paid users can untick **Include RECLIPD watermark** in the editor before exporting. Existing downloaded files are unchanged; legacy exports without a recorded watermark are not reused for a newly watermarked export.

### Export clarity
Exports use H.264 CRF 17 with the medium encoder preset, Lanczos video resizing, and 192 kbps AAC when audio is encoded. This prioritizes detail over file size and rendering speed. Browser previews remain lightweight. Export resolution remains source-limited, up to 1080×1920 for suitable footage; landscape crops may be smaller. New export requests use the updated render version instead of reusing older outputs.

### Account settings and password recovery
- Settings now supports password changes, synced caption/resolution/theme preferences, and password-confirmed account deletion.
- Preferences are stored on the account and loaded on sign-in/page reload. Existing browser defaults are migrated on first use when the account has no preferences.
- Password changes and resets revoke other sessions. Reset links are random, hashed in the database, valid for 30 minutes and single-use; reset secrets are in URL fragments, not server request logs.
- Deletion removes projects, clips, assets, preferences and credit history; active processing/exports must finish or be cancelled first. The account becomes an inaccessible anonymous tombstone to retain payment reconciliation records and prevent repeat free trials. Physical file failures are retried by cleanup. Old preview caches expire after seven days; backups have their own retention.
- Recovery email requires SMTP. For local Gmail development, enable Google 2-Step Verification and create an App Password, then run:
  `python3 scripts/configure_gmail.py`
  The hidden prompt writes only to ignored local `.env`. Never use the normal Google password.
- Restart the API with `docker compose up -d --force-recreate api`, then use **Forgot password?** on the login page to test delivery. Without SMTP configuration the app explicitly reports recovery unavailable.
- Development links use `APP_URL=http://localhost:5173` and work on the computer hosting the app. Set the public HTTPS origin for deployment. Gmail can support a small production launch, subject to Google sending limits and account restrictions; a verified transactional sender is recommended for reliability at scale.
- PayPal is not integrated/enabled by these account changes. Existing paid checkout remains disabled pending verified payment integration.

### PayPal sandbox setup (Personal account → Business checkout)
PayPal website checkout needs a Business merchant account. Upgrade the existing Personal account through PayPal's account settings if offered, or create a separate Kenyan Business account. Complete PayPal's verification using accurate business details. A sandbox Business seller and sandbox Personal buyer let you test without moving real money.

1. Sign in at https://developer.paypal.com/dashboard/ and select Sandbox.
2. Create a REST app under Apps & Credentials for the sandbox Business seller.
3. Get the sandbox Client ID, Secret and seller Merchant ID. Run `python3 scripts/configure_paypal.py` to save credentials privately in ignored `.env`.
4. Restart the API: `docker compose up -d --force-recreate api`.
5. Use a regular RECLIPD test account (not an unlimited account), open Billing, choose a package and approve with the separate sandbox buyer.
6. For asynchronous verification, configure the app's webhook at your public HTTPS endpoint `/api/billing/paypal/webhook`, subscribe to PAYMENT.CAPTURE.COMPLETED, PAYMENT.CAPTURE.REFUNDED and PAYMENT.CAPTURE.REVERSED, and save its ID as PAYPAL_WEBHOOK_ID. Localhost cannot receive PayPal webhooks; the return flow and Check payment action can verify local tests.

Implementation uses server-owned USD prices, PayPal Orders v2 create/capture, stable request IDs, owned payment references, merchant/amount/currency/capture validation, and signature verification through PayPal. Duplicate capture callbacks/webhooks do not grant additional credits. Refund/reversal events revoke the package's unspent credits (conservatively, the whole remaining package even for partial refunds); already-consumed work is not made negative. Paystack records remain available. Test credits use the existing local ledger and must not be treated as real-money purchases.

Live API endpoints are deliberately unavailable in this implementation. Before enabling real payments: complete Business account eligibility, run real sandbox success/cancellation/decline/retry/webhook/refund tests, use a public HTTPS deployment, and establish refund/dispute operations. No external sandbox payment has been verified until credentials are configured.

### First production launch with Gmail
Account deletion, password change/recovery and synced preferences are not development-only features; they are included in the production build. Apply all database migrations when deploying.
Set APP_URL to the public HTTPS frontend origin, COOKIE_SECURE=true and CORS_ORIGINS to that origin on the server. Configure SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, SMTP_USERNAME, SMTP_FROM and SMTP_PASSWORD using a Google App Password. Keep credentials in server environment variables.
Gmail is acceptable for an initial small launch subject to its sending limits; the application does not prohibit production Gmail. The local configure_gmail.py helper sets APP_URL to localhost, so set the public URL separately in production. Recovery cannot send until credentials are configured.

### Experimental Micro test profile

`docker compose -f compose.yaml -f compose.micro.yaml up -d --build` enables
low-memory operation. This is **not a production certification for 1 GB servers**.
Use a host with configured swap; the worker allows up to 3 GB RAM+swap, but other
services and the OS also need memory. Keep exactly one worker replica. Model,
beam size, output resolution and encoding quality are unchanged. Heavy jobs and
uncached previews share a filesystem lock on the media volume; busy previews
return a retryable error. Worker children are replaced after each task, Whisper
is released after transcription, and FFmpeg/BLAS thread counts are limited.
Cached previews and existing exports remain reusable; no new cross-project
transcription cache has been implemented. Existing duration/time limits remain.

Before public use, test a short authorized upload, transcription, editing,
export, download, concurrent submissions, failure refunds, and recovery on the
actual server. Measure peak memory, swap use, disk space and job duration.
Do not enable live checkout for this experiment. Public HTTPS, secure cookies,
strong server-specific secrets, firewall configuration and backups still need
setup. This overlay does not expose the localhost-only web/API ports publicly.

### Single-server HTTPS test deployment

The optional `compose.public.yaml` adds Caddy on ports 80/443, with certificates
and state in named volumes. Set `PUBLIC_HOST` in the server-only `.env`, plus
matching HTTPS `APP_URL`, `BILLING_RETURN_URL`, `CORS_ORIGINS`, and
`COOKIE_SECURE=true`. Generate new server session/database secrets. Do not copy
local user databases or credentials by default. Open TCP 80/443 in the cloud
security list and host firewall, retaining SSH access. Database and Redis have
no public ports; web/API direct ports stay loopback-only.

Use all three files consistently:
`docker compose -f compose.yaml -f compose.micro.yaml -f compose.public.yaml up -d --build`.
Keep checkout disabled during performance testing. A free IP-based hostname
can support a temporary trial but depends on the DNS provider and stable IP.
The overlay does not itself configure backups or guarantee Micro performance.

When transferring source from macOS, use `COPYFILE_DISABLE=1 tar ...` and
exclude `._*` files. These AppleDouble metadata files are not Python source;
if included beside Alembic migrations they can prevent API startup. Both Docker
build contexts also exclude these sidecars and `.DS_Store`.

### Optional VideoScale cloud retrieval
Run `python3 scripts/configure_videoscale.py` to save Basic Auth privately. Enable
`VIDEOSCALE_ENABLED=true` only on the worker/API deployment after configuring
`VIDEOSCALE_BUDGET_BYTES` within your remaining provider allowance. The default is
zero (fail closed). No automatic purchases, top-ups, or budget resets are performed.
Provider billing must also have auto-top-up disabled in its dashboard; the local
budget cannot observe other applications using the same account.

The adapter checks public/unrestricted metadata using the YouTube API, selects
H.264 video up to 1080p plus AAC audio, and merges without re-encoding. It rejects
oversized imports instead of silently lowering resolution. Downloads are bounded
by `VIDEOSCALE_MAX_IMPORT_MB` (512 by default), duration limits, and timeouts.
The persistent `.videoscale-budget.sqlite` in media storage reserves 125% of the
provider's estimated file sizes before tasks start, including failed attempts.
Preserve this file across deployments. It is a conservative app allowance, not a
live provider balance. A timed-out provider task may finish remotely; retries
reserve additional allowance. The adapter never forwards Basic Auth to storage.

Current verified storage destination is `s3.fr-par.scw.cloud` over HTTPS. A provider
host change fails closed and requires review. Uploads and connected originals
continue through their existing workflow. VideoScale is a third-party retrieval
service; configuration does not establish ownership or authorization for footage.
