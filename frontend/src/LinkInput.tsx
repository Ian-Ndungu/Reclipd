import { useEffect, useState } from "react";
import { LoaderCircle, RefreshCw, CheckCircle2 } from "lucide-react";
import type { Project } from "./types";
import { api, json, time } from "./api";
export type ImportPreview = {
  kind: "youtube" | "direct";
  video_id: string | null;
  title: string | null;
  thumbnail: string | null;
  channel: string | null;
  duration: number | null;
  available: boolean;
  message: string;
  metadata_error: string | null;
};
export function LinkInput({
  url,
  source,
  onUrl,
  onSource,
  onReady,
  onUpload,
  authenticated = true,
}: {
  authenticated?: boolean;
  url: string;
  source: string;
  onUrl: (value: string) => void;
  onSource: (value: string) => void;
  onReady: (ready: boolean) => void;
  onUpload: () => void;
}) {
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [connecting, setConnecting] = useState(false);
  useEffect(() => {
    if (authenticated)
      api<Project[]>("/projects")
        .then((p) => setProjects(p.filter((x) => x.status === "ready")))
        .catch(() => {});
  }, [authenticated]);
  useEffect(() => {
    setConfirmed(false);
    setSelected("");
  }, [url]);
  useEffect(() => {
    let active = true;
    setPreview(null);
    setError("");
    onReady(false);
    if (!authenticated || !url.trim()) {
      setBusy(false);
      return;
    }
    setBusy(true);
    const timer = setTimeout(() => {
      api<ImportPreview>("/imports/preview", {
        method: "POST",
        body: json({ url: url.trim(), source_url: source.trim() || null }),
      })
        .then((p) => {
          if (active) {
            setPreview(p);
            onReady(p.available);
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        })
        .finally(() => {
          if (active) setBusy(false);
        });
    }, 600);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [url, source, retry, onReady, authenticated]);
  return (
    <div className="link-input">
      <label>
        Video link
        <input
          name="url"
          type="url"
          required
          placeholder="Paste YouTube video URL here..."
          value={url}
          onChange={(e) => {
            onReady(false);
            onSource("");
            onUrl(e.target.value);
          }}
        />
      </label>
      <small>
        YouTube watch, Shorts and youtu.be links, or direct video files from
        approved HTTPS hosts.
      </small>
      {busy && (
        <p role="status">
          <LoaderCircle className="spin" size={16} /> Checking video metadata
          and source access…
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {!authenticated && (
        <p className="muted">
          Paste your link now. Sign in or create an account when you click
          Generate AI Clips.
        </p>
      )}
      {preview && (
        <section className="panel" aria-label="Video link preview">
          {preview.thumbnail && (
            <img
              src={preview.thumbnail}
              alt="Video thumbnail"
              referrerPolicy="no-referrer"
              style={{ width: 240, maxWidth: "100%", borderRadius: 12 }}
            />
          )}
          {preview.kind === "youtube" && preview.video_id && (
            <iframe
              title="YouTube embedded preview"
              src={`https://www.youtube-nocookie.com/embed/${preview.video_id}`}
              loading="lazy"
              allow="encrypted-media; picture-in-picture"
              allowFullScreen
              referrerPolicy="strict-origin-when-cross-origin"
            />
          )}
          {preview.title && <h3>{preview.title}</h3>}
          {preview.channel && <p>{preview.channel}</p>}
          {preview.duration != null && (
            <p>Duration: {time(preview.duration)}</p>
          )}
          {preview.kind === "youtube" && (
            <a
              className="text-link"
              href={`https://www.youtube.com/watch?v=${preview.video_id}`}
              target="_blank"
              rel="noreferrer"
            >
              Watch on YouTube
            </a>
          )}
          {preview.metadata_error && (
            <p role="status">{preview.metadata_error}</p>
          )}
          <p role="status">
            {preview.available && <CheckCircle2 size={16} />} {preview.message}
          </p>
        </section>
      )}
      {(preview?.kind === "youtube" || source) && (
        <label>
          Authorized source file URL (optional)
          <input
            type="url"
            value={source}
            onChange={(e) => {
              onReady(false);
              onSource(e.target.value);
            }}
            placeholder="https://approved-host.example/original.mp4"
          />
          <small>
            Provide the original footage you are authorized to use. YouTube
            metadata access does not grant access to the video file.
          </small>
        </label>
      )}
      {preview?.kind === "youtube" && authenticated && (
        <section className="source-connection">
          <h3>Connect your stored original</h3>
          <p className="muted">
            Choose the original footage for this YouTube video from your
            completed projects. Future imports of this link use that file
            automatically.
          </p>
          <label>
            Original video
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">Select an original…</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            This is the matching original and I have permission to process it.
          </label>
          <button
            type="button"
            className="button secondary"
            disabled={!selected || !confirmed || connecting}
            onClick={async () => {
              setConnecting(true);
              setError("");
              try {
                await api("/imports/connection", {
                  method: "PUT",
                  body: json({
                    url,
                    project_id: selected,
                    rights_confirmed: true,
                  }),
                });
                setRetry((n) => n + 1);
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setConnecting(false);
              }
            }}
          >
            {connecting ? "Connecting…" : "Connect original"}
          </button>
          {!projects.length && (
            <p className="muted">
              Upload an original first to add it to your library. No external
              cloud-storage account is connected.
            </p>
          )}
        </section>
      )}
      {(error ||
        preview?.metadata_error ||
        (preview && !preview.available)) && (
        <div className="button-row">
          <button
            type="button"
            className="button secondary small"
            disabled={busy}
            onClick={() => setRetry((n) => n + 1)}
          >
            <RefreshCw size={14} /> Retry check
          </button>
          <button
            type="button"
            className="button secondary small"
            onClick={onUpload}
          >
            Upload authorized source file
          </button>
        </div>
      )}
    </div>
  );
}
