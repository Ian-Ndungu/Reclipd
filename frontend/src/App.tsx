import { PremiumLanding } from "./Landing";
import { ThemeProvider, ThemeSelect } from "./Theme";
import { readDraft, saveDraft, clearDraft } from "./draft";
import { LinkInput } from "./LinkInput";
import {
  useEffect,
  useState,
  createContext,
  useContext,
  type ReactNode,
} from "react";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  Scissors,
  LayoutDashboard,
  Plus,
  ArrowUpRight,
  ArrowRight,
  Upload,
  Link2,
  Film,
  Type,
  Palette,
  Download,
  Settings,
  CreditCard,
  Shield,
  LogOut,
  ChevronRight,
  Search,
  Check,
  Clock,
  LoaderCircle,
  RefreshCw,
  FolderOpen,
  Play,
  Command,
  Menu,
  X,
} from "lucide-react";
import { api, json, time, uploadProject } from "./api";
import {
  type User,
  type Project,
  type Clip,
  type ExportJob,
  type Brand,
  defaultCaption,
  presets,
} from "./types";
import { Editor } from "./Editor";
import { AssetUploader, BrandAssetFields } from "./Assets";
const Auth = createContext<{ user: User | null; refresh: () => Promise<void> }>(
  { user: null, refresh: async () => {} },
);
export const useAuth = () => useContext(Auth);
export function ErrorBox({ error }: { error: string }) {
  return error ? (
    <div className="error" role="alert">
      {error}
    </div>
  ) : null;
}
export function Empty({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Film size={28} />
      </div>
      <h3>{title}</h3>
      <p>{detail}</p>
      {action}
    </div>
  );
}
export function Badge({ status }: { status: string }) {
  return (
    <span className={`badge ${status}`}>
      <span />
      {status}
    </span>
  );
}
export function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
export default function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}
function AppContent() {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true);
  const refresh = async () => {
    try {
      setUser(await api<User>("/me"));
    } catch {
      setUser(null);
    }
  };
  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, []);
  if (loading)
    return (
      <div className="loading">
        <LoaderCircle className="spin" /> Opening your studio
      </div>
    );
  return (
    <Auth.Provider value={{ user, refresh }}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route
          path="/new"
          element={
            user ? (
              <Navigate to="/studio/new" replace />
            ) : (
              <div className="guest-project">
                <header>
                  <Logo />
                </header>
                <main>
                  <NewProject />
                </main>
              </div>
            )
          }
        />
        <Route
          path="/auth"
          element={
            user ? (
              <Navigate
                to={readDraft().mode ? "/studio/new" : "/studio"}
                replace
              />
            ) : (
              <Authentication />
            )
          }
        />
        <Route
          path="/studio"
          element={user ? <Shell /> : <Navigate to="/auth" />}
        >
          <Route index element={<Dashboard />} />
          <Route path="new" element={<NewProject />} />
          <Route path="projects/:id" element={<ProjectPage />} />
          <Route path="clips/:id" element={<Editor />} />
          <Route path="captions" element={<Captions />} />
          <Route path="headlines" element={<Headlines />} />
          <Route path="brands" element={<Brands />} />
          <Route path="exports" element={<Exports />} />
          <Route path="settings" element={<Account />} />
          <Route path="billing" element={<Billing />} />
          <Route path="admin" element={<Admin />} />
        </Route>
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Auth.Provider>
  );
}
import { Outlet } from "react-router-dom";
export function Logo() {
  return (
    <Link to="/" className="logo">
      <span className="logo-mark">
        <Scissors size={20} />
      </span>{" "}
      RECLIPD <span className="logo-ai">AI STUDIO</span>
    </Link>
  );
}
function Shell() {
  const [collapsed, setCollapsed] = useState(false);
  const { user, refresh } = useAuth();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <button
        className="mobile-toggle icon-button"
        aria-label="Toggle navigation"
        aria-expanded={open}
        aria-controls="studio-navigation"
        onClick={() => setOpen(!open)}
      >
        {open ? <X /> : <Menu />}
      </button>
      <aside
        id="studio-navigation"
        className={open ? "sidebar open" : "sidebar"}
      >
        <Logo />
        <div className="workspace">
          <span className="avatar">{user?.name.slice(0, 1).toUpperCase()}</span>
          <div>
            {user?.name}'s workspace<small>Personal workspace</small>
          </div>
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav onClick={() => setOpen(false)}>
          {[
            ["/studio", LayoutDashboard, "Overview"],
            ["/studio/new", Plus, "New project"],
            ["/studio/exports", Download, "Exports"],
          ].map(([to, Icon, label]) => (
            <NavLink end to={to as string} key={to as string}>
              {typeof Icon !== "string" && <Icon size={18} />} {label as string}
            </NavLink>
          ))}
          <div className="nav-caption">CREATIVE TOOLS</div>
          <NavLink to="/studio/captions">
            <Type size={18} />
            Caption styles<span className="tiny-tag">20</span>
          </NavLink>
          <NavLink to="/studio/headlines">
            <Command size={18} />
            AI headlines
          </NavLink>
          <NavLink to="/studio/brands">
            <Palette size={18} />
            Brand kits
          </NavLink>
          <div className="nav-caption">MANAGE</div>
          <NavLink to="/studio/billing">
            <CreditCard size={18} />
            Plan & usage
          </NavLink>
          <NavLink to="/studio/settings">
            <Settings size={18} />
            Settings
          </NavLink>
          {user?.is_admin && (
            <NavLink to="/studio/admin">
              <Shield size={18} />
              Operations
            </NavLink>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="plan-card">
            <div>
              Room for your next idea <span>FREE</span>
            </div>
            <p>120 processing minutes to explore.</p>
            <Link to="/studio/billing">
              View your usage <ArrowUpRight size={14} />
            </Link>
          </div>
          <button
            className="user-button"
            onClick={async () => {
              await api("/auth/logout", { method: "POST" });
              await refresh();
              navigate("/");
            }}
          >
            <span className="avatar">{user?.name[0]}</span>
            <span>
              {user?.name}
              <small>Sign out</small>
            </span>
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <div className="main-area">
        <header className="topbar">
          <button
            className="icon-button sidebar-desktop-toggle"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            onClick={() => setCollapsed((v) => !v)}
          >
            <Menu size={16} />
          </button>
          <span>
            Workspace <ChevronRight size={14} /> AI Studio
          </span>
          <span className="local-label">
            <span /> Development workspace
          </span>
        </header>
        <main>
          <Outlet />
        </main>
        <footer>
          RECLIPD AI Studio <span>Made for the moments that matter.</span>
        </footer>
      </div>
    </div>
  );
}
function Landing() {
  return <PremiumLanding />;
}
function Authentication() {
  const [register, setRegister] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const { refresh } = useAuth();
  return (
    <div className="auth-page">
      <div className="auth-aside">
        <Logo />
        <div>
          <div className="eyebrow">THE CREATOR’S CUT</div>
          <h1>
            More story.
            <br />
            Less scrolling
            <br />
            through footage.
          </h1>
          <p>Your next great moment starts here.</p>
        </div>
        <small>RECLIPD AI Studio / Development preview</small>
      </div>
      <div className="auth-form">
        <div className="eyebrow">WELCOME TO YOUR STUDIO</div>
        <h1>{register ? "Create your account" : "Welcome back."}</h1>
        <p>
          {register
            ? "A space for your stories, from first cut to final frame."
            : "Pick up where your creativity left off."}
        </p>
        <ErrorBox error={error} />
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            const form = new FormData(e.currentTarget);
            try {
              await api(`/auth/${register ? "register" : "login"}`, {
                method: "POST",
                body: json(Object.fromEntries(form)),
              });
              await refresh();
            } catch (err) {
              setError((err as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {register && (
            <label>
              Your name
              <input name="name" autoComplete="name" required maxLength={100} />
            </label>
          )}
          <label>
            Email address
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete={register ? "new-password" : "current-password"}
              required
              minLength={10}
              maxLength={128}
              placeholder="At least 10 characters"
            />
          </label>
          <button className="button primary" disabled={busy}>
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : register ? (
              "Create account"
            ) : (
              "Enter studio"
            )}
            <ArrowRight size={16} />
          </button>
        </form>
        <p className="auth-switch">
          {register ? "Already have an account?" : "New to RECLIPD?"}{" "}
          <button onClick={() => setRegister(!register)}>
            {register ? "Sign in" : "Create an account"}
          </button>
        </p>
      </div>
    </div>
  );
}
function useProjects() {
  const [items, setItems] = useState<Project[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    api<Project[]>("/projects")
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
  return { items, error, loading };
}
function Dashboard() {
  const { user, refresh } = useAuth();
  useEffect(() => {
    void refresh();
  }, []);
  const { items, error, loading } = useProjects();
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all");
  const filtered = items.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) &&
      (filter === "all" || p.status === filter),
  );
  return (
    <>
      <PageTitle
        eyebrow="YOUR CREATIVE WORKSPACE"
        title={`Let’s make something, ${user?.name.split(" ")[0]}.`}
        description="Big ideas. Standout moments. All in one place."
        action={
          <Link to="/studio/new" className="button primary">
            <Plus size={18} />
            New project
          </Link>
        }
      />
      <section className="create-banner">
        <div className="banner-copy">
          <span className="eyebrow">LONG VIDEO. NEW POSSIBILITIES.</span>
          <h2>
            Your best moments.
            <br />
            Ready for their close-up.
          </h2>
          <p>Turn one video into a collection of clips worth sharing.</p>
          <Link to="/studio/new" className="button light">
            Create your first cut <ArrowUpRight size={17} />
          </Link>
          <div className="format-tags">
            <span>YouTube Shorts</span>
            <i /> <span>Instagram Reels</span>
            <i /> <span>TikTok</span>
          </div>
        </div>
        <div className="banner-art" aria-hidden="true">
          <div className="frame frame-back">
            <div className="frame-line" />
            <div className="frame-line short" />
          </div>
          <div className="frame frame-front">
            <div className="frame-top">
              <span>THE CREATOR’S CUT</span>
              <Scissors size={16} />
            </div>
            <div className="abstract-orbit">
              <div />
              <div />
              <div />
            </div>
            <div className="frame-caption">
              MAKE EVERY
              <br />
              <span>MOMENT COUNT.</span>
            </div>
            <div className="frame-bottom">
              <Play size={12} fill="currentColor" />
              <div />
              00:28
            </div>
          </div>
          <div className="floating-chip">
            <Check size={14} /> Made for vertical
          </div>
        </div>
      </section>
      <div className="stats-grid">
        <div>
          <span className="stat-icon">
            <FolderOpen size={20} />
          </span>
          <section>
            <p>Total projects</p>
            <strong>
              {items.length}
              <small>Your creative library</small>
            </strong>
          </section>
        </div>
        <div>
          <span className="stat-icon">
            <Scissors size={20} />
          </span>
          <section>
            <p>Ready to edit</p>
            <strong>
              {items.filter((p) => p.status === "ready").length}
              <small>Projects with highlights</small>
            </strong>
          </section>
        </div>
        <div>
          <span className="stat-icon">
            <Clock size={20} />
          </span>
          <section>
            <p>Processing minutes</p>
            <strong>
              {Math.ceil((user?.used_seconds || 0) / 60)}
              <small>of 120 available</small>
            </strong>
          </section>
        </div>
      </div>
      <div className="section-heading">
        <div>
          <h2>
            Your projects <span>{items.length}</span>
          </h2>
          <p>Every story starts somewhere.</p>
        </div>
        <label className="search">
          <Search size={16} />
          <input
            placeholder="Search projects…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search projects"
          />
        </label>
      </div>
      <div className="tabs">
        {[
          ["all", "All projects"],
          ["ready", "Ready to edit"],
          ["processing", "Processing"],
          ["failed", "Needs attention"],
        ].map(([value, label]) => (
          <button
            key={value}
            className={filter === value ? "active" : ""}
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>
      <ErrorBox error={error} />
      {loading ? (
        <p className="muted">Loading your projects…</p>
      ) : filtered.length ? (
        <div className="project-grid">
          {filtered.map((p) => (
            <Link
              className="project-card"
              to={`/studio/projects/${p.id}`}
              key={p.id}
            >
              <div className="project-visual">
                <Film size={36} />
                <Badge status={p.status} />
                <span>{time(p.media.duration)}</span>
              </div>
              <div className="project-info">
                <h3>{p.name}</h3>
                <p>
                  {new Date(p.created_at).toLocaleDateString()}{" "}
                  <ArrowUpRight size={16} />
                </p>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <Empty
          title={
            search ? "No matching projects" : "Your next story starts here"
          }
          detail={
            search
              ? "Try a different project name."
              : "Drop in a long video. Discover the moments that deserve their own spotlight."
          }
          action={
            <Link to="/studio/new" className="button secondary">
              <Plus size={16} />
              Create a project
            </Link>
          }
        />
      )}
      <div className="bottom-hint">
        <span>
          <Type size={20} /> Give your words a signature look.
        </span>
        <Link to="/studio/captions">
          Explore caption styles <ArrowRight size={16} />
        </Link>
      </div>
    </>
  );
}
function NewProject() {
  const { user } = useAuth();
  const [draft] = useState(readDraft);
  const [url, setUrl] = useState(draft.url || "");
  const [source, setSource] = useState(draft.source || "");
  const [uploadPercent, setUploadPercent] = useState(0);
  const [uploadLimits, setUploadLimits] = useState<{max_bytes: number; max_seconds: number} | null>(null);
  useEffect(() => {
    api<{max_bytes: number; max_seconds: number}>("/upload-limits").then(setUploadLimits).catch(() => {});
  }, []);
  const [filePreview, setFilePreview] = useState("");
  const [linkReady, setLinkReady] = useState(false);
  const [mode, setMode] = useState(draft.mode || "link"),
    [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [drag, setDrag] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    if (!file) {
      setFilePreview("");
      return;
    }
    const value = URL.createObjectURL(file);
    setFilePreview(value);
    return () => URL.revokeObjectURL(value);
  }, [file]);
  return (
    <>
      <PageTitle
        eyebrow="A NEW BEGINNING"
        title="Let’s find your best moments."
        description="Start with a video. We’ll help you find the story inside."
      />
      <form
        className="new-project"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          const f = new FormData(e.currentTarget);
          const config = {
            content_category: String(f.get("content_category") || "auto"),
            instructions: String(f.get("instructions") || ""),
            caption_preset: String(f.get("caption_preset") || "bold"),
            aspect_ratio: "9:16",
            language: String(f.get("language") || "") || null,
            clip_count: Number(f.get("clip_count")),
            min_duration: Number(f.get("min_duration")),
            max_duration: Number(f.get("max_duration")),
          };
          if (!user) {
            saveDraft({
              url,
              source,
              mode,
              name: String(f.get("name") || ""),
              ...config,
            });
            navigate("/auth");
            setBusy(false);
            return;
          }
          try {
            let p: Project;
            if (mode === "upload") {
              if (!file) throw Error("Choose a video first");
              f.set("file", file);
              f.set("config", json(config));
              f.set("rights_confirmed", "true");
              p = await uploadProject<Project>(f, setUploadPercent);
            } else {
              p = await api("/projects/import", {
                method: "POST",
                body: json({
                  name: f.get("name"),
                  url: url.trim(),
                  source_url: source.trim() || null,
                  rights_confirmed: true,
                  config,
                }),
              });
            }
            clearDraft();
            navigate(`/studio/projects/${p.id}`);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <section className="panel">
          <div className="tabs">
            <button
              type="button"
              className={mode === "link" ? "active" : ""}
              onClick={() => setMode("link")}
            >
              <Link2 size={16} /> Paste Video Link
            </button>
            <button
              type="button"
              className={mode === "upload" ? "active" : ""}
              onClick={() => setMode("upload")}
            >
              <Upload size={16} /> Upload Video
            </button>
          </div>
          {mode === "upload" ? (
            <label
              className={`drop-zone ${drag ? "drag" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDrag(true);
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDrag(false);
                setFile(e.dataTransfer.files[0] || null);
              }}
            >
              <Upload size={30} />
              <h3>{file ? file.name : "Drag your video here"}</h3>
              <p>
                {file
                  ? `${(file.size / 1024 / 1024).toFixed(1)} MB · Click to change`
                  : "or click to browse your files"}
              </p>
              <small>MP4, MOV, MKV, WebM{uploadLimits?.max_bytes ? ` · Up to ${Math.round(uploadLimits.max_bytes / 1024 / 1024)} MB · ${Math.round(uploadLimits.max_seconds / 60)} minutes` : ""}</small>
              <input
                type="file"
                accept=".mp4,.mov,.mkv,.webm"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                aria-label="Choose video"
              />
            </label>
          ) : (
            <LinkInput
              authenticated={!!user}
              url={url}
              source={source}
              onUrl={setUrl}
              onSource={setSource}
              onReady={setLinkReady}
              onUpload={() => setMode("upload")}
            />
          )}
          <label>
            Project name
            <input
              name="name"
              placeholder="e.g. The conversation worth sharing"
              defaultValue={draft.name}
              required={!!user}
              maxLength={200}
            />
          </label>
        </section>
        <section className="panel">
          <h3>Shape your highlights</h3>
          <p className="muted">
            We’ll rank candidates using signals found in your video.
          </p>
          <div className="form-grid">
            <label>
              Number of clips
              <select name="clip_count" defaultValue={draft.clip_count || 5}>
                {[1, 3, 5, 8, 10].map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </label>
            <label>
              Minimum seconds
              <input
                name="min_duration"
                type="number"
                defaultValue={draft.min_duration || 15}
                min={5}
                max={120}
                required
              />
            </label>
            <label>
              Maximum seconds
              <input
                name="max_duration"
                type="number"
                defaultValue={draft.max_duration || 60}
                min={5}
                max={180}
                required
              />
            </label>
          </div>
          <div className="form-grid">
            <label>
              Content category
              <select
                name="content_category"
                defaultValue={draft.content_category || "auto"}
              >
                {[
                  "auto",
                  "podcast",
                  "interview",
                  "education",
                  "product",
                  "commentary",
                ].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            <label>
              Caption style
              <select
                name="caption_preset"
                defaultValue={draft.caption_preset || "bold"}
              >
                {presets.map((p) => (
                  <option value={p.id} key={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Aspect ratio
              <select name="aspect_ratio">
                <option>9:16 · Vertical</option>
              </select>
            </label>
            <label>
              Spoken language
              <select name="language" defaultValue={draft.language || ""}>
                <option value="">Detect automatically</option>
                {[
                  ["en", "English"],
                  ["es", "Spanish"],
                  ["fr", "French"],
                  ["sw", "Swahili"],
                  ["de", "German"],
                ].map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Clipping instructions
            <textarea
              name="instructions"
              maxLength={1000}
              rows={3}
              defaultValue={draft.instructions}
              placeholder="Focus on the discussion about product launches…"
            />
            <small>
              Uses literal keyword relevance in local fallback mode; a
              configured local LLM can interpret the brief. Captions stay in the
              spoken language.
            </small>
          </label>
          {mode === "upload" && filePreview && (
            <video
              className="upload-preview"
              src={filePreview}
              controls
              preload="metadata"
            />
          )}
          {mode === "upload" && busy && (
            <div role="status">
              <progress max="100" value={uploadPercent} />
              <p>
                {uploadPercent}% uploaded
                {uploadPercent === 100 ? " · creating project…" : ""}
              </p>
            </div>
          )}
          <label className="checkbox">
            <input type="checkbox" required={!!user} />I own this media or have
            permission to process and use it. Any source URL I supply contains
            the footage I am authorized to use.
          </label>
          <ErrorBox error={error} />
          <button
            className="button primary"
            disabled={busy || (!!user && mode === "link" && !linkReady)}
          >
            {busy ? (
              <>
                <LoaderCircle className="spin" size={18} />
                Creating your project…
              </>
            ) : (
              <>
                Generate AI Clips <ArrowRight size={18} />
              </>
            )}
          </button>
          <p className="fine-print">
            Your original video stays intact. Every edit is reversible.
          </p>
        </section>
      </form>
    </>
  );
}
function ProjectPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [deleting, setDeleting] = useState(false);
  const [p, setP] = useState<Project | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = () =>
      api<Project>(`/projects/${id}`)
        .then((x) => {
          if (active) setP(x);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    load();
    const timer = setInterval(load, 2500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id]);
  if (!p) return <ErrorBox error={error || "Loading project…"} />;
  return (
    <>
      <PageTitle
        eyebrow="PROJECT / HIGHLIGHTS"
        title={p.name}
        description={`${time(p.media.duration)} source · ${p.media.width || "—"} × ${p.media.height || "—"}`}
        action={<div className="row"><Badge status={p.status} /><button
          className="button secondary"
          disabled={deleting || !["ready", "failed"].includes(p.status)}
          title={!['ready', 'failed'].includes(p.status) ? "Wait for processing to finish before deleting" : "Delete project"}
          onClick={async () => {
            if (!window.confirm(`Delete “${p.name}”? Its clips and exports will be permanently removed. This cannot be undone.`)) return;
            setDeleting(true);
            try {
              await api(`/projects/${p.id}`, {method: "DELETE"});
              navigate("/studio", {replace: true});
            } catch (e) { setError((e as Error).message); setDeleting(false); }
          }}
        >{deleting ? "Deleting…" : "Delete project"}</button></div>}
      />
      <ErrorBox error={error || p.error || ""} />
      {p.status !== "ready" ? (
        <section className="panel processing">
          <div className="processing-icon">
            {p.status === "failed" ? (
              <RefreshCw size={32} />
            ) : (
              <Scissors className="spin-slow" size={32} />
            )}
          </div>
          <h2>
            {p.status === "failed" ? "This needs another take." : p.stage}
          </h2>
          <p>
            {p.status === "failed"
              ? "Your source is saved. Resolve the error, then try again."
              : "Long videos can take several minutes on this local CPU. You can leave this page; processing continues in the background."}
          </p>
          <progress max={100} value={p.progress} />
          <strong>{p.progress}%</strong>
          <div className="processing-steps">
            {["Inspect", "Transcribe", "Analyze", "Rank", "Ready"].map(
              (s, i) => (
                <span key={s} className={p.progress > i * 20 ? "done" : ""}>
                  {p.progress > (i + 1) * 20 ? (
                    <Check size={15} />
                  ) : (
                    <span>{i + 1}</span>
                  )}
                  {s}
                </span>
              ),
            )}
          </div>
          {p.status === "failed" && (
            <button
              className="button primary"
              onClick={async () => {
                try {
                  setP(await api(`/projects/${id}/retry`, { method: "POST" }));
                  setError("");
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Retry processing
            </button>
          )}
        </section>
      ) : (
        <>
          <div className="notice">
            <Command size={20} />
            <div>
              <strong>Highlights, with a reason.</strong>
              <p>
                Scores are relative editorial signals, not predictions of views.{" "}
                {p.analysis.ranking_method}
              </p>
              {p.analysis.warnings?.map((w) => (
                <small key={w}>{w}</small>
              ))}
            </div>
          </div>
          <div className="section-heading">
            <h2>
              Your highlights <span>{p.clips?.length || 0}</span>
            </h2>
            <span className="muted">Ranked by relevance</span>
          </div>
          <div className="clip-grid">
            {p.clips?.map((c, i) => (
              <ClipCard c={c} index={i} key={c.id} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
function ClipCard({ c, index }: { c: Clip; index: number }) {
  const [preview, setPreview] = useState(false);
  const [previewError, setPreviewError] = useState(false);
  return (
    <article className="clip-card">
      <div className="clip-preview">
        {preview ? (
          <video
            src={`/api/clips/${c.id}/preview?start=${c.start}&end=${c.end}`}
            controls
            autoPlay
            playsInline
            preload="none"
            onError={() => setPreviewError(true)}
          />
        ) : (
          <button
            className="button secondary"
            onClick={() => {
              setPreview(true);
              setPreviewError(false);
            }}
          >
            <Play size={20} /> Play clip
          </button>
        )}
        {previewError && (
          <button
            className="button secondary"
            onClick={() => setPreview(false)}
          >
            Preview unavailable · Retry
          </button>
        )}
        <span className="clip-index">0{index + 1}</span>
        <span className="duration">{time(c.end - c.start)}</span>
      </div>
      <div className="clip-body">
        <div className="score">
          <span>{Math.round(c.score)} / 100</span> Signal score
        </div>
        <h3>{c.title}</h3>
        <p>{c.description}</p>
        <details>
          <summary>Why this moment?</summary>
          <ul>
            {c.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </details>
        <div className="clip-bottom">
          <span>
            {time(c.start)} – {time(c.end)}
          </span>
          <Link className="button secondary small" to={`/studio/clips/${c.id}`}>
            Open editor <ArrowUpRight size={14} />
          </Link>
        </div>
      </div>
    </article>
  );
}
function Captions() {
  return (
    <>
      <PageTitle
        eyebrow="MAKE IT SOUND LIKE YOU. LOOK LIKE YOU."
        title="Words with personality."
        description="Twenty starting points. Endless ways to make them yours in the clip editor."
      />
      <div className="preset-grid">
        {presets.map((p, i) => (
          <article className="preset-card" key={p.id}>
            <div
              className={`caption-example preset-${p.id}`}
              style={{ fontFamily: p.style.font, color: p.style.color }}
            >
              <small>{String(i + 1).padStart(2, "0")} / CAPTION PRESET</small>
              <div>
                This is your
                <br />
                <em style={{ color: p.style.emphasis_color }}>moment.</em>
              </div>
              <span>9:16 · WORD-LEVEL CAPTIONS</span>
            </div>
            <h3>{p.name}</h3>
            <p>{p.desc}</p>
            <Link to="/studio" className="text-link">
              Choose a clip to style <ArrowUpRight size={15} />
            </Link>
          </article>
        ))}
      </div>
      <div className="notice">
        Nineteen built-in font families are included in the media worker.
        Caption styling is applied at export; the editor preview is an
        approximation.
      </div>
    </>
  );
}
function Headlines() {
  const { items, error } = useProjects();
  const [clips, setClips] = useState<Clip[]>([]),
    [selected, setSelected] = useState(""),
    [tone, setTone] = useState("concise"),
    [count, setCount] = useState(5),
    [maxCharacters, setMaxCharacters] = useState(90),
    [drafts, setDrafts] = useState<Record<string, string>>({}),
    [feedback, setFeedback] = useState(""),
    [busy, setBusy] = useState(false),
    [err, setErr] = useState("");
  const clip = clips.find((c) => c.id === selected);
  return (
    <div className="headline-workspace">
      <PageTitle
        eyebrow="FIND THE RIGHT WORDS"
        title="Find the right first impression."
        description="Explore a few angles. Refine your words. Stay true to the moment."
      />
      <ErrorBox error={error || err} />
      <p role="status" className="headline-feedback">{feedback}</p>
      <section className="panel headline-controls">
        <div className="headline-section-label"><span>01 · Your source</span><small>Start with a finished clip</small></div>
        <div className="form-grid">
          <label>
            Project
            <select
              defaultValue=""
              disabled={busy}
              onChange={async (e) => {
                const projectId = e.target.value;
                setClips([]); setSelected(""); setErr(""); setFeedback(""); setBusy(true);
                try {
                  const p = await api<Project>(`/projects/${projectId}`);
                  setClips(p.clips || []);
                  setSelected(p.clips?.[0]?.id || "");
                } catch (e) {
                  setErr((e as Error).message);
                } finally { setBusy(false); }
              }}
            >
              <option value="" disabled>
                Select a project
              </option>
              {items
                .filter((p) => p.status === "ready")
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Highlight
            <select
              value={selected}
              disabled={busy}
              onChange={(e) => { setSelected(e.target.value); setFeedback(""); }}
            >
              <option value="" disabled>
                Select a clip
              </option>
              {clips.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="headline-section-label"><span>02 · Your direction</span><small>Specific beats sensational</small></div>
        <div className="form-grid">
          <label>
            Tone
            <select value={tone} onChange={(e) => setTone(e.target.value)}>
              {[
                "concise",
                "informative",
                "funny",
                "dramatic",
                "viral",
                "curiosity",
                "minimal",
              ].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label>Suggestions<select value={count} onChange={e => setCount(Number(e.target.value))}>
            {[3,5,8,10].map(n => <option key={n} value={n}>{n} options</option>)}
          </select></label>
          <label>Headline length<select value={maxCharacters} onChange={e => setMaxCharacters(Number(e.target.value))}>
            <option value={60}>Short · up to 60 characters</option>
            <option value={90}>Balanced · up to 90 characters</option>
            <option value={140}>Detailed · up to 140 characters</option>
          </select></label>
        </div>
        <button
          className="button primary"
          disabled={!selected || busy}
          onClick={async () => {
            setBusy(true); setErr(""); setFeedback("");
            const clipId = selected;
            try {
              const hs = await api<Clip["headlines"]>(
                `/clips/${clipId}/headlines`,
                { method: "POST", body: json({ tone, count, max_characters: maxCharacters }) },
              );
              setClips(cs => cs.map(c => c.id === clipId ? {...c, headlines: hs} : c));
              setDrafts({});
              setFeedback(`${hs.length} suggestions ready. Review each against the clip before using it.`);
            } catch (e) {
              setErr((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Working…" : clip?.headlines.length ? "Generate new options" : "Generate headlines"}
          <Command size={16} />
        </button>
      </section>
      <div className="headline-results-heading"><h2>Your shortlist</h2><span>{clip?.headlines.length || 0} suggestions</span></div>
      {clip && !clip.headlines.length && !busy && <p className="panel muted">Choose a tone and generate your first shortlist. You can edit any suggestion before copying or adding it to the video.</p>}
      {busy && <p role="status" className="panel">Preparing your shortlist…</p>}
      <div className="headline-list headline-cards">
        {clip?.headlines.map((h, i) => (
          <article key={i}>
            <span className="headline-number">{String(i + 1).padStart(2, "0")}</span>
            <div>
              <label className="headline-draft-label">Headline {i + 1}
                <textarea rows={2} maxLength={140} value={drafts[`${clip.id}:${i}`] ?? h.text}
                  onChange={e => setDrafts(d => ({...d, [`${clip.id}:${i}`]: e.target.value}))} />
              </label>
              <span className="headline-character-count">{(drafts[`${clip.id}:${i}`] ?? h.text).length} characters</span>
              <small>
                {h.tone} · {h.source.includes("local LLM") ? "AI draft · review facts" : "Transcript-based template"}
              </small>
            </div>
            <button
              className="button secondary small"
              onClick={async () => {
                if (!clip || !(drafts[`${clip.id}:${i}`] ?? h.text).trim()) return;
                try {
                  const updated = await api<Clip>(`/clips/${clip.id}`, {
                    method: "PUT",
                    body: json({
                      revision: clip.revision,
                      edits: {
                        ...clip.edits,
                        headline: drafts[`${clip.id}:${i}`] ?? h.text,
                        show_headline: true,
                      },
                    }),
                  });
                  setClips((cs) =>
                    cs.map((c) => (c.id === updated.id ? updated : c)),
                  );
                  setErr(""); setFeedback(`Headline ${i + 1} applied to the video overlay.`);
                } catch (e) {
                  setErr((e as Error).message);
                }
              }}
            >
              Use as overlay
            </button>
            <button
              className="button secondary small"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(drafts[`${clip.id}:${i}`] ?? h.text);
                  setFeedback(`Headline ${i + 1} copied.`);
                } catch {
                  setErr(
                    "Copy unavailable. Select and copy the headline text.",
                  );
                }
              }}
            >
              Copy
            </button>
          </article>
        ))}
      </div>
      {clip && (
        <section className="panel">
          <h3>Keep the source in view</h3>
          <p className="muted">Check names, numbers and outcomes before publishing. A headline should make sense without adding a claim the clip does not support.</p>
          <label>Retained transcript
            <textarea readOnly rows={5} value={clip.edits.words.filter(w => clip.edits.segments.some(s => w.start < s.end && w.end > s.start)).map(w => w.word).join(" ")} />
          </label>
          <p className="headline-quality-note">Transcript templates are available without a language model. A connected model can suggest more natural angles; it still needs your editorial review. Correct the transcript in the editor first if recognition missed a name or changed the meaning.</p>
          <Link
            className="button secondary small"
            to={`/studio/clips/${clip.id}`}
          >
            Edit selected clip
          </Link>
        </section>
      )}
      {!clip && (
        <Empty
          title="A good headline starts with a real moment"
          detail="Choose a processed project and a highlight above."
        />
      )}
    </div>
  );
}
function Brands() {
  const [brands, setBrands] = useState<Brand[]>([]),
    [error, setError] = useState("");
  const load = () =>
    api<Brand[]>("/brands")
      .then(setBrands)
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  return (
    <>
      <PageTitle
        eyebrow="CONSISTENTLY YOU"
        title="Your brand, in every frame."
        description="Save caption typography, colors, and export resolution for reuse."
      />
      <ErrorBox error={error} />
      <form
        className="panel"
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          try {
            await api("/brands", {
              method: "POST",
              body: json({
                name: f.get("name"),
                captions: {
                  ...defaultCaption,
                  font: f.get("font"),
                  emphasis_color: f.get("color"),
                  custom_font_id: f.get("custom_font_id") || null,
                },
                logo_asset_id: f.get("logo_asset_id") || null,
                resolution: Number(f.get("resolution")),
              }),
            });
            await load();
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        <div className="form-grid">
          <label>
            Kit name
            <input
              name="name"
              required
              placeholder="My signature style"
              maxLength={100}
            />
          </label>
          <label>
            Font
            <select name="font">
              {[
                "DejaVu Sans",
                "Liberation Sans",
                "Liberation Serif",
                "Liberation Mono",
              ].map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
          </label>
          <label>
            Accent
            <input name="color" type="color" defaultValue="#4D8DFF" />
          </label>
          <label>
            Export
            <select name="resolution" defaultValue="1080">
              <option value="1080">1080 × 1920 maximum</option>
              <option value="720">720 × 1280 maximum</option>
            </select>
          </label>
          <BrandAssetFields />
        </div>
        <button className="button primary">
          <Plus size={16} />
          Save brand kit
        </button>
      </form>
      <div className="project-grid">
        {brands.map((b) => (
          <article className="panel brand-card" key={b.id}>
            <span
              className="brand-swatch"
              style={{ background: b.config.captions.emphasis_color }}
            >
              Aa
            </span>
            <h3>{b.name}</h3>
            <p>
              {b.config.captions.font} · {b.config.resolution}p
            </p>
            <button
              className="text-link"
              onClick={async () => {
                try {
                  await api(`/brands/${b.id}`, { method: "DELETE" });
                  load();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Delete kit
            </button>
          </article>
        ))}
      </div>
      <AssetUploader />
      <p className="muted">
        Apply a saved kit in the clip editor. Uploaded logos render in the top
        right. Reload this page after uploading to add new assets to a kit.
      </p>
    </>
  );
}
function Exports() {
  const [items, setItems] = useState<ExportJob[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    const load = () =>
      api<ExportJob[]>("/exports")
        .then(setItems)
        .catch((e) => setError(e.message));
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);
  return (
    <>
      <PageTitle
        eyebrow="READY FOR THE WORLD"
        title="Your finished cuts."
        description="MP4 exports, ready for Shorts, Reels, and TikTok."
      />
      <ErrorBox error={error} />
      {items.length ? (
        <div className="export-list">
          {items.map((e) => (
            <article className="panel export-row" key={e.id}>
              <div className="stat-icon">
                <Film size={22} />
              </div>
              <div>
                <h3>RECLIPD — {e.id.slice(0, 8)}</h3>
                <p>{new Date(e.created_at).toLocaleString()}</p>
                {e.error && <ErrorBox error={e.error} />}
              </div>
              <Badge status={e.status} />
              {["queued", "processing"].includes(e.status) && (
                <progress max="100" value={e.progress} />
              )}
              <Link to={`/studio/clips/${e.clip_id}`} className="text-link">
                Edit
              </Link>
              {e.status === "complete" && (
                <a
                  className="button primary small"
                  href={`/api/exports/${e.id}/download`}
                >
                  <Download size={15} />
                  Download
                </a>
              )}
            </article>
          ))}
        </div>
      ) : (
        <Empty
          title="The final cut lives here"
          detail="Open a highlight, make it yours, then export your finished video."
        />
      )}
    </>
  );
}
function Account() {
  const { user, refresh } = useAuth();
  const [message, setMessage] = useState("");
  return (
    <>
      <PageTitle
        title="Your account."
        description="The details behind your creative workspace."
      />
      <section className="panel narrow">
        <h3>Appearance</h3>
        <p className="muted">Choose light, dark, or follow your device.</p>
        <ThemeSelect />
      </section>
      <form
        className="panel narrow"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api("/me", {
              method: "PUT",
              body: json({ name: new FormData(e.currentTarget).get("name") }),
            });
            await refresh();
            setMessage("Profile saved.");
          } catch (e) {
            setMessage((e as Error).message);
          }
        }}
      >
        <label>
          Display name
          <input
            name="name"
            defaultValue={user?.name}
            required
            maxLength={100}
          />
        </label>
        <label>
          Email
          <input value={user?.email} disabled />
        </label>
        <button className="button primary">Save changes</button>
        <p role="status">{message}</p>
      </form>
      <p className="muted">
        Email changes, password reset, and account deletion are not available in
        this local development release.
      </p>
    </>
  );
}
function Billing() {
  const [usage, setUsage] = useState<{
      used_seconds: number;
      limit_seconds: number;
    } | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    api<typeof usage>("/usage")
      .then(setUsage)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <PageTitle
        eyebrow="SPACE TO EXPERIMENT"
        title="Your plan & usage."
        description="A development allowance for trying the full processing workflow."
      />
      <ErrorBox error={error} />
      <section className="panel billing-panel">
        <span className="eyebrow">DEVELOPMENT FREE</span>
        <h2>Make your next idea happen.</h2>
        <p>Local processing · All caption presets · Vertical MP4 exports</p>
        <div className="usage-number">
          {Math.ceil((usage?.used_seconds || 0) / 60)}{" "}
          <span>/ {(usage?.limit_seconds || 7200) / 60} minutes</span>
        </div>
        <progress
          max={usage?.limit_seconds || 7200}
          value={usage?.used_seconds || 0}
        />
        <p className="muted">
          Successful source processing counts once. Failed processing is
          refunded. Editing and exports do not use processing minutes.
        </p>
        <div className="notice">
          No payment details needed. Paid plans and payment-provider integration
          are not enabled.
        </div>
      </section>
    </>
  );
}
function Admin() {
  const [data, setData] = useState<{
      users: number;
      projects: Project[];
    } | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    api<{ users: number; projects: Project[] }>("/admin")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <PageTitle
        title="Studio operations."
        description="Recent project state and recoverable failures."
      />
      <ErrorBox error={error} />
      {data && (
        <>
          <p>{data.users} registered users</p>
          {data.projects.map((p) => (
            <article className="panel export-row" key={p.id}>
              <div>
                <h3>{p.name}</h3>
                <p>{p.stage}</p>
                <small>{p.error}</small>
              </div>
              <Badge status={p.status} />
              <span>{p.progress}%</span>
              {p.status === "failed" && (
                <button
                  className="button secondary small"
                  onClick={async () => {
                    try {
                      await api(`/admin/projects/${p.id}/retry`, {
                        method: "POST",
                      });
                      setData({
                        ...data,
                        projects: data.projects.map((x) =>
                          x.id === p.id
                            ? { ...x, status: "queued", progress: 0 }
                            : x,
                        ),
                      });
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Retry
                </button>
              )}
            </article>
          ))}
        </>
      )}
    </>
  );
}
