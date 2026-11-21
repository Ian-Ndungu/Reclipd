import {Onboarding} from "./Onboarding";
import {validateFields,focusError,type FieldErrors} from "./formErrors";
import {AccountSecurity, PasswordRecovery} from "./AccountSecurity";
import {useTheme} from "./Theme";
import {CreditOverview, DashboardCredits, type CreditUsage} from "./Credits";
import {Payments} from "./Payments";
import {DeleteNoticeProvider, useDeleteNotice} from "./DeleteNotice";
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
  useSearchParams,
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
  Eye,
  EyeOff,
  HardDrive,
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
import {CaptionGallery, BrandWorkspace} from "./StyleStudio";
import {StudioPreferences, readStudioDefaults} from "./StudioPreferences";
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
      <DeleteNoticeProvider><AppContent /></DeleteNoticeProvider>
    </ThemeProvider>
  );
}
function AppContent() {
  const {setTheme}=useTheme();
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true);
  const refresh = async () => {
    try {
      const account=await api<User>("/me");
      let prefs=account.preferences || {};
      if(!Object.keys(prefs).length){
        const local=readStudioDefaults(account.id);
        let theme: "light"|"dark"|"system"="light";
        try {const saved=window.localStorage.getItem("reclipd-theme"); if(saved==="dark"||saved==="system") theme=saved;} catch {}
        try {prefs=await api("/me/preferences",{method:"PUT",body:json({...local,theme})});account.preferences=prefs;} catch {}
      }
      try {window.localStorage.setItem(`reclipd-defaults:${account.id}`,JSON.stringify(prefs));} catch {}
      setTheme(prefs.theme || "light");
      setUser(account);
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
        <Route path="/forgot-password" element={<PasswordRecovery />} />
        <Route path="/reset-password" element={<PasswordRecovery reset />} />
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
                to={user.preferences?.onboarding_completed === false ? "/studio/welcome" : readDraft().mode ? "/studio/new" : "/studio"}
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
          <Route index element={user?.preferences?.onboarding_completed === false ? <Navigate to="/studio/welcome" replace/> : <Dashboard />} />
          <Route path="welcome" element={<Onboarding onComplete={refresh}/>} />
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
            <p>90 trial minutes, then 60 free minutes monthly.</p>
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
            <span /> Your creative workspace
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
  const [authParams] = useSearchParams();
  const [fieldErrors,setFieldErrors]=useState<FieldErrors>({});
  const [showPassword, setShowPassword] = useState(false);
  const [register, setRegister] = useState(authParams.get("mode") === "register"),
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
        <small>RECLIPD AI Studio / Create More. Edit Less.</small>
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
        <form noValidate onChange={e=>{if(!(e.target instanceof HTMLInputElement))return;const name=e.target.name;setFieldErrors(old=>({...old,[name]:""}));setError("");}}
          onSubmit={async (e) => {
            e.preventDefault();
            const invalid=validateFields(e.currentTarget);setFieldErrors(invalid);
            if(Object.keys(invalid).length){focusError(e.currentTarget,invalid);return;}
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
              const text=(err as Error).message;
              if(text==="Email or password is incorrect") setFieldErrors({password:text});
              else if(text.includes("already exists")) setFieldErrors({email:text});
              else setError(text);
            } finally {
              setBusy(false);
            }
          }}
        >
          {register && (
            <label>
              Your name
              <input name="name" autoComplete="name" required maxLength={100} aria-invalid={!!fieldErrors.name} aria-describedby={fieldErrors.name?"auth-name-error":undefined}/>
              {fieldErrors.name&&<span id="auth-name-error" className="field-error" role="alert">{fieldErrors.name}</span>}
            </label>
          )}
          <label>
            Email address
            <input name="email" type="email" autoComplete="email" required aria-invalid={!!fieldErrors.email} aria-describedby={fieldErrors.email?"auth-email-error":undefined}/>
            {fieldErrors.email&&<span id="auth-email-error" className="field-error" role="alert">{fieldErrors.email}</span>}
          </label>
          <div className="password-field">
            <label htmlFor="auth-password">Password</label>
            <div className="password-input">
            <input
              id="auth-password"
              aria-invalid={!!fieldErrors.password}
              aria-describedby={fieldErrors.password?"auth-password-error":undefined}
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete={register ? "new-password" : "current-password"}
              required
              minLength={10}
              maxLength={128}
              placeholder="At least 10 characters"
            />
            <button
              type="button"
              className="password-toggle"
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-controls="auth-password"
              onClick={() => setShowPassword((visible) => !visible)}
            >
              {showPassword ? <EyeOff size={20} aria-hidden="true" /> : <Eye size={20} aria-hidden="true" />}
            </button>
            </div>
            {fieldErrors.password&&<p id="auth-password-error" className="field-error" role="alert">{fieldErrors.password}</p>}
          </div>
          {!register && <div className="auth-recovery-link"><Link to="/forgot-password">Forgot password?</Link></div>}
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
          <button onClick={() => { setRegister(!register); setShowPassword(false); setFieldErrors({}); setError(""); }}>
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
  return { items, error, loading, setItems };
}
function Dashboard() {
  const {confirmDelete, notify} = useDeleteNotice();
  const { user, refresh } = useAuth();
  useEffect(() => {
    void refresh();
  }, []);
  const { items, error, loading, setItems } = useProjects();
  const [deleteError, setDeleteError] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
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
              <small>Total tracked usage</small>
            </strong>
          </section>
        </div>
      </div>
      <DashboardCredits/>
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
      <ErrorBox error={deleteError || error} />
      {loading ? (
        <p className="muted">Loading your projects…</p>
      ) : filtered.length ? (
        <div className="project-grid">
          {filtered.map((p) => (
            <article className="project-card" key={p.id}>
              <Link to={`/studio/projects/${p.id}`} style={{display: "block"}}>
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
              <div style={{padding: "0 20px 16px"}}>
                <button className="button secondary" disabled={!!deletingId || p.status === "cancelling"}
                  aria-label={`${["queued", "processing", "cancelling"].includes(p.status) ? "Cancel clipping" : "Delete project"} ${p.name}`}
                  title={!['ready', 'failed', 'cancelled'].includes(p.status) ? "Stop clipping at the next safe checkpoint" : "Delete project"}
                  onClick={async () => {
                    if (["queued", "processing"].includes(p.status)) {
                      setDeletingId(p.id); setDeleteError("");
                      try { const updated = await api<Project>(`/projects/${p.id}/cancel`, {method: "POST"}); setItems(previous => previous.map(item => item.id === p.id ? updated : item)); }
                      catch (e) { setDeleteError((e as Error).message); }
                      finally { setDeletingId(null); }
                      return;
                    }
                    if (!await confirmDelete(p.name)) return;
                    setDeletingId(p.id); setDeleteError("");
                    try {
                      await api(`/projects/${p.id}`, {method: "DELETE"});
                      notify(`“${p.name}” was removed from your workspace.`);
                      setItems(previous => previous.filter(project => project.id !== p.id));
                    } catch (e) { setDeleteError((e as Error).message); }
                    finally { setDeletingId(null); }
                  }}>
                  {deletingId === p.id ? "Please wait…" : ["queued", "processing", "cancelling"].includes(p.status) ? (p.status === "cancelling" ? "Cancelling…" : "Cancel clipping") : "Delete project"}
                </button>
              </div>
            </article>
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
  const [draft] = useState(() => ({...readStudioDefaults(user?.id), ...readDraft()}));
  const [workflow, setWorkflow] = useState<"ai" | "manual">(draft.workflow || "ai");
  const [url, setUrl] = useState(draft.url || "");
  const [source, setSource] = useState(draft.source || "");
  const [driveFile, setDriveFile] = useState<DriveFile | null>(null);
  const [uploadPercent, setUploadPercent] = useState(0);
  const [uploadLimits, setUploadLimits] = useState<{max_bytes: number; max_seconds: number} | null>(null);
  useEffect(() => {
    api<{max_bytes: number; max_seconds: number}>("/upload-limits").then(setUploadLimits).catch(() => {});
  }, []);
  const [filePreview, setFilePreview] = useState("");
  const [linkReady, setLinkReady] = useState(false);
  const [mode, setMode] = useState(draft.workflow === "manual" ? "upload" : draft.mode || "link"),
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
        title="How would you like to create?"
        description="Let AI find the highlights, or make your own cuts. One account and one credit balance."
      />
      <form
        className="new-project"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          const f = new FormData(e.currentTarget);
          const config = {
            workflow,
            resolution: draft.resolution,
            content_category: String(f.get("content_category") || "auto"),
            instructions: String(f.get("instructions") || ""),
            caption_preset: String(f.get("caption_preset") || "bold"),
            aspect_ratio: "9:16",
            language: String(f.get("language") || "") || null,
            clip_count: Number(f.get("clip_count") || 5),
            min_duration: Number(f.get("min_duration") || 15),
            max_duration: Number(f.get("max_duration") || 60),
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
            } else if (mode === "drive") {
              if (!driveFile) throw Error("Connect Google Drive and choose a video first");
              p = await api("/integrations/google-drive/projects", {
                method: "POST",
                body: json({
                  file_id: driveFile.id,
                  name: f.get("name") || driveFile.name,
                  rights_confirmed: true,
                  config,
                }),
              });
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
          <div className="workflow-choice" aria-label="Creation mode">
            <button type="button" aria-pressed={workflow === "ai"} disabled={busy} onClick={() => setWorkflow("ai")}>
              <strong>AI Clips</strong><span>Find highlights automatically. Credits use source duration.</span>
            </button>
            <button type="button" aria-pressed={workflow === "manual"} disabled={busy} onClick={() => {setWorkflow("manual"); setMode("upload");}}>
              <strong>Manual Editor</strong><span>Choose every cut yourself. Pay credits only for new exports.</span>
            </button>
          </div>
          {workflow === "manual" && <p className="fine-print">Upload and edit free. Each new export uses 1 credit minute per finished minute, calculated to the second. Unchanged exports are reused. Same balance and packages; no separate subscription. Start with up to 3 minutes, then select any part of your source.</p>}
          <div className="tabs">
            <button
              type="button"
              disabled={workflow === "manual"}
              className={mode === "link" ? "active" : ""}
              onClick={() => setMode("link")}
            >
              <Link2 size={16} /> Paste Video Link
            </button>
            <button
              type="button"
              disabled={workflow === "manual"}
              className={mode === "drive" ? "active" : ""}
              onClick={() => setMode("drive")}
            >
              <HardDrive size={16} /> Google Drive
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
          ) : mode === "drive" ? (
            <GoogleDriveInput value={driveFile} onChange={setDriveFile} />
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
          <fieldset disabled={workflow === "manual"} hidden={workflow === "manual"} className="ai-options">
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
              placeholder="Focus on product launches. Avoid sponsorships. 01:00–05:00."
            />
            <small>
              Describe topics or names to prioritize. Use “Avoid sponsorships.” to exclude a topic, or “01:00–05:00” to limit the source range. Without a language model, matching uses transcript keywords. Set clip length and caption style using the controls; instructions do not translate speech or add footage.
            </small>
          </label>
          </fieldset>
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
                {uploadPercent === 100 ? " · creating project…" : " · progress saved automatically"}
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
            disabled={busy || (!!user && mode === "link" && !linkReady) || (!!user && mode === "drive" && !driveFile)}
          >
            {busy ? (
              <>
                <LoaderCircle className="spin" size={18} />
                Creating your project…
              </>
            ) : (
              <>
                {workflow === "manual" ? "Open Manual Editor" : "Generate AI Clips"} <ArrowRight size={18} />
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

type DriveFile = {
  id: string;
  name: string;
  size: number;
  mime_type: string;
  duration_ms: number | null;
  supported: boolean;
};

function GoogleDriveInput({ value, onChange }: { value: DriveFile | null; onChange: (file: DriveFile | null) => void }) {
  const [status, setStatus] = useState<{enabled: boolean; connected: boolean} | null>(null);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const reload = async () => {
    setLoading(true); setError("");
    try {
      const current = await api<{enabled: boolean; connected: boolean}>("/integrations/google-drive/status");
      setStatus(current);
      if (current.connected) setFiles(await api<DriveFile[]>("/integrations/google-drive/files"));
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  };
  useEffect(() => { void reload(); }, []);
  if (loading && !status) return <p role="status"><LoaderCircle className="spin" size={16}/> Checking Google Drive…</p>;
  if (!status?.enabled) return <section className="panel"><h3>Connect Google Drive</h3><p className="muted">Google Drive imports need a server-side OAuth client before they can be enabled.</p><ErrorBox error={error || "Google Drive is not configured yet."}/></section>;
  if (!status.connected) return <section className="panel"><h3>Connect Google Drive</h3><p className="muted">Choose a video you own or are authorized to edit. RECLIPD reads only the video you select.</p><button type="button" className="button primary" onClick={async () => { try { const data = await api<{authorization_url: string}>("/integrations/google-drive/authorize", {method:"POST"}); window.location.assign(data.authorization_url); } catch (e) { setError((e as Error).message); } }}>Connect Google Drive</button><ErrorBox error={error}/></section>;
  return <section className="panel"><div className="row"><div><h3>Choose a Google Drive video</h3><p className="muted">Only videos within the current upload limit are available.</p></div><button type="button" className="button secondary small" onClick={() => void reload()} disabled={loading}><RefreshCw size={14}/> Refresh</button></div>{loading ? <p role="status"><LoaderCircle className="spin" size={16}/> Loading your videos…</p> : <label>Video<select value={value?.id || ""} onChange={(e) => onChange(files.find((file) => file.id === e.target.value) || null)}><option value="">Select a video…</option>{files.map((file) => <option key={file.id} value={file.id} disabled={!file.supported}>{file.name}{file.duration_ms ? ` · ${time(file.duration_ms / 1000)}` : ""}{file.supported ? "" : " · exceeds limit"}</option>)}</select></label>}{!loading && !files.length && <p className="muted">No supported video files found in Drive.</p>}<ErrorBox error={error}/></section>;
}
function ProjectPage() {
  const {confirmDelete, notify} = useDeleteNotice();
  const { id } = useParams();
  const [connectionError, setConnectionError] = useState("");
  const navigate = useNavigate();
  const [deleting, setDeleting] = useState(false);
  const [p, setP] = useState<Project | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = () =>
      api<Project>(`/projects/${id}`)
        .then((x) => {
          if (active) { setP(x); setConnectionError(""); }
        })
        .catch((e) => {
          if (active) setConnectionError(`Unable to refresh progress. Reconnecting automatically. ${e.message}`);
        });
    load();
    const timer = setInterval(load, 2500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id]);
  useEffect(() => {
    if (p?.status === "ready" && p.config?.workflow === "manual" && p.clips?.[0])
      navigate(`/studio/clips/${p.clips[0].id}`, {replace: true});
  }, [p, navigate]);
  if (!p) return <ErrorBox error={connectionError || error || "Loading project…"} />;
  return (
    <>
      <Link to="/studio" className="muted">← All projects</Link>
      <PageTitle
        eyebrow="PROJECT / HIGHLIGHTS"
        title={p.name}
        description={`${time(p.media.duration)} source · ${p.media.width || "—"} × ${p.media.height || "—"}`}
        action={<div className="row">{["queued", "processing", "cancelling"].includes(p.status) ? <span className="processing-status" role="status"><LoaderCircle className="spin-slow" size={18}/>{p.status === "cancelling" ? "Cancelling…" : `${p.progress}% · ${p.stage}`}</span> : <Badge status={p.status} />}<button
          className="button secondary"
          disabled={deleting || p.status === "cancelling"}
          title={!['ready', 'failed', 'cancelled'].includes(p.status) ? "Stop clipping at the next safe checkpoint" : "Delete project"}
          onClick={async () => {
            if (["queued", "processing"].includes(p.status)) {
              setDeleting(true);
              try { setP(await api(`/projects/${p.id}/cancel`, {method: "POST"})); }
              catch (e) { setError((e as Error).message); }
              finally { setDeleting(false); }
              return;
            }
            if (!await confirmDelete(p.name)) return;
            setDeleting(true);
            try {
              await api(`/projects/${p.id}`, {method: "DELETE"});
                      notify(`“${p.name}” was removed from your workspace.`);
              navigate("/studio", {replace: true});
            } catch (e) { setError((e as Error).message); setDeleting(false); }
          }}
        >{deleting ? "Please wait…" : ["queued", "processing", "cancelling"].includes(p.status) ? "Cancel clipping" : "Delete project"}</button></div>}
      />
      <ErrorBox error={error || connectionError || p.error || ""} />
      {p.status !== "ready" ? (
        <section className="panel processing">
          <div className="processing-icon">
            {["failed", "cancelled"].includes(p.status) ? (
              <RefreshCw size={32} />
            ) : (
              <Scissors className="spin-slow" size={32} />
            )}
          </div>
          <h2>
            {["failed", "cancelled"].includes(p.status) ? p.status === "cancelled" ? "Clipping cancelled" : "This needs another take." : p.stage}
          </h2>
          <p>
            {["failed", "cancelled"].includes(p.status)
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
          {["failed", "cancelled"].includes(p.status) && (
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
function Captions() { return <CaptionGallery />; }
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
function Brands() { return <BrandWorkspace />; }

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
        title="Make the studio yours."
        description="Manage your profile, appearance and creative defaults."
      />
      <section className="panel narrow settings-section">
        <h2>Appearance</h2>
        <p className="muted">Choose light, dark, or follow your device.</p>
        <ThemeSelect onSave={async theme=>{
          await api("/me/preferences",{method:"PUT",body:json({theme})});
          await refresh();
        }}/>
      </section>
      <StudioPreferences key={user?.id} userId={user?.id} synced onSaved={refresh} />
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
      <AccountSecurity onDeleted={async ()=>{
        if(user) window.localStorage.removeItem(`reclipd-defaults:${user.id}`);
        window.sessionStorage.removeItem("reclipd-draft");
        await refresh();
      }}/>
    </>
  );
}
function Billing() {
  const [usage, setUsage] = useState<(CreditUsage & {limit_seconds:number|null;billing_enabled:boolean}) | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = () => {
    setLoading(true); setError("");
    api<NonNullable<typeof usage>>("/usage").then(setUsage).catch(e => setError(e.message)).finally(() => setLoading(false));
  };
  useEffect(()=>{load();const timer=setInterval(load,60000);return()=>clearInterval(timer);}, []);
  const unlimited = usage?.limit_seconds === null;
  const remaining = usage?.unlimited ? null : usage?.available_seconds ?? (usage?.limit_seconds == null ? null : Math.max(0, usage.limit_seconds - usage.used_seconds));
  return <>
    <PageTitle eyebrow="YOUR ACCOUNT" title="Plan & usage" description="Know your allowance, track processing, and stay in control."
      action={<button className="button secondary" disabled={loading} onClick={load}><RefreshCw size={16}/> Refresh usage</button>}/>
    <ErrorBox error={error}/>
    {!usage ? <section className="panel" aria-busy={loading}>{loading ? "Loading your plan…" : "Usage is unavailable. Try refreshing."}</section> : <>
      {typeof usage.trial_seconds === 'number' && <CreditOverview usage={usage}/>}
      <div className="billing-overview">
        <section className="panel billing-plan">
          <span className="eyebrow">CURRENT PLAN</span><h2>{unlimited ? "Unlimited workspace" : usage.plan}</h2>
          <p>{unlimited ? "Your account has no processing-minute cap." : "Your plan includes the full editing workflow. Paid minute packs are optional."}</p>
          <div className="billing-price">No active subscription<span>No recurring charges configured</span></div>
          <div className="billing-features"><span><Check size={16}/> AI clipping workflow</span><span><Check size={16}/> Caption styles and editor</span><span><Check size={16}/> MP4 exports</span></div>
          <Link to="/studio/new" className="button primary">Create a project <ArrowRight size={16}/></Link>
        </section>
        <section className="panel billing-meter"><span className="eyebrow">PROCESSING ALLOWANCE</span>
          <h2>{unlimited ? "Unlimited" : `${Math.floor((remaining || 0) / 60)} minutes left`}</h2>
          <p>{Math.ceil(usage.used_seconds / 60)} minutes used{unlimited ? " · tracked for your records" : ` of ${usage.limit_seconds! / 60}`}</p>
          {!unlimited && <progress aria-label="Processing allowance used" max={usage.limit_seconds || 1} value={Math.min(usage.used_seconds, usage.limit_seconds || 1)}/>}
          {remaining === 0 && <p className="error">Allowance reached. Existing clips can still be edited and exported.</p>}
          <p className="muted">Trial minutes expire after seven days. Free minutes refresh monthly without rollover; paid minutes expire 365 days after purchase.</p>
          <Link to="/studio">View your projects <ArrowRight size={16}/></Link>
        </section>
      </div>
      <div className="billing-overview">
        <section className="panel"><h3>How usage is counted</h3><p>Source-video duration is reserved when processing starts, using trial, then monthly free, then earliest-expiring paid credits. Failed or cancelled processing returns minutes to their original buckets; expiry dates do not change. Deleting a completed project does not refund usage.</p><p>Editing, headline regeneration and exports do not use processing minutes. Upload-size, video-duration and concurrent-job limits still apply.</p></section>
        <section className="panel"><h3>Payments & invoices</h3><p>Paystack test checkout supports one-time minute packs. Live payments, recurring subscriptions and tax invoices are not enabled.</p><Link to="/studio/settings">Account settings <ArrowRight size={16}/></Link><p className="muted">Test transactions are simulations, not receipts for real payments.</p></section>
      </div>
      <section className="panel" style={{padding:28,marginBottom:24}}><h3>Processing history</h3>
      {!usage.processing_history?.length ? <p>No processing activity yet.</p> : usage.processing_history.map(r=><article key={r.project_id} style={{padding:'12px 0',borderBottom:'1px solid var(--border)'}}><strong>{r.name}</strong><p>{(r.seconds/60).toFixed(2)} minutes · {r.status} · {new Date(r.created_at).toLocaleString()}</p></article>)}
      </section>
      <Payments unlimited={unlimited} onVerified={load}/>
    </>}
  </>;
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
