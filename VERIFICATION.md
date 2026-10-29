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

### Processing controls and billing — 2026-10-12
- Added cooperative cancellation endpoint and worker checkpoints, reserved-quota refunds, queued cancellation and retry. Processing jobs display a live stage indicator and Cancel clipping; terminal states offer deletion. Cancellation waits for the next worker checkpoint; it is not an immediate process kill.
- Added All projects navigation on project detail. Billing now shows actual plan allowance, remaining minutes, refreshable usage, unlimited accounts, accounting rules and explicit absence of payment-provider/invoice integration.
- Passed 23 frontend tests, targeted cancellation (including worker refund/source preservation), deletion and unlimited-quota tests, and Docker production builds.

### Paystack sandbox — 2026-10-12
- Added migration-managed payment ledger, configured KES packs, hosted checkout, authenticated transaction verification, HMAC-SHA512 webhook validation and idempotent processing credits. Only test keys and verified test-domain payments are accepted.
- Billing UI includes disabled-until-configured packages, return-page verification and payment history. Unlimited accounts cannot buy unnecessary credits.
- Passed 65 backend tests, 23 frontend tests and production Docker builds. No actual Paystack sandbox transaction has been exercised: merchant test key and package prices are not configured. Live payments, subscriptions, refunds/disputes and invoices remain unsupported.

### Expiring credits and USD catalog — 2026-10-12
- Deployed 90-minute seven-day signup trial; 60-minute monthly Free Forever thereafter; no free rollover; fixed USD catalog and 365-day paid expiry; first two successful Creator purchases receive 50-minute bonuses each. Checkout remains hard-disabled.
- Added persistent grant and reservation ledgers, account serialization, duplicate grant keys, trial→free→paid expiry-order consumption, original-bucket refunds, usage history and countdown/balance displays. Existing accounts retain signup date and one-time historical usage deductions; Unlimited is preserved.
- Signup controls: existing authentication throttling, canonical Gmail identity uniqueness and daily observed-network attempt limit. Email ownership verification is not implemented; broader multi-account fraud prevention remains a production limitation.
- Passed 72 backend tests, 24 frontend tests and production builds. Live PostgreSQL concurrency test passed overspend protection, exactly two Creator bonuses and one monthly grant under parallel requests. The temporary QA account and records were removed. Saved ignored database backup before migration.
- Real Paystack checkout still unverified and disabled; merchant USD capability must be confirmed. No new live-payment claims.

## Manual editing, shared export credits, and transitions — 2026-10-17
- 94 backend tests passed in Docker against the final source, including real FFmpeg exports for crossfade, dissolve, slide left/right, wipe left/right, speed changes, fades, and silent three-cut rendering.
- 24 frontend tests passed sequentially; production build passed. New-project test verifies the manual choice and hiding/restoring AI-only options.
- Manual billing tests cover no-credit upload, skipping AI, duration/speed cost, reservation, unchanged and legacy-default export reuse, insufficient funds, completed exports, queue/render failures, and stale-job refunds.
- Browser verified the choice before upload and manual mode on a narrow viewport. Screenshot: qa-artifacts/manual-editor-choice.png.
- Remaining limitations: transition/fade previews require an export; transitions use one global style; manual projects do not auto-transcribe; single-source vertical editing and existing 180-second selected-source limits remain.

## Caption studio, brand library, settings and face tracking — 2026-10-17
- 104 backend tests passed in Docker; 26 frontend tests passed; production builds passed.
- Targeted manual workflow tests confirm the new project resolution default reaches its edit decision.
- Brand updates enforce account ownership, validate caption values and retain the kit ID. Caption preset selection and browser/account-scoped defaults have frontend coverage.
- Browser inspection confirmed caption search filtering, boxed preview, all 19 brand font options, and Settings defaults on a narrow viewport. Screenshot: qa-artifacts/brand-library.png.
- API, worker and web rebuilt and deployed, including previously blocked face tracking changes (4 Hz frontal/profile detection, geometry continuity and balanced FFmpeg crop expressions).
- Limits: caption/brand previews approximate typography; custom assets and timing render in exports. Project defaults are browser-local. Face tracking is not active-speaker recognition and has no real-footage accuracy benchmark.

## Export watermark
- Backend: 107 tests passed, including free-user bypass prevention, legacy export reuse exclusion, paid/pending/expired entitlement and actual FFmpeg pixel rendering.
- Frontend: 26 tests passed; TypeScript/Vite production builds passed.
- New exports default to a RECLIPD badge; only verified purchases within 365 days and configured unlimited accounts may opt out. Existing downloaded files are unchanged.

## Animated watermark
- Moved branding to top-left: vector scissors rotate/slide into place; RECLIPD follows and stays visible.
- Removed paid watermark helper sentence from export confirmation.
- Versioned export decisions to avoid reusing the previous watermark design.
- 9 targeted backend tests (including FFmpeg animation frames, stable settled state, placement and manual export reuse), 28 frontend tests and Docker production builds passed.

## Watermark motion refinement
- Eased scissors movement with subtle bounce, braking/return, progressive text reveal and expanding smoke puffs.
- Two-second animation repeats at midpoint only for exports longer than 15 seconds; watermark otherwise remains settled.
- 10 targeted backend tests passed, including rendering and repeat threshold. Backend Docker builds passed.
- Inspected rendered settled frame; sample animation in qa-artifacts/watermark-motion.mp4.

## Flip and bounce watermark
- Added cyan dashed cutting seam and a centred name flip followed by damped squash/stretch bounces.
- Name settles after 3.2 seconds; long-clip midpoint replay preserved.
- 11 targeted tests passed; backend Docker builds passed. Rendered sample: qa-artifacts/watermark-flip.mp4.

## Stronger word bounce
- Replaced subtle decaying motion with a full word jump/flip and two distinct rebounds, each with landing squash/stretch.
- Scissors remain parked while the word moves; settles at 3.8 seconds.
- 11 targeted tests and backend Docker builds passed.
- Close-up rendered preview: qa-artifacts/watermark-word-bounce.mp4.

## Premium watermark typography and easing
- Bundled OFL Montserrat Bold, proportional tracking, softer shadow/outline.
- Smooth acceleration/deceleration for scissors travel/return and the word flip, retaining visible word rebounds.
- 11 targeted tests and all Docker builds passed; rendered preview qa-artifacts/watermark-premium.mp4.

## Export clarity
- Increased watermark typography size and outline contrast.
- H.264 CRF 17 / medium applied consistently across export encode stages, including logo overlays; 192 kbps AAC and Lanczos video scaling.
- Full backend suite: 110 passed. Backend Docker builds passed.
- Source-aware resolution limits preserved; preview encoding unchanged.

## Account lifecycle and synced preferences
- Full backend suite: 115 passed, including password/session revocation, recovery expiry/single use/cooldown, generic recovery responses, SMTP failure, preference persistence and deletion guards.
- Frontend: 31 passed, including password confirmation, reset fragment handling and server-backed preferences.
- All Docker production builds passed; migration 550f0a4d03de adds account state. Local database backup made before migration.
- Gmail SMTP delivery requires the user's App Password; no live email sent and no payment provider enabled.

## PayPal sandbox integration
- Server-owned USD checkout, Orders v2 create/capture, validated approval host, owned payment references, stable request IDs and reusable pending orders.
- Merchant/currency/amount/capture validation; verified webhooks; idempotent credit grants and conservative refund/reversal handling.
- UI handles PayPal returns/cancellation and payment-history verification; credentials remain server-only.
- 125 backend tests and 34 frontend tests passed. All Docker builds passed. Database backed up before migration 660a1b5e04ef.
- No live payment capability enabled. External sandbox checkout/webhook testing is pending merchant credentials and a reachable webhook endpoint.

## 2026-10-19 — Signup introduction and PayPal configuration diagnosis
- Reproduced PayPal sandbox rejection: invalid `payee/merchant_id` length/syntax; credentials authenticate but merchant ID configuration needs replacement. No payment captured.
- Added setup-script merchant ID validation and actionable checkout errors.
- Added two-step welcome flow for newly registered users, AI/manual choice, preserved source drafts, account-persisted completion, skip/back/retry, responsive semantic form controls.
- Frontend: 39 tests passed; production build passed. Targeted account/PayPal backend suite: 17 tests passed.
- Real purchase and webhook verification remain pending correct seller merchant ID. Visual browser QA not performed in this pass.

## 2026-10-24 — Oracle Micro deployment test
- Fixed API migration startup: macOS AppleDouble `._*.py` sidecars were being treated as migrations. Removed only sidecars from server source and excluded them in both Docker contexts; documented metadata-free transfer.
- Rebuilt API/frontend, started all seven services. API healthy, frontend returns HTTP 200 internally. PostgreSQL/Redis healthy.
- Server media regression tests: 33 passed initially; two HTTP TestClient checks inherited secure production cookies and passed when rerun with COOKIE_SECURE=false (35 distinct checks passed). Isolated that setting in conftest; 5 local targeted tests passed even with COOKIE_SECURE=true in the parent environment. Production cookies remain secure.
- Real API upload/Whisper/highlight/export/download test passed on synthetic speech/video: source 16.931 seconds at 1080x1920; 53 transcript words; highlights ready in 104 seconds including first model download. Export/download took 236 seconds for a 5.92-second H.264/AAC clip, 1080x1920, 6,829,153 bytes. No resolution or encoder quality reduction. This is a short synthetic benchmark, not a transcription accuracy or long-video capacity certification.
- Observed snapshots reached 684 MB used host RAM and 721 MB used swap; these are not continuously measured peaks. 4 GB swap configured. Substantial rendering delay makes Micro experimental.
- Downloaded MP4 also passed a full FFmpeg video/audio decode with no errors.
- Public HTTPS not complete: Caddy certificate challenge times out; user still needs Oracle subnet TCP 80/443 ingress. Public browser/upload test pending.
- Payment checkout and YouTube retrieval disabled on this fresh server; SMTP, backups and representative production load testing remain unconfigured/unverified. No local users/media migrated.

## 2026-10-25 — Public HTTPS verification
- After Oracle ingress rules were added, Caddy obtained a trusted certificate. Public HTTPS frontend returns HTTP 200; HTTP redirects to HTTPS.
- Public `/api/upload-limits` returns JSON successfully through Caddy/nginx/API.
- Prior upload/transcription/export/download benchmark was performed internally; a full public browser upload has not yet been tested. Micro remains an experimental deployment with the limitations above.

## 2026-10-25 — DuckDNS domain
- Configured reclipd.duckdns.org (A record 92.4.142.102), APP_URL, billing return URL and CORS on the server. Previous environment saved privately as .env.before-duckdns.
- Caddy obtained a trusted certificate for the new hostname. Server Caddyfile redirects the prior sslip.io address, preserving request URI.

## Oracle YouTube downloader compatibility check
- Compared deployed yt-dlp 2026.08.19 with PyPI stable 2026.10.21. Installed newer version only in worker /tmp/reclipd-ytdlp-check; running worker dependency unchanged.
- Metadata-only extractor test on failed video lJkhLKlA2P8 with the same public-only settings still returned YouTube bot verification. No video download or processing job succeeded or was claimed. No user credits consumed by the diagnostic.

## 2026-10-26 — Isolated pytubefix test
- Installed pytubefix 11.2.1 only into worker /tmp/reclipd-pytubefix-check; production dependencies unchanged.
- Tested failed public link lJkhLKlA2P8 with default client, OAuth/cache disabled, no supplied cookies/proxies/PO token. Bounded test would download at most 100 MB and FFprobe the file.
- Test stopped with BotDetection before footage download. No clipping job or credit allocation created. This alternative does not resolve the observed Oracle block.

## VideoScale Oracle retrieval test — 2026-10-26
- Configured Basic Auth was passed privately via SSH stdin; no credential printed or added to source. Production provider remains disabled.
- Official documented API authenticated successfully from Oracle for the previously failing authorized test video lJkhLKlA2P8.
- One bounded format-394 retrieval task completed. Download endpoint returned JSON containing a signed object-storage URL; file fetched over HTTPS without forwarding provider credentials.
- Retrieved 41,129,925 bytes. FFprobe verified an AV1 video stream, 256x144, duration 4298.732065 seconds. This deliberately small video-only test confirms actual footage retrieval, not production quality or audio support.
- Still required: production adapter, bounded high-quality video/audio retrieval and merging, quota enforcement, failure handling, and end-to-end clipping tests. No paid checkout/top-up enabled. Provider balance was not independently verified.

## VideoScale adapter implementation — 2026-10-26
- Added cloud adapter to the existing YouTube worker dispatch, default disabled. Existing uploads and connected originals preserved.
- Public metadata checks, direct H.264/AAC selection up to 1080p, copy-only mux, pinned HTTPS object downloads, no redirect/auth forwarding, bounded download and temporary-file cleanup.
- Lifetime SQLite bandwidth reservations protect concurrent workers; zero budget fails closed, failed attempts retain reservations, no reset/top-up code.
- 32 import/provider tests passed locally (including concurrent budget exhaustion, partial-download cleanup, secret-safe errors, public policy, format/size/audio selection and merge dispatch).
- Backend images built on Oracle; live services not switched/enabled. Real 57-minute authorized source had 1.428 GB 1080p video alone, exceeding default 512 MB import cap. Initial live selection exposed HLS unknown-size preference; fixed by selecting direct HTTPS formats. No new download task was created in these checks.
- Remaining: short authorized source to verify combined real video/audio, clipping/export and enable production with a confirmed remaining provider allowance. Previous real retrieval verified only 144p video without audio.

## VideoScale deployment — 2026-10-26
- User explicitly requested deployment before the outstanding full audiovisual test.
- No active projects at rollout. Recreated API, worker and beat using the built integration images.
- Private credential configured on Oracle through SSH stdin. Cloud provider enabled with 1,000,000,000-byte lifetime reservation budget and 512 MB per-import cap; no paid purchases or top-up configured by this deployment.
- API healthy; HTTPS /api/upload-limits returned 200 with expected limits. Worker configuration verified without revealing credentials, and existing YouTube resolution routes into the adapter.
- Full real video+audio import through clipping/export remains unverified. Earlier real footage test was video-only. Local automated import/provider suite: 32 passed.

## Import allowance increase — 2026-10-26
User confirmed 9.96 GB remaining in VideoScale. Oracle configured for 2048 MB per import and 8,000,000,000-byte lifetime reservation budget. Prior reserved usage was zero and there were no active projects. Existing ledger and credentials preserved. Backend services recreated; public API healthy. Duration remains capped at 3600 seconds. No provider purchase or automatic top-up performed.

## Queued provider response diagnosis — 2026-10-27
- Failed project 7a72ab61-e7a7-4d66-8966-1865df781ee6 used video Gd1oMg7_8Mc.
- Oracle format lookup succeeded (HTTP 200); selected 137 + 140, conservative reservation 1,615,750,826 bytes.
- Provider task creation returned HTTP 202 with a valid queued task. Adapter incorrectly required HTTP 200 and surfaced a temporary-unavailable error.
- Corrected POST handling to accept 200/201/202, retain strict GET behavior and reject empty 204 responses. Regression suite: 36 passed.
- Saved one diagnostic video task privately in the shared media volume for recovery; task ID and credentials are not recorded here. Prior ledger reservations were 5,086,602,907 bytes; no refunds made because earlier tasks may have transferred data.
- Recovery identified a second defect: storage DNS sorted IPv6 first, but Oracle has no IPv6 route (errno 101); IPv4 destinations connect successfully. Added validated-address fallback with IPv4 preference and unchanged TLS verification. Combined suite: 37 passed.
- Both fixes deployed to API/worker/beat; API healthy. Existing provider task and its 1,615,750,826-byte recovery reservation reused without another video-task creation.
- At user's explicit request, live account ianndungu06@gmail.com granted is_admin and appended to persistent UNLIMITED_USER_IDS configuration. Server verified admin=True, unlimited=True and watermark_removal=True. Third-party bandwidth safeguards remain unchanged.
- Live account entitlements verified after restart: admin=True, unlimited=True, watermark_removal=True.
- Saved provider task later returned status=expired during recovery. Stopped only the identified one-off Python recovery process; Celery remains running. No complete audiovisual source was recovered or attached to the failed project; full import/export verification remains outstanding. Both HTTP 202 handling and storage address fallback are deployed.

## 2026-10-27 upload timeout correction
- Production web log showed upload limits fetched at 10:54:01 UTC and upload connection aborted at 11:04:02 UTC, matching the frontend's fixed ten-minute XHR deadline.
- Replaced total transfer deadline with five-minute inactivity watchdog refreshed by upload progress, with cleanup on completion/error/abort. Slow progressing uploads can exceed ten minutes without reducing media quality or raising size limits.
- Nginx body/send/read inactivity limits aligned to five minutes.
- Frontend: 43 tests passed, including simulated uploads progressing beyond ten minutes, stalled transfer abort, and timer cleanup. Production build passed. A real large-file retry remains necessary to confirm the user's connection end to end.
