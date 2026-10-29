import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, json } from "./api";
import {
  presets,
  defaultCaption,
  fontFamilies,
  type CaptionStyle,
  type Brand,
} from "./types";
import { readDraft, saveDraft } from "./draft";
import { AssetUploader, BrandAssetFields } from "./Assets";

function CaptionPreview({
  style,
  text,
}: {
  style: CaptionStyle;
  text: string;
}) {
  const words = (text.trim() || "Make every moment count.").split(/\s+/);
  return (
    <div className={`style-preview placement-${style.placement}`}>
      <span className="style-preview-label">Caption preview</span>
      <div
        style={{
          fontFamily: style.font,
          fontSize: Math.min(36, style.size * 0.4),
          fontWeight: style.weight,
          color: style.color,
          letterSpacing: (style.letter_spacing ?? 0) * 0.4,
          lineHeight: 1.15,
          textShadow: style.shadow ? "1px 2px 3px #000b" : "none",
          WebkitTextStroke: `${Math.min(1.2, style.stroke * 0.3)}px ${style.stroke_color || "#000000"}`,
          background: style.background
            ? style.background_color || "#111827"
            : "transparent",
          padding: style.background ? "8px 12px" : undefined,
        }}
      >
        {words.map((word, i) => (
          <span
            key={i}
            style={{
              color:
                i === words.length - 1 && style.animation === "highlight"
                  ? style.emphasis_color
                  : undefined,
            }}
          >
            {word}
            {i < words.length - 1 ? " " : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
export function CaptionGallery() {
  const [query, setQuery] = useState(""),
    [text, setText] = useState("Make every moment count."),
    [filter, setFilter] = useState("all");
  const navigate = useNavigate();
  const shown = presets.filter(
    (p) =>
      `${p.name} ${p.desc} ${p.style.font || defaultCaption.font}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === "all" ||
        (filter === "boxed"
          ? (p.style.background ?? defaultCaption.background)
          : (p.style.animation ?? defaultCaption.animation) !== "none")),
  );
  return (
    <div className="style-workspace">
      <header className="style-heading">
        <span className="eyebrow">CAPTION STUDIO</span>
        <h1>Find your signature style.</h1>
        <p className="muted">
          Explore {presets.length} presets. Preview your words, then refine
          every detail in the editor.
        </p>
      </header>
      <section className="panel style-toolbar">
        <label>
          Try your own words
          <input
            maxLength={100}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        <div className="form-grid">
          <label>
            Search styles or fonts
            <input
              type="search"
              placeholder="Try minimal, podcast, Inter…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label>
            Show
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">All styles</option>
              <option value="boxed">Background captions</option>
              <option value="animated">Animated presets</option>
            </select>
          </label>
        </div>
        <p className="fine-print">
          Typography previews are approximate. Word timing and animation apply
          to actual captions during export.
        </p>
      </section>
      <p role="status" className="muted">
        {shown.length} styles found
      </p>
      <div className="style-grid">
        {shown.map((p) => {
          const style = { ...defaultCaption, ...p.style };
          return (
            <article className="panel style-card" key={p.id}>
              <CaptionPreview style={style} text={text} />
              <h2>{p.name}</h2>
              <p className="muted">{p.desc}</p>
              <div className="style-tags">
                <span>{style.font}</span>
                <span>
                  {style.animation === "none" ? "Static" : style.animation}
                </span>
                <span>{style.placement}</span>
              </div>
              <button
                className="button secondary"
                onClick={() => {
                  saveDraft({ ...readDraft(), workflow: "ai", caption_preset: p.id });
                  navigate("/studio/new");
                }}
              >
                Use for new AI clips
              </button>
            </article>
          );
        })}
      </div>
      {!shown.length && (
        <section className="panel">
          <h2>No styles match</h2>
          <button
            className="button secondary"
            onClick={() => {
              setQuery("");
              setFilter("all");
            }}
          >
            Clear filters
          </button>
        </section>
      )}
    </div>
  );
}
export function BrandWorkspace() {
  const [brands, setBrands] = useState<Brand[]>([]),
    [editing, setEditing] = useState<Brand | null>(null),
    [name, setName] = useState(""),
    [style, setStyle] = useState<CaptionStyle>({ ...defaultCaption }),
    [resolution, setResolution] = useState<720 | 1080>(1080);
  const [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [removing, setRemoving] = useState<string | null>(null),
    [assetVersion, setAssetVersion] = useState(0);
  async function load() {
    try {
      setBrands(await api<Brand[]>("/brands"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  function edit(brand: Brand | null) {
    setEditing(brand);
    setName(brand?.name || "");
    setStyle({ ...defaultCaption, ...brand?.config.captions });
    setResolution(brand?.config.resolution || 1080);
    setError("");
  }
  return (
    <div className="style-workspace">
      <header className="style-heading">
        <span className="eyebrow">BRAND LIBRARY</span>
        <h1>Consistent, from the first frame.</h1>
        <p className="muted">
          Save your caption look, logo, fonts and export quality. Apply a kit in
          the clip editor.
        </p>
      </header>
      {error && (
        <p role="alert" className="error-box">
          {error}
        </p>
      )}
      <p role="status">{message}</p>
      <div className="brand-builder">
        <form
          className="panel"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            setMessage("");
            const form = new FormData(e.currentTarget);
            try {
              await api(editing ? `/brands/${editing.id}` : "/brands", {
                method: editing ? "PUT" : "POST",
                body: json({
                  name,
                  captions: {
                    ...style,
                    custom_font_id: form.get("custom_font_id") || null,
                  },
                  resolution,
                  logo_asset_id: form.get("logo_asset_id") || null,
                }),
              });
              setMessage(
                editing
                  ? "Brand kit updated. Existing clip edits are unchanged."
                  : "Brand kit saved. Apply it from the editor.",
              );
              edit(null);
              await load();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <h2>{editing ? "Edit brand kit" : "Create a brand kit"}</h2>
          <fieldset disabled={busy} className="brand-fields">
            <label>
              Kit name
              <input
                required
                maxLength={100}
                value={name}
                placeholder="Your signature style"
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              Start from a caption preset
              <select
                value={style.preset}
                onChange={(e) => {
                  const preset = presets.find((p) => p.id === e.target.value)!;
                  setStyle({
                    ...defaultCaption,
                    ...preset.style,
                    preset: preset.id as CaptionStyle["preset"],
                  });
                }}
              >
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="form-grid">
              <label>
                Font
                <select
                  value={style.font}
                  onChange={(e) =>
                    setStyle({
                      ...style,
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
                Size
                <input
                  type="number"
                  min={24}
                  max={140}
                  value={style.size}
                  onChange={(e) =>
                    setStyle({ ...style, size: Number(e.target.value) })
                  }
                />
              </label>
              <label>
                Text color
                <input
                  type="color"
                  value={style.color}
                  onChange={(e) =>
                    setStyle({ ...style, color: e.target.value })
                  }
                />
              </label>
              <label>
                Highlight color
                <input
                  type="color"
                  value={style.emphasis_color}
                  onChange={(e) =>
                    setStyle({ ...style, emphasis_color: e.target.value })
                  }
                />
              </label>
              <label>
                Placement
                <select
                  value={style.placement}
                  onChange={(e) =>
                    setStyle({
                      ...style,
                      placement: e.target.value as CaptionStyle["placement"],
                    })
                  }
                >
                  <option value="top">Top</option>
                  <option value="center">Center</option>
                  <option value="bottom">Bottom</option>
                </select>
              </label>
              <label>
                Export quality
                <select
                  value={resolution}
                  onChange={(e) =>
                    setResolution(Number(e.target.value) as 720 | 1080)
                  }
                >
                  <option value={1080}>1080p maximum</option>
                  <option value={720}>720p maximum</option>
                </select>
              </label>
            </div>
            <div className="form-grid">
              <BrandAssetFields
                key={`${editing?.id || "new"}:${assetVersion}`}
                logoId={editing?.config.logo_asset_id}
                fontId={editing?.config.captions.custom_font_id}
              />
            </div>
            <div className="row">
              <button className="button primary" disabled={busy}>
                {busy ? "Saving…" : editing ? "Update kit" : "Save kit"}
              </button>
              {editing && (
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => edit(null)}
                >
                  Cancel editing
                </button>
              )}
            </div>
          </fieldset>
        </form>
        <aside className="panel brand-live">
          <h2>Live preview</h2>
          <CaptionPreview
            style={style}
            text={name || "Make every moment count."}
          />
          <p className="fine-print">
            Built-in typography preview. Uploaded logos, custom fonts and
            animation are applied in the editor/export.
          </p>
        </aside>
      </div>
      <h2>
        Your brand kits <small>({brands.length})</small>
      </h2>
      {loading ? (
        <p role="status">Loading brand kits…</p>
      ) : !brands.length ? (
        <section className="panel">
          <h3>Your first signature starts here.</h3>
          <p className="muted">
            Create a kit above to reuse your look across clips.
          </p>
        </section>
      ) : (
        <div className="style-grid">
          {brands.map((b) => (
            <article className="panel style-card" key={b.id}>
              <CaptionPreview
                style={{ ...defaultCaption, ...b.config.captions }}
                text={b.name}
              />
              <h3>{b.name}</h3>
              <p className="muted">
                {b.config.captions.font} · {b.config.resolution}p
              </p>
              {removing === b.id ? (
                <>
                  <p>Delete this kit? Saved clip edits will remain.</p>
                  <div className="row">
                    <button
                      className="button secondary"
                      onClick={() => setRemoving(null)}
                    >
                      Keep kit
                    </button>
                    <button
                      className="button secondary"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        setError("");
                        try {
                          await api(`/brands/${b.id}`, { method: "DELETE" });
                          if (editing?.id === b.id) edit(null);
                          setRemoving(null);
                          setMessage("Brand kit deleted.");
                          await load();
                        } catch (e) {
                          setError((e as Error).message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Confirm delete
                    </button>
                  </div>
                </>
              ) : (
                <div className="row">
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => {
                      edit(b);
                      window.scrollTo({ top: 0, behavior: "auto" });
                    }}
                  >
                    Edit kit
                  </button>
                  <button
                    className="text-link"
                    disabled={busy}
                    onClick={() => setRemoving(b.id)}
                  >
                    Delete
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
      <AssetUploader onUploaded={() => setAssetVersion((v) => v + 1)} />
    </div>
  );
}
