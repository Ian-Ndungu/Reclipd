import { ExportDialog } from "./ExportDialog";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  Download,
  LoaderCircle,
  Pause,
  Play,
  Redo2,
  Save,
  Scissors,
  Undo2,
  Volume2,
  X,
} from "lucide-react";
import { api, json, time } from "./api";
import {
  type Brand,
  type CaptionStyle,
  type Clip,
  type Edits,
  type Project,
  presets,
  defaultCaption,
  fontFamilies,
} from "./types";
import { ErrorBox } from "./App";
import { activeWord, splitAt, totalDuration } from "./editorState";
import type { Asset } from "./Assets";
export function Editor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const video = useRef<HTMLVideoElement>(null);
  const resume = useRef(false);
  const pendingSeek = useRef<number | null>(null);
  const positionRef = useRef(0);
  const [buffering, setBuffering] = useState(false);
  const [previewRetry, setPreviewRetry] = useState(0);
  const [exportQuote, setExportQuote] = useState<{seconds: number; reused: boolean; can_remove_watermark: boolean} | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportError, setExportError] = useState("");
  const [canRemoveWatermark, setCanRemoveWatermark] = useState(false);
  const [siblings, setSiblings] = useState<Clip[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [clip, setClip] = useState<Clip | null>(null),
    [project, setProject] = useState<Project | null>(null),
    [edits, setEdits] = useState<Edits | null>(null),
    [past, setPast] = useState<Edits[]>([]),
    [future, setFuture] = useState<Edits[]>([]),
    [brands, setBrands] = useState<Brand[]>([]),
    [position, setPosition] = useState(0),
    [playing, setPlaying] = useState(false),
    [tab, setTab] = useState("Captions"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [saved, setSaved] = useState(false),
    [segmentIndex, setSegmentIndex] = useState(0);
  useEffect(() => {
    api<Asset[]>("/assets")
      .then(setAssets)
      .catch((e) => setError(e.message));
    api<{ clip: Clip; project: Project }>(`/clips/${id}`)
      .then(({ clip, project }) => {
        setClip(clip);
        setProject(project);
        api<Project>(`/projects/${project.id}`)
          .then((p) => setSiblings(p.clips || []))
          .catch(() => {});
        setPast([]);
        setFuture([]);
        setSaved(false);
        setEdits(clip.edits);
        setPosition(clip.edits.segments[0].start);
      })
      .catch((e) => setError(e.message));
    api<Brand[]>("/brands")
      .then(setBrands)
      .catch((e) => setError(e.message));
  }, [id]);
  useEffect(() => {
    const id = edits?.captions.custom_font_id;
    if (!id) return;
    const font = new FontFace("ReclipdCustom", `url(/api/assets/${id})`);
    let active = true;
    font
      .load()
      .then((f) => {
        if (active) document.fonts.add(f);
      })
      .catch(() => {});
    return () => {
      active = false;
      document.fonts.delete(font);
    };
  }, [edits?.captions.custom_font_id]);
  positionRef.current = position;
  useEffect(() => {
    // Timeline changes (including undo/redo) invalidate the active playback cut.
    resume.current = false;
    video.current?.pause();
    setPlaying(false);
    setBuffering(false);
    if (edits?.segments.length) {
      const oldPosition = positionRef.current;
      let index = edits.segments.findIndex(s => oldPosition >= s.start && oldPosition < s.end);
      if (index < 0) index = 0;
      const cut = edits.segments[index];
      const target = Math.max(cut.start, Math.min(oldPosition, cut.end - 0.001));
      setSegmentIndex(index);
      setPosition(target);
      pendingSeek.current = target;
      const element = video.current;
      if (element && element.readyState >= 1 && element.getAttribute("src")?.includes(`start=${cut.start}&end=${cut.end}&`)) {
        element.currentTime = target - cut.start;
        pendingSeek.current = null;
      }
    }
  }, [edits?.segments]);
  useEffect(() => {
    if (video.current) video.current.volume = edits?.volume ?? 1;
  }, [edits?.volume, segmentIndex, previewRetry]);
  useEffect(() => {
    if (video.current) { video.current.playbackRate = edits?.speed ?? 1; video.current.preservesPitch = true; }
  }, [edits?.speed, segmentIndex, previewRetry]);
  useEffect(() => {
    if (!playing || !edits) return;
    let frame = 0;
    const cut = edits.segments[segmentIndex];
    const tick = () => {
      if (video.current && cut && pendingSeek.current === null && video.current.readyState >= 2) {
        setPosition(Math.min(cut.end, cut.start + video.current.currentTime));
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, segmentIndex, edits?.segments]);
  useEffect(() => {
    if (!edits) return;
    let active = true;
    setExportQuote(null);
    const timer = setTimeout(() => {
      api<{seconds: number; reused: boolean; can_remove_watermark: boolean}>(`/clips/${id}/export-quote`, {method: "POST", body: json(edits)})
        .then(value => {if (active) {setExportQuote(value); setCanRemoveWatermark(value.can_remove_watermark);}}).catch(() => {});
    }, 300);
    return () => {active = false; clearTimeout(timer);};
  }, [id, edits, project?.config?.workflow]);
  function change(next: Edits) {
    if (!edits) return;
    setPast((p) => [...p.slice(-49), edits]);
    setFuture([]);
    setEdits(next);
    setSaved(false);
  }
  function style(value: Partial<CaptionStyle>) {
    if (edits) change({ ...edits, captions: { ...edits.captions, ...value } });
  }
  async function save() {
    if (!clip || !edits) return;
    const c = await api<Clip>(`/clips/${id}`, {
      method: "PUT",
      body: json({ revision: clip.revision, edits }),
    });
    setClip(c);
    setSaved(true);
    return c;
  }
  if (!edits || !clip || !project)
    return <ErrorBox error={error || "Opening editor…"} />;
  const current = activeWord(edits, position);
  const wordIndex = edits.words.findIndex((w) => w === current);
  const phrase =
    wordIndex < 0
      ? []
      : edits.words.slice(
          Math.floor(wordIndex / 5) * 5,
          Math.floor(wordIndex / 5) * 5 + 5,
        );
  const segment = edits.segments[segmentIndex] ?? edits.segments[0];
  const previewUrl = `/api/clips/${clip.id}/preview?start=${segment.start}&end=${segment.end}&retry=${previewRetry}`;
  const elapsed = edits.segments.slice(0, segmentIndex).reduce((n, s) => n + s.end - s.start, 0)
    + Math.max(0, Math.min(segment.end - segment.start, position - segment.start));
  const seekElapsed = (seconds: number) => {
    let remaining = Math.max(0, Math.min(seconds, totalDuration(edits)));
    for (let i = 0; i < edits.segments.length; i++) {
      const cut = edits.segments[i];
      const length = cut.end - cut.start;
      if (remaining < length || i === edits.segments.length - 1) {
        seek(cut.start + Math.min(remaining, length - 0.001));
        return;
      }
      remaining -= length;
    }
  };
  const seek = (value: number) => {
    const index = edits.segments.findIndex(
      (s) => value >= s.start && value < s.end,
    );
    if (index < 0) return;
    setPosition(value);
    setSegmentIndex(index);
    pendingSeek.current = value;
    if (video.current && index === segmentIndex && video.current.readyState >= 1) {
      video.current.currentTime = value - segment.start;
      pendingSeek.current = null;
    }
  };
  const play = () => {
    if (!video.current) return;
    setError("");
    resume.current = true;
    setBuffering(true);
    const element = video.current;
    element.play().catch((e: DOMException) => {
      if (video.current !== element) return;
      if (e.name === "AbortError") return;
      resume.current = false;
      setBuffering(false);
      setPlaying(false);
      setError("Preview could not play. Retry the preview below.");
    });
  };
  const toggle = () => {
    if (!video.current) return;
    if (playing || resume.current) {
      resume.current = false;
      video.current.pause();
      setPlaying(false);
      setBuffering(false);
    } else {
      if (video.current.ended || position >= segment.end) seek(edits.segments[0].start);
      play();
    }
  };
  const canSplit = edits.segments.some(s => position > s.start + 0.1 && position < s.end - 0.1);
  function split() {
    const actual = video.current && pendingSeek.current === null && video.current.readyState >= 1
      ? segment.start + video.current.currentTime : position;
    const next = splitAt(edits!, actual);
    if (next === edits) return;
    positionRef.current = actual;
    setPosition(actual);
    change(next);
  }
  return (
    <div className="editor">
      <div className="editor-heading">
        <div>
          <Link className="text-link" to={`/studio/projects/${project.id}`}>
            <ArrowLeft size={14} />
            Back to highlights
          </Link>
          <h1>{clip.title}</h1>
        </div>
        <div className="button-row">
          <button
            className="icon-button"
            aria-label="Undo"
            disabled={!past.length}
            onClick={() => {
              const prev = past[past.length - 1];
              setFuture([edits, ...future]);
              setPast(past.slice(0, -1));
              setEdits(prev);
              setSaved(false);
            }}
          >
            <Undo2 size={18} />
          </button>
          <button
            className="icon-button"
            aria-label="Redo"
            disabled={!future.length}
            onClick={() => {
              setPast([...past, edits]);
              setEdits(future[0]);
              setFuture(future.slice(1));
              setSaved(false);
            }}
          >
            <Redo2 size={18} />
          </button>
          <button
            className="button secondary small"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await save();
                setError("");
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {saved ? <Check size={15} /> : <Save size={15} />}{" "}
            {saved ? "Saved" : "Save"}
          </button>
          <button
            className="button primary small"
            disabled={busy}
            onClick={() => {setExportError(""); setExportOpen(true);}}
          >
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Download size={16} />
            )}
            Export{project.config?.workflow === "manual" ? (exportQuote ? (exportQuote.reused ? " · reuse free" : ` · ${(exportQuote.seconds / 60).toFixed(3)} credit min`) : " · calculating cost…") : ""}
          </button>
        </div>
      </div>
      <ErrorBox error={error} />
      {exportOpen && <ExportDialog open={exportOpen} title={clip.title} edits={edits} quote={exportQuote}
        busy={busy} error={exportError} canRemoveWatermark={canRemoveWatermark}
        onWatermark={watermark => change({...edits, watermark})}
        onClose={() => setExportOpen(false)}
        onConfirm={async () => {
          setBusy(true); setExportError("");
          try {
            await save();
            await api(`/clips/${id}/exports`, {method:"POST"});
            setExportOpen(false);
            navigate("/studio/exports");
          } catch(e) {setExportError((e as Error).message);}
          finally {setBusy(false);}
        }}/>}
      <div className="editor-workspace">
        <aside className="editor-library">
          <h3>Project clips</h3>
          <nav aria-label="Project clips">
            {siblings.map((c) => (
              <Link
                className={c.id === clip.id ? "active" : ""}
                key={c.id}
                to={`/studio/clips/${c.id}`}
              >
                {c.title}
                <small>{time(c.end - c.start)}</small>
              </Link>
            ))}
          </nav>
          <h3>Creative tools</h3>
          <button onClick={() => setTab("Captions")}>Caption templates</button>
          <button onClick={() => setTab("Frame")}>Brand kits & media</button>
          <Link to="/studio/brands">Manage assets ({assets.length})</Link>
          <h3>Brand kits</h3>
          {brands.map((b) => (
            <button
              key={b.id}
              onClick={() =>
                change({
                  ...edits,
                  brand_kit_id: b.id,
                  captions: b.config.captions,
                  resolution: b.config.resolution,
                  logo_asset_id: b.config.logo_asset_id,
                })
              }
            >
              {b.name}
            </button>
          ))}
        </aside>
        <div className="preview-column">
          <div className="preview-toolbar">
            <span>{buffering ? "Preparing clip preview…" : "Preview"}</span>
            <span>9:16 · {edits.resolution}p maximum</span>
          </div>
          {error && (
            <button
              className="button secondary"
              onClick={() => {
                setError("");
                setPreviewRetry((n) => n + 1);
              }}
            >
              Retry preview
            </button>
          )}
          <div className="video-stage">
            <div className="portrait-video">
              <video
                key={previewUrl}
                ref={video}
                src={previewUrl}
                playsInline
                preload="auto"
                onPlay={() => { resume.current = true; }}
                onPause={(e) => {
                  setPlaying(false);
                  if (!e.currentTarget.ended) resume.current = false;
                }}
                style={{
                  filter: `brightness(${edits.brightness ?? 1}) contrast(${edits.contrast ?? 1}) saturate(${edits.saturation ?? 1})`,
                  transform: edits.flip_horizontal ? "scaleX(-1)" : undefined,
                  objectFit: edits.reframe === "fit" ? "contain" : "cover",
                  objectPosition: `${edits.focus_x * 100}% center`,
                }}
                onLoadedMetadata={(e) => {
                  e.currentTarget.currentTime = Math.max(
                    0,
                    Math.min(
                      (pendingSeek.current ?? position) - segment.start,
                      segment.end - segment.start,
                    ),
                  );
                  pendingSeek.current = null;
                  e.currentTarget.volume = edits.volume ?? 1;
                  e.currentTarget.playbackRate = edits.speed ?? 1;
                  e.currentTarget.preservesPitch = true;
                }}
                onCanPlay={() => {
                  setBuffering(false);
                  if (resume.current) play();
                }}
                onWaiting={() => setBuffering(true)}
                onPlaying={() => {
                  setBuffering(false);
                  setPlaying(true);
                }}
                onError={() => {
                  resume.current = false;
                  setPlaying(false);
                  setBuffering(false);
                  setError(
                    "Preview unavailable. Retry below; your original video and edits are saved.",
                  );
                }}
                onEnded={() => {
                  if (segmentIndex + 1 < edits.segments.length) {
                    pendingSeek.current = edits.segments[segmentIndex + 1].start;
                    setPlaying(false);
                    setPosition(edits.segments[segmentIndex + 1].start);
                    setSegmentIndex(segmentIndex + 1);
                    setBuffering(true);
                  } else {
                    setPosition(segment.end);
                    resume.current = false;
                    setPlaying(false);
                  }
                }}
                onTimeUpdate={(e) => {
                  if (pendingSeek.current === null)
                    setPosition(Math.min(segment.end, segment.start + e.currentTarget.currentTime));
                }}
              />
              {edits.captions.enabled && phrase.length > 0 && (
                <div
                  className={`live-captions placement-${edits.captions.placement} ${edits.captions.preset === "boxed" || edits.captions.background ? "caption-box" : ""}`}
                  style={{
                    fontFamily: edits.captions.custom_font_id
                      ? "ReclipdCustom"
                      : `${edits.captions.font}, sans-serif`,
                    fontSize: edits.captions.size / 3.6,
                    fontWeight: edits.captions.weight,
                    color: edits.captions.color,
                    textShadow: `1px 1px ${edits.captions.shadow}px black`,
                    WebkitTextStroke: `${edits.captions.stroke / 5}px ${edits.captions.stroke_color || "#000000"}`,
                    letterSpacing: (edits.captions.letter_spacing || 0) / 3.6,
                    background: edits.captions.background
                      ? edits.captions.background_color
                      : undefined,
                  }}
                >
                  {phrase.map((w, i) => (
                    <span
                      key={i}
                      style={{
                        color:
                          w === current &&
                          edits.captions.animation === "highlight"
                            ? edits.captions.emphasis_color
                            : edits.captions.color,
                      }}
                    >
                      {w.word}{" "}
                    </span>
                  ))}
                </div>
              )}
              {edits.show_headline && (
                <div className="headline-overlay">{edits.headline}</div>
              )}
              {edits.logo_asset_id && (
                <img
                  className="preview-logo"
                  src={`/api/assets/${edits.logo_asset_id}`}
                  alt="Brand logo"
                />
              )}
            </div>
          </div>
          <div className="transport">
            <button
              className="icon-button"
              onClick={toggle}
              aria-label={playing ? "Pause" : "Play"}
            >
              {playing ? <Pause size={20} /> : <Play size={20} />}
            </button>
            <span>
              {time(elapsed / (edits.speed ?? 1))} <em>/ {time(totalDuration(edits) / (edits.speed ?? 1))}</em>
            </span>
            <span className="transport-end">
              <Volume2 size={16} />
              Clip time
            </span>
          </div>
          <div className="timeline">
            <div className="timeline-heading">
              <span>
                <Scissors size={14} /> Edit timeline ·{" "}
                {time(totalDuration(edits))}
              </span>
              <button
                className="text-link"
                onClick={split}
                disabled={!canSplit}
                title={canSplit ? "Split this cut at the current frame" : "Move the playhead inside a cut to split"}
              >
                Split at playhead
              </button>
            </div>
            <input
              className="scrubber"
              type="range"
              min={0}
              max={totalDuration(edits)}
              step={0.05}
              value={elapsed}
              aria-valuetext={`${elapsed.toFixed(2)} of ${totalDuration(edits).toFixed(2)} seconds`}
              style={{ background: `linear-gradient(to right, var(--accent) ${100 * elapsed / totalDuration(edits)}%, var(--border) ${100 * elapsed / totalDuration(edits)}%)` }}
              onChange={(e) => seekElapsed(Number(e.target.value))}
              aria-label="Clip playhead"
            />
            <div className="timeline-track">
              {edits.segments.map((s, i) => (
                <button
                  key={i}
                  aria-label={`Seek within cut ${i + 1}`}
                  style={{ flex: `${s.end - s.start} 1 0%` }}
                  onClick={(event) => {
                    const bounds = event.currentTarget.getBoundingClientRect();
                    const fraction = event.detail === 0 || bounds.width === 0 ? 0
                      : Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
                    seek(s.start + Math.min(s.end - s.start - 0.001, fraction * (s.end - s.start)));
                  }}
                >
                  <FilmStrip /> {time(s.start)}–{time(s.end)}
                </button>
              ))}
              <span className="timeline-playhead" aria-hidden="true" style={{ left: `${100 * elapsed / totalDuration(edits)}%` }} />
            </div>
            <p className="timeline-hint">Drag the progress bar or click a frame position below it, then split. Splitting pauses at that position and keeps both cuts.</p>
            <div className="segment-list">
              {edits.segments.map((s, i) => (
                <div key={i}>
                  <span>Cut {i + 1}</span>
                  <label>
                    Trim start
                    <input
                      type="range"
                      aria-label={`Cut ${i + 1} trim start`}
                      min={0}
                      max={s.end - 0.1}
                      step="0.1"
                      value={s.start}
                      onChange={(e) =>
                        change({
                          ...edits,
                          segments: edits.segments.map((v, j) =>
                            j === i
                              ? { ...v, start: Number(e.target.value) }
                              : v,
                          ),
                        })
                      }
                    />
                  </label>
                  <label>
                    Trim end
                    <input
                      type="range"
                      aria-label={`Cut ${i + 1} trim end`}
                      min={s.start + 0.1}
                      max={Math.min(project.media.duration ?? clip.end, s.start + 180)}
                      step="0.1"
                      value={s.end}
                      onChange={(e) =>
                        change({
                          ...edits,
                          segments: edits.segments.map((v, j) =>
                            j === i ? { ...v, end: Number(e.target.value) } : v,
                          ),
                        })
                      }
                    />
                  </label>
                  <label>
                    In{" "}
                    <input
                      aria-label={`Cut ${i + 1} start`}
                      type="number"
                      min={0}
                      max={s.end - 0.1}
                      step={0.1}
                      value={s.start}
                      onChange={(e) =>
                        change({
                          ...edits,
                          segments: edits.segments.map((v, j) =>
                            i === j
                              ? { ...v, start: Number(e.target.value) }
                              : v,
                          ),
                        })
                      }
                    />
                  </label>
                  <label>
                    Out{" "}
                    <input
                      aria-label={`Cut ${i + 1} end`}
                      type="number"
                      min={s.start + 0.1}
                      max={project.media.duration}
                      step={0.1}
                      value={s.end}
                      onChange={(e) =>
                        change({
                          ...edits,
                          segments: edits.segments.map((v, j) =>
                            i === j ? { ...v, end: Number(e.target.value) } : v,
                          ),
                        })
                      }
                    />
                  </label>
                  <button
                    className="icon-button"
                    aria-label={`Remove cut ${i + 1}`}
                    disabled={edits.segments.length === 1}
                    onClick={() =>
                      change({
                        ...edits,
                        segments: edits.segments.filter((_, j) => j !== i),
                      })
                    }
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>
          <p className="fine-print">
            Caption layout and automatic reframing are approximations here.
            Rendered exports apply the full FFmpeg styles and tracking.
          </p>
        </div>
        <aside className="editor-inspector">
          <div className="tabs">
            {["Captions", "Transcript", "Frame"].map((t) => (
              <button
                className={tab === t ? "active" : ""}
                onClick={() => setTab(t)}
                key={t}
              >
                {t}
              </button>
            ))}
          </div>
          {tab === "Captions" ? (
            <>
              <div className="inspector-section">
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={edits.captions.enabled}
                    onChange={(e) => style({ enabled: e.target.checked })}
                  />
                  Show captions
                </label>
                <h3>Find your style</h3>
                <div className="preset-picker">
                  {presets.map((p) => (
                    <button
                      className={
                        edits.captions.preset === p.id ? "selected" : ""
                      }
                      key={p.id}
                      onClick={() =>
                        style({
                          ...defaultCaption,
                          ...p.style,
                          custom_font_id: null,
                          preset: p.id,
                        })
                      }
                    >
                      <strong
                        style={{
                          color: p.style.emphasis_color,
                          fontFamily: p.style.font,
                        }}
                      >
                        Aa
                      </strong>
                      {p.name}
                    </button>
                  ))}
                </div>
              </div>
              <div className="inspector-section">
                <h3>Make it yours</h3>
                <label>
                  Font family
                  <select
                    value={edits.captions.font}
                    onChange={(e) =>
                      style({
                        font: e.target.value as CaptionStyle["font"],
                        custom_font_id: null,
                      })
                    }
                  >
                    {fontFamilies.map((f) => (
                      <option key={f}>{f}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Custom font
                  <select
                    value={edits.captions.custom_font_id || ""}
                    onChange={(e) =>
                      style({ custom_font_id: e.target.value || null })
                    }
                  >
                    <option value="">Use built-in font</option>
                    {assets
                      .filter((a) => a.kind === "font")
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                  </select>
                </label>
                <div className="form-grid">
                  <label>
                    Size
                    <input
                      type="number"
                      min={24}
                      max={140}
                      value={edits.captions.size}
                      onChange={(e) => style({ size: Number(e.target.value) })}
                    />
                  </label>
                  <label>
                    Weight
                    <select
                      value={edits.captions.weight}
                      onChange={(e) =>
                        style({ weight: Number(e.target.value) as 400 | 700 })
                      }
                    >
                      <option value={400}>Regular</option>
                      <option value={700}>Bold</option>
                    </select>
                  </label>
                </div>
                <div className="form-grid">
                  <label>
                    Text
                    <input
                      type="color"
                      value={edits.captions.color}
                      onChange={(e) => style({ color: e.target.value })}
                    />
                  </label>
                  <label>
                    Emphasis
                    <input
                      type="color"
                      value={edits.captions.emphasis_color}
                      onChange={(e) =>
                        style({ emphasis_color: e.target.value })
                      }
                    />
                  </label>
                </div>
                <div className="form-grid">
                  <label>
                    Stroke
                    <input
                      type="range"
                      min={0}
                      max={8}
                      value={edits.captions.stroke}
                      onChange={(e) =>
                        style({ stroke: Number(e.target.value) })
                      }
                    />
                  </label>
                  <label>
                    Shadow
                    <input
                      type="range"
                      min={0}
                      max={8}
                      value={edits.captions.shadow}
                      onChange={(e) =>
                        style({ shadow: Number(e.target.value) })
                      }
                    />
                  </label>
                </div>
                <div className="form-grid">
                  <label>
                    Stroke color
                    <input
                      type="color"
                      value={edits.captions.stroke_color || "#000000"}
                      onChange={(e) => style({ stroke_color: e.target.value })}
                    />
                  </label>
                  <label>
                    Background color
                    <input
                      type="color"
                      value={edits.captions.background_color || "#111827"}
                      onChange={(e) =>
                        style({ background_color: e.target.value })
                      }
                    />
                  </label>
                </div>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={!!edits.captions.background}
                    onChange={(e) => style({ background: e.target.checked })}
                  />
                  Caption background
                </label>
                <label>
                  Letter spacing
                  <input
                    type="range"
                    min="0"
                    max="12"
                    step="0.5"
                    value={edits.captions.letter_spacing || 0}
                    onChange={(e) =>
                      style({ letter_spacing: Number(e.target.value) })
                    }
                  />
                </label>
                <label>
                  Placement
                  <select
                    value={edits.captions.placement}
                    onChange={(e) =>
                      style({
                        placement: e.target.value as CaptionStyle["placement"],
                      })
                    }
                  >
                    {["top", "center", "bottom"].map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Animation
                  <select
                    value={edits.captions.animation}
                    onChange={(e) =>
                      style({
                        animation: e.target.value as CaptionStyle["animation"],
                      })
                    }
                  >
                    {["highlight", "fade", "none"].map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                </label>
              </div>
            </>
          ) : tab === "Transcript" ? (
            <div className="inspector-section">
              <h3>Every word, in sync.</h3>
              <p className="muted">
                Edit text and word timing. Times refer to the original video.
              </p>
              <div className="word-list">
                {edits.words.map((w, i) => (
                  <div className={current === w ? "current" : ""} key={i}>
                    <input
                      aria-label={`Word ${i + 1}`}
                      value={w.word}
                      maxLength={100}
                      onChange={(e) =>
                        change({
                          ...edits,
                          words: edits.words.map((x, j) =>
                            i === j ? { ...x, word: e.target.value } : x,
                          ),
                        })
                      }
                    />
                    <input
                      aria-label={`Word ${i + 1} start`}
                      type="number"
                      step={0.01}
                      min={0}
                      value={w.start}
                      onChange={(e) =>
                        change({
                          ...edits,
                          words: edits.words.map((x, j) =>
                            i === j
                              ? { ...x, start: Number(e.target.value) }
                              : x,
                          ),
                        })
                      }
                    />
                    <input
                      aria-label={`Word ${i + 1} end`}
                      type="number"
                      step={0.01}
                      min={w.start + 0.01}
                      value={w.end}
                      onChange={(e) =>
                        change({
                          ...edits,
                          words: edits.words.map((x, j) =>
                            i === j ? { ...x, end: Number(e.target.value) } : x,
                          ),
                        })
                      }
                    />
                  </div>
                ))}
              </div>
              <button type="button" className="button secondary" disabled={edits.words.length >= 10000}
                onClick={() => change({...edits, captions: {...edits.captions, enabled: true}, words: [...edits.words, {start: position, end: Math.min(position + .5, project.media.duration ?? clip.end), word: "Text"}]})}>Add caption at playhead</button>
              {!edits.words.length && (
                <p>No spoken words detected in this clip.</p>
              )}
            </div>
          ) : (
            <div className="inspector-section">
              <h3>A different perspective.</h3>
              <label>
                Reframe mode
                <select
                  value={edits.reframe}
                  onChange={(e) =>
                    change({
                      ...edits,
                      reframe: e.target.value as Edits["reframe"],
                    })
                  }
                >
                  <option value="auto">Automatic face tracking</option>
                  <option value="manual">Manual crop</option>
                  <option value="fit">Fit entire frame</option>
                </select>
              </label>
              <label>
                Horizontal focus
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={edits.focus_x}
                  onChange={(e) =>
                    change({ ...edits, focus_x: Number(e.target.value) })
                  }
                />
              </label>
              <small>Auto mode follows a consistent detected face and smooths movement during export. It does not identify the speaker. Focus provides a fallback when detection is lost; use Manual crop or Fit entire frame for crowded scenes. Browser framing is approximate.</small>
              <label>
                Export size
                <select
                  value={edits.resolution}
                  onChange={(e) =>
                    change({
                      ...edits,
                      resolution: Number(e.target.value) as 720 | 1080,
                    })
                  }
                >
                  <option value={1080}>1080 × 1920 maximum</option>
                  <option value={720}>720 × 1280 maximum</option>
                </select>
              </label>
              <label>
                Brand kit
                <select
                  value={edits.brand_kit_id || ""}
                  onChange={(e) => {
                    const kit = brands.find((b) => b.id === e.target.value);
                    if (kit)
                      change({
                        ...edits,
                        brand_kit_id: kit.id,
                        captions: kit.config.captions,
                        resolution: kit.config.resolution,
                        logo_asset_id: kit.config.logo_asset_id,
                      });
                    else change({ ...edits, brand_kit_id: null });
                  }}
                >
                  <option value="">No brand kit</option>
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Logo
                <select
                  value={edits.logo_asset_id || ""}
                  onChange={(e) =>
                    change({ ...edits, logo_asset_id: e.target.value || null })
                  }
                >
                  <option value="">No logo</option>
                  {assets
                    .filter((a) => a.kind === "logo")
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Headline / export note
                <input
                  value={edits.headline}
                  maxLength={240}
                  onChange={(e) =>
                    change({ ...edits, headline: e.target.value })
                  }
                />
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={!!edits.show_headline}
                  onChange={(e) =>
                    change({ ...edits, show_headline: e.target.checked })
                  }
                />
                Show headline on video
              </label>
              <fieldset className="editor-adjustments">
                <legend>Speed & transitions</legend>
                <label>Between-cut transition
                  <select value={edits.transition ?? "none"} onChange={(e) => change({...edits, transition: e.target.value as Edits["transition"]})}>
                    <option value="none">None · hard cut</option><option value="fade">Crossfade</option>
                    <option value="dissolve">Dissolve</option><option value="slideleft">Slide left</option>
                    <option value="slideright">Slide right</option><option value="wipeleft">Wipe left</option><option value="wiperight">Wipe right</option>
                  </select>
                </label>
                <label>Transition length · {edits.transition_duration ?? .3}s
                  <input type="range" min="0.1" max="1" step="0.1" disabled={!edits.transition || edits.transition === "none"}
                    value={edits.transition_duration ?? .3} onChange={(e) => change({...edits, transition_duration: Number(e.target.value)})} />
                </label>
                <p className="fine-print">Split into at least two cuts to add transitions. Transitions are export-only, with audio crossfades. Overlap shortens the export and its credit cost; duration is capped at half the shortest cut. Preview playback and trimming show source time without overlap.</p>
                <label>Video speed · {edits.speed ?? 1}×
                  <select value={edits.speed ?? 1} onChange={(e) => change({...edits, speed: Number(e.target.value)})}>
                    {[.25, .5, .75, 1, 1.25, 1.5, 2, 3, 4].map(rate => <option key={rate} value={rate}>{rate}×{rate === 1 ? " · Normal" : ""}</option>)}
                  </select>
                </label>
                <p className="fine-print">Applies to all cuts and exports. Audio pitch is preserved. Timeline trim positions remain in source seconds.</p>
                {(["fade_in", "fade_out"] as const).map(key => <label key={key}>{key === "fade_in" ? "Fade in" : "Fade out"} · {edits[key] ?? 0}s
                  <input type="range" min="0" max="2" step="0.1" value={edits[key] ?? 0} onChange={(e) => change({...edits, [key]: Number(e.target.value)})} />
                </label>)}
                <p className="fine-print">Fades affect picture and sound in exports, including overlays. Preview fades by rendering an export. Each fade is capped at half the finished duration.</p>
              </fieldset>
              <fieldset className="editor-adjustments">
                <legend>Picture adjustments</legend>
                <p className="fine-print">Applied to all cuts. Captions and logos keep their original colors.</p>
                <label>Quick look
                  <select value="" onChange={(e) => {
                    const looks: Record<string, Partial<Edits>> = {
                      natural: {brightness: 1, contrast: 1, saturation: 1},
                      vivid: {brightness: 1.03, contrast: 1.12, saturation: 1.3},
                      soft: {brightness: 1.06, contrast: .9, saturation: .85},
                      mono: {brightness: 1, contrast: 1.1, saturation: 0},
                    };
                    if (looks[e.target.value]) change({...edits, ...looks[e.target.value]});
                  }}>
                    <option value="" disabled>Apply a preset…</option>
                    <option value="natural">Natural</option><option value="vivid">Vivid</option>
                    <option value="soft">Soft</option><option value="mono">Black & white</option>
                  </select>
                </label>
                {(["brightness", "contrast", "saturation"] as const).map((key) => (
                  <label key={key}>{key[0].toUpperCase() + key.slice(1)} · {Math.round((edits[key] ?? 1) * 100)}%
                    <input type="range" min={key === "saturation" ? 0 : .5} max={key === "saturation" ? 2 : 1.5} step={.01}
                      value={edits[key] ?? 1} onChange={(e) => change({...edits, [key]: Number(e.target.value)})} />
                  </label>
                ))}
                <label className="checkbox"><input type="checkbox" checked={edits.flip_horizontal ?? false}
                  onChange={(e) => change({...edits, flip_horizontal: e.target.checked})} />Mirror video horizontally</label>
                <button type="button" className="button" onClick={() => change({...edits, brightness: 1, contrast: 1, saturation: 1, flip_horizontal: false})}>Reset picture</button>
              </fieldset>
              <button type="button" className="button" onClick={() => change({...edits, volume: (edits.volume ?? 1) === 0 ? 1 : 0})}>
                {(edits.volume ?? 1) === 0 ? "Unmute audio" : "Mute audio"}
              </button>
              <label>
                Audio volume
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={edits.volume ?? 1}
                  onChange={(e) =>
                    change({ ...edits, volume: Number(e.target.value) })
                  }
                />
              </label>
              <Link className="text-link" to="/studio/headlines">
                Explore headline suggestions
              </Link>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
function FilmStrip() {
  return (
    <span className="film-strip" aria-hidden="true">
      ▥ ▥ ▥
    </span>
  );
}
