# Feature status — RECLIPD AI Studio

Status refers to the local development release. **Implemented** means executable product code is present, not a placeholder screen. Model-dependent integrations and production deployment work are listed separately.

## Phase 1 — application foundation

- [x] React, TypeScript, Vite and Tailwind frontend with original dark navy/blue RECLIPD branding; responsive navigation and forms.
- [x] FastAPI/Pydantic API, SQLAlchemy models, PostgreSQL and Alembic migrations.
- [x] Redis/Celery worker and scheduler in Docker Compose.
- [x] Registration/login/logout, Argon2 password hashes, expiring JWT HttpOnly cookies, CSRF origin checks, Redis login throttling.
- [x] Project-level ownership enforcement across media, clips, edits and exports; admin authorization.
- [x] Drag/drop MP4, MOV, MKV, WebM upload, rights confirmation, request/file limits, project creation and persistence.
- [x] Authorized direct HTTPS imports with hostname allowlist, public-IP checks, pinned TLS connection, redirect denial, size/time limits.
- [x] No prohibited YouTube downloading, policy circumvention, DRM bypass, or credential extraction. YouTube metadata import is not included; users upload authorized source files.
- [x] `.env.example`, secret-generating bootstrap, README and Docker setup.

## Phase 2 — processing

- [x] Real FFprobe inspection, dimensions/duration/format checks; FFmpeg audio extraction.
- [x] Real faster-whisper transcription with word timestamps and configurable local model/device.
- [x] PySceneDetect scene boundaries and per-second RMS audio intensity.
- [x] Deterministic transcript/scene/audio ranking, duration/count settings, overlap suppression, score explanations and honest missing-signal warnings.
- [x] Optional local LLM protocol/adapter for contextual ranking and headlines; deterministic fallback on failure.
- [x] Optional local Pyannote speaker-change adapter with genuine model output; excluded when unavailable.
- [x] Actual vertical H.264/AAC rendering, split/concat, no-upscale sizing and MP4 fast-start.
- [x] OpenCV frontal-face tracking with smoothed crop motion; manual focus and fit overrides.
- [x] Durable job state and progress updates, timeouts, duplicate-delivery guards, retryable failures, quota refunds, stale-job/scratch cleanup.
- [ ] General semantic subject tracking, active-speaker framing, and multi-person shot composition. Default auto framing follows the largest frontal face; manual/fit is the fallback.
- [ ] A provisioned speaker diarization model in the default image. Adapter exists, but its heavyweight optional dependencies/model are not installed or validated by default.

## Phase 3 — creative workflow

- [x] Ranked clip results with timestamps, transcript descriptions, scores and evidence.
- [x] Dedicated editor with preview, numeric trim controls, split/remove segments, timeline seeking, playback, undo/redo and non-destructive saved edit decisions.
- [x] Word text/timestamp editing; trim/split retiming for captions.
- [x] Twenty caption presets, including the original bold, minimal, neon, pop and boxed styles.
- [x] Font family/size/weight, fill/accent colors, stroke/shadow, placement, and highlight/fade/no-animation controls.
- [x] Built-in licensed DejaVu/Liberation fonts; licensed TTF/OTF uploads with validation and restricted-embedding rejection.
- [x] 3–10 headline suggestions through the API; UI requests 5, with funny/dramatic/informative/concise/viral tones. Fallbacks are labeled transcript templates, not generated insights.
- [x] Brand kits with fonts, colors, logo assets and export resolution; application in editor and render.
- [x] Export creation, progress, history and authenticated MP4 downloads.
- [ ] Pixel-identical browser preview of libass caption layout and automatic face tracking. The preview is explicitly approximate; the final render applies the full pipeline.
- [ ] Advanced caption keyframes, arbitrary logo positioning, transition effects or a general multi-track NLE. The requested basic trim/split workflow is implemented.

## Phase 4 — durability and hardening

- [x] Persistent project/transcript/clip/edit/export/brand/asset records and migrations.
- [x] Revision-aware edit saves and immutable export decisions.
- [x] Development quota layer: reserved processing seconds, PostgreSQL row locking, refund on failure, active project/export limits.
- [x] Safe subprocess argument arrays, FFmpeg protocol/demuxer restrictions, SSRF protection, opaque storage keys, path containment, upload/asset limits and protected media routes.
- [x] Non-root application/worker images; loopback web/API exposure; no database/broker host ports.
- [x] Structured API/media diagnostics, operations overview and administrator retry API/UI.
- [x] Backend tests for ownership, cookie authentication, upload policy, SSRF rejection, edit conflicts, ranking, ASS safety, timing, quota and task lifecycle.
- [x] Real FFmpeg integration tests; frontend timeline and application interaction tests; production type/build checks.
- [x] README describes configuration, deployment boundaries, licenses and operational limitations.
- [ ] External S3 implementation. A storage contract/local implementation is present; S3 needs staging/presigned-object work.
- [ ] Real payment provider integration. Intentionally absent for the requested local MVP; no payment credentials needed.
- [ ] Public production launch readiness: account recovery/verification, privacy/deletion/retention workflows, billing provider, observability/backups, release-image scanning and capacity/security review.

## Required pages

| Page | Route | Behavior |
| --- | --- | --- |
| Marketing | `/` | Original landing page and working studio/auth navigation |
| Authentication | `/auth` | Registration and session sign-in |
| Dashboard | `/studio` | Actual projects, search/filter, usage and empty state |
| New project | `/studio/new` | Upload/import with rights/configuration |
| Processing | `/studio/projects/:id` | Persisted status/stages, polling, failure/retry |
| Results | `/studio/projects/:id` | Ranked highlights when ready |
| Clip editor | `/studio/clips/:id` | Saved edit decisions, captions, cuts, brands, export |
| Caption gallery | `/studio/captions` | Twenty presets; choose a clip to apply |
| Headline suggestions | `/studio/headlines` | Project/clip/tone selection and real API suggestions |
| Brand kits | `/studio/brands` | Save kits, upload assets, reuse in editor |
| Export history | `/studio/exports` | Actual export records, progress and download |
| Account | `/studio/settings` | Profile name editing; unsupported account actions disclosed |
| Billing/usage | `/studio/billing` | Actual development allowance; no payment collection |
| Admin operations | `/studio/admin` | Authorized job overview and failed-project retry |

## Verification record

- Final Docker backend suite: **47 passed**, including all FFmpeg tests. Host-only runs skip FFmpeg tests when the executables are absent.
- Docker FFmpeg tests verify real media inspection, split/concat, caption burn-in, output duration/aspect ratio and invalid-media rejection.
- Frontend interaction suite: **11 passed**. TypeScript/Vite production build passes.
- Frontend dependency audit reports zero vulnerabilities after updating Vitest.
- Whisper `base` transcribed a synthetic 17.775-second English fixture into 52 timed words in Docker. No user media was used.
- Full-stack smoke test passed: registration → upload → transcription → 2 highlights → edits → headlines → rendered MP4 download → exact quota accounting.
- Browser checks covered landing/sign-in, authenticated dashboard/results/editor, undo/redo/save, export history, and 390-pixel mobile layouts/navigation. Full results are recorded in `VERIFICATION.md`.

Model-heavy integrations (optional LLM, optional Pyannote) require separately provisioned services/models. They are not presented as validated simply because their fallback tests pass.

### Playback repair
- Clip cards now have playable short previews with native controls and retry.
- Editor playback uses cached browser-compatible excerpts; trim/split timestamps remain relative to the original source.
- Preview cache is disposable after seven days; exports still use original-quality media.
- CPU transcription threads and beam size are configurable. A short warm-model benchmark did not establish a material beam-size speedup; long-source processing remains CPU-bound.

### URL import update
- [x] Default Paste Video Link tab; original upload flow preserved.
- [x] Watch, youtu.be and Shorts parsing; official Data API title/channel/thumbnail/duration adapter.
- [x] Source access preflight, loading/retry, explicit upload fallback, stale-preview invalidation.
- [x] Approved direct HTTPS file imports, including original source URLs paired with YouTube references; existing Celery pipeline reused.
- [ ] Live YouTube metadata verification: requires operator-supplied `YOUTUBE_API_KEY`.
- [ ] Automatic footage retrieval from YouTube itself: no approved media-access integration is configured. A public URL or metadata key is insufficient.

### Expanded caption design library
- 19 built-in font families, each with regular and bold files served to browser previews and installed for FFmpeg exports.
- 20 caption presets including editorial, podcast, documentary, typewriter, mint, coral, cinema, lecture, and high contrast.
- Presets reset prior styling consistently; selecting a built-in font clears a previously selected custom font override. Existing custom font uploads remain available.
- RECLIPD continues to use its own processing engine; no OpusClip integration was added. YouTube audiovisual access remains unresolved.


### Premium interface and connected source update
- [x] White-default semantic light/dark/system themes; persistent preference in Settings only.
- [x] Redesigned landing, responsive studio surfaces, collapsible sidebar, caption playground and reduced-motion support.
- [x] Guest draft preservation through login, upload progress and local file preview.
- [x] Owner-scoped original-video connections and provider extension point; existing pipeline reused.
- [x] 19 font families, 20 presets, headline overlay, caption background/stroke colors, letter spacing and audio volume.
- [x] Real upload → transcription → clips → styled MP4 export and connected-original → import → clips smoke tests.
- [ ] Arbitrary YouTube footage retrieval; no approved external footage provider configured.
- [ ] Cloud storage account connectors, caption line-height control, translation and non-vertical exports.
- [ ] Complete every-page browser audit and formal WCAG audit; current visual checks cover landing, dashboard, gallery and new project on desktop/mobile.

### Revised YouTube scope
- [x] Optional unofficial yt-dlp public-video provider, enabled locally at the user's request.
- [x] Rights confirmation, restrictive metadata policy, worker isolation/timeouts, byte limits and upload fallback.
- [x] Live user-authorized YouTube download → transcription → highlight → MP4 verification using the supplied test URL; success does not guarantee availability for every video.
- Earlier statements that no YouTube extractor exists are superseded by this optional provider; no official footage-access integration has been added.
