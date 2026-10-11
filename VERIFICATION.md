# Verification — 10 October 2026

## Automated checks

| Check | Result |
| --- | --- |
| Docker backend suite | **29 passed**, no skipped tests |
| Frontend Vitest suite | **5 passed** across 2 files |
| TypeScript + Vite production build | **Passed** |
| Docker images | API, worker, scheduler and web built successfully |
| Database migrations | PostgreSQL reached `114d1757a67f (head)` |
| Frontend dependency audit | **0 vulnerabilities** after updating Vitest |
| Compose services | PostgreSQL, Redis, API, worker, scheduler and web running; configured health checks passing |

The backend suite covers authentication cookies/logout, ownership isolation, CSRF checks, pre-parser upload authentication, media/asset policy, private-destination URL rejection, storage containment, stale editing revisions, invalid/non-finite editing inputs, explainable ranking, transcript-based headline fallback, word retiming, ASS escaping, duplicate job delivery, quota reservation/refunds, font allowlisting, and real FFmpeg integration.

The real render tests generate their own fixtures, inspect actual media, trim/split/concatenate it, burn captions, verify vertical dimensions and duration, reject invalid media, and exercise automatic framing, a custom font, and a logo overlay.

The test runner emits a Starlette warning about its legacy HTTPX test-client integration; it does not fail tests. Vite notes that `/api/fonts/...` font resources resolve at runtime, as designed. These resources are served by authenticated API routes in the Docker image.

## Real-model and full-stack smoke tests

No user media was used. `scripts/media_smoke.py` generated an English speech fixture using FFmpeg's speech generator and synthetic video.

- Source: **17.775 seconds**, 640×360.
- Whisper: **base**, CPU/int8, **52 timed words**, English detected/configured.
- Live HTTP registration and authenticated session: passed.
- Real upload persisted to the media volume: passed.
- Redis/Celery processing progressed from queued through transcription to ready: passed.
- PostgreSQL persisted **2 ranked highlights** with the transcript and score explanations.
- A clip was split, a middle interval removed, caption settings changed, and edits saved through the API.
- Headline endpoint returned the requested **3 labeled suggestions**.
- An export was queued, rendered, listed, and downloaded through the authenticated API.
- Downloaded MP4: **507,551 bytes**, H.264 video with audio, **198×352** (exactly 9:16), **9.899675 seconds**.
- The small output is intentional: the source was only 640×360 and the renderer avoids upscaling the vertical crop. Frame/AAC timing accounts for the small difference from ideal cut duration.
- Development quota charge: **17.775 seconds**, exactly the source duration, unaffected by editing/export.

The local data volume contains the explicitly labeled synthetic QA project and rendered export from this run. No built-in demo account or password is shipped in application source.

To repeat these optional smoke tests after starting the stack:

```sh
docker compose run --rm --no-deps -v "$PWD/scripts:/scripts:ro" api python /scripts/media_smoke.py
docker compose run --rm --no-deps -v "$PWD/scripts:/scripts:ro" api python /scripts/e2e_smoke.py
```

These create a new synthetic QA account/project and store temporary QA credentials with mode 0600 under `/data/qa-fixtures/session.json` for optional browser verification. Delete that temporary file after use. Ordinary application registration does not create such a file.

## Browser verification

Checked the built application in the in-app browser:

- Marketing and authentication layouts.
- Successful sign-in to the synthetic QA account.
- Dashboard showing the real project and metered usage.
- Two real highlight results and missing-diarization disclosure.
- Clip editor loading persisted split/caption decisions and the source video.
- Caption preset changes, undo, redo, and save returning a visible **Saved** state.
- Removing the active playing cut pauses playback safely; undo restores the timeline.
- Bundled font serving fixes browser font substitution.
- Export history displays the completed MP4 and download link.
- Responsive editor/dashboard and working menu at **390×844**.
- Sidebar scrolling keeps account controls reachable on short screens; hidden mobile navigation is removed from the accessibility tree.

## Boundaries

Not validated: a user-provisioned local LLM service, a Pyannote speaker model, GPU inference, third-party allowlisted import hosts, arbitrary real-world codecs/content/languages, high-concurrency capacity, or public production security/compliance. No paid billing or S3 backend is configured. These are documented explicitly in `FEATURE_STATUS.md` and `README.md`.

## Playback repair — October 10, 2026
- Added short MP4 preview caching, authenticated ownership checks, range validation, concurrency bounds, and byte-range serving; editor maps preview time to source timestamps and advances between retained cuts.
- Added result-card playback controls and preview retry behavior. Disabled Nginx response buffering for media.
- Switched configurable CPU transcription default from beam 5 to beam 1; preserved word timestamps and the base model.
- 31 backend tests pass in Docker, including a real FFV1 MKV → H.264 fast-start MP4 test and preview cache/range/authorization checks.
- 6 frontend tests pass, including split-preview playback and timestamp mapping; production build passes.
- A 30-second excerpt of the affected source encoded to a browser preview in 3.47 seconds. This verifies generation, not a browser playback observation.
- Warm-model 60-second sample comparison: beam 5 / two threads = 7.24 seconds; beam 1 / two threads = 7.23 seconds. These results do not demonstrate a meaningful decoding-mode speedup. First-use model loading adds overhead.

## YouTube reference and authorized URL import — October 10, 2026
- Docker backend suite: **44 passed**. Frontend: **8 passed**. TypeScript/Vite production build succeeded.
- Tests cover all three YouTube formats, invalid IDs/URLs/credentials/ports, fixed official metadata endpoint, missing-key handling, metadata without footage access, approved source resolution, queue handoff, HEAD/GET media checks, private/unapproved destinations, and UI readiness invalidation.
- Authorized source success tests use controlled HTTP responses and DNS fixtures; no fabricated source or metadata is used in the application itself. No live external approved source was available for a full network import check.
- Running app: all three YouTube reference formats recognized; metadata-only import returned 422; private direct URL was unavailable.
- Real live upload regression: 17.775-second synthetic speech fixture → 52 transcript words → two clips → split/caption save → MP4 export (507,551 bytes); usage charged once. Project `606b1ec8-88b0-445e-9ec8-e641f790d4af`. Temporary QA credentials removed.
- Live Google metadata retrieval remains unverified without `YOUTUBE_API_KEY`; the UI explicitly reports the missing configuration. No YouTube audiovisual access is configured or implied.

## Expanded fonts and caption presets — October 10, 2026
- Increased the library to 12 built-in families / 24 regular and bold font files and 20 caption presets. Custom font uploads remain available.
- Frontend: 8 tests passed, including selecting the Editorial preset and all 12 font options; TypeScript/Vite production build passed.
- Added a Docker regression that authenticates and fetches every built-in font, checks the font's embedded family name against the API schema, renders a caption through FFmpeg, and checks that the selected PostScript font matches the actual bundled face.
- Existing uploads, local processing, and editor remain the RECLIPD implementation. No OpusClip processing dependency was added. The separate YouTube source-access limitation is unchanged.
- Final Docker backend suite: **45 passed**, including all 24 FFmpeg font-selection checks.

## Premium UI and connected originals — October 11, 2026
- Final backend suite: 47 passed including the enhanced rendering test; frontend 11 passed and production build passed.
- Live synthetic upload produced 52 timed words, two clips and a 506,783-byte MP4 with headline overlay, Inter captions, background/spacing and adjusted audio. Usage charged 17.775 seconds once.
- Connecting that original to a synthetic YouTube reference, previewing, importing and processing through the worker succeeded without fetching YouTube footage.
- Browser checks: light landing/dashboard, light and dark caption gallery, and dark New Project at 390px with no settled horizontal overflow. Remaining page-by-page visual review was interrupted by tool approval usage limits; it is not claimed complete.

- Settings-only appearance change deployed. The supplied YouTube credential was stored in ignored, mode-0600 `.env` and loaded by the backend. Live official metadata request returned HTTP 403 / API_KEY_SERVICE_BLOCKED; Google key restrictions require operator correction. No credential is included in this record or the frontend.

## Optional public YouTube importer — October 11, 2026
- Implemented pinned yt-dlp 2026.8.19 with bundled Node 22 runtime; enabled locally after the user revised the import scope.
- Backend: 53 tests passed, covering public/restricted metadata policy, source format filtering, rights confirmation, canonical queue handoff, subprocess timeout/cleanup and existing processing regressions.
- Frontend: 11 tests passed; TypeScript/Vite build passed. Docker API/worker/beat/web rebuilt and started successfully.
- Live test source supplied by the user: `plN7JMbadRg`, duration 3,479 seconds. Official metadata, public-provider preview, queue handoff and actual footage transfer succeeded; final processing/export result recorded below when complete.
- Browser verification could not start because the in-app browser control timed out; no new visual QA is claimed.

- Live end-to-end test PASSED: source `plN7JMbadRg` → 849,194,658-byte 1920×1080 source → 10,248 timed transcript words → one ranked clip → 2,838,540-byte H.264 MP4 with audio. Export probe: 14.599675 seconds, 594×1056 (9:16). Test export copied to ignored `qa-artifacts/youtube-test-clip.mp4`.
- Combined audio/video received-byte counter fixed; all six focused importer tests passed after the fix. Full suite before this display fix: 53 backend and 11 frontend tests passed; production build passed.

## Clip player synchronization repair — October 11, 2026
- Editor transport and scrubber now use the edited clip's elapsed time and total retained duration, rather than the full source duration. Original timestamps remain available in cut/trim controls.
- Cross-cut seeking retains the pending target during media loading; previews remount when their source range changes, replay starts from the first cut, and animation-frame updates keep the playhead/captions aligned with video time.
- Expanded editor regression covers clip-relative progress, seek across a removed interval, loading-event seek preservation, replay and automatic cut advancement. All 11 frontend tests and the production build pass.
- Real preview API check on the live YouTube test clip: HTTP 200; H.264 with audio, 640×360, 14.580867 seconds. Byte-range seek returned HTTP 206 and exactly 256 requested bytes.
- In-app browser control timed out, so manual visual playback was not verified this turn.

## Progress bar and split follow-up — October 11, 2026
- Frame-strip clicks now seek to the clicked position within each cut instead of always seeking its start. Added a moving playhead overlay and elapsed fill on the clip progress bar.
- Splitting reads the video clock and preserves the selected source position. Timeline changes and undo/redo preserve retained positions instead of unconditionally returning to cut one. Splits at cut boundaries are disabled with an explanatory tooltip.
- Expanded editor integration test checks frame-strip coordinate seeking, moving marker position, splitting at the latest media time, retained progress and undo/redo. All 11 frontend tests pass; production build passes.
- Browser control still times out; these are automated interaction checks, not a claimed manual browser playback verification.

## Headline workspace — October 11, 2026
- Added responsive editable suggestion cards, source/direction controls, suggestion count and length preferences, copy/apply status, and retained transcript review.
- Improved template sentence selection and bounded length; strengthened optional LLM instructions and rejection of duplicates, overlong text and numbers absent from the source.
- Headline API excludes trimmed-out words and returns an actionable error for clips without retained speech.
- 56 backend tests, 12 frontend tests, and production build passed. Tests cover retained-source filtering, invalid model response fallback, length/angle behavior, edited draft overlay application and request preferences.
- No LLM service is currently configured; live semantic generation is not claimed. Manual visual UI review remains unverified due to the browser connection issue.

### Upload response fix — 2026-10-11
- Confirmed Nginx rejected a 1,248,281,977-byte multipart upload with HTTP 413; the client masked the HTML error as an unreadable response.
- Increased backend/local upload limit to 2048 MB and proxy limit to 2049 MB for multipart overhead. UI reads server limits and checks file size before sending media; proxy 413 responses are JSON and client handles non-JSON errors safely.
- Passed 56 backend tests, 19 frontend tests and production build. Verified deployed limit and authenticated synthetic MP4 upload through the web proxy (201 JSON project). The user's original large file was not available for replay.

### Project deletion — 2026-10-11
- Added confirmed deletion on the project page and an owner-authorized DELETE endpoint. Active processing/exports block deletion; clips, exports and source connections are removed in dependency order. Shared originals are retained, and used processing quota is not refunded. Disposable preview cache expires through existing cleanup.
- Passed the deletion backend test (ownership, busy states, dependent rows, shared media, repeated deletion), 20 frontend tests, and production build locally.
- Deployment blocked: Docker image build failed with read-only filesystem / snapshot I/O errors. Host reports less than 1 GB free. Free disk space and restore Docker before rebuilding API/web and deploying. No user projects were deleted during testing.
- Full local backend run: 51 passed, 5 skipped, 1 failed because this host virtualenv lacks yt-dlp; the focused deletion test passes. Docker suite could not run due to the storage failure.
