import { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  ArrowRight,
  Upload,
  Scissors,
  Type,
  ScanFace,
  Sparkles,
  Film,
  Palette,
  Download,
  Wand2,
  BarChart3,
  Check,
} from "lucide-react";
import { Logo, useAuth } from "./App";
import { saveDraft } from "./draft";
import { presets, defaultCaption } from "./types";
export function PremiumLanding() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [showHandoff, setShowHandoff] = useState(false);
  const handoff = useRef<HTMLHeadingElement>(null);
  const linkInput = useRef<HTMLInputElement>(null);
  useEffect(() => { if (showHandoff) handoff.current?.focus(); }, [showHandoff]);
  const [url, setUrl] = useState("");
  const [preset, setPreset] = useState(0);
  const [after, setAfter] = useState(true);
  const style = { ...defaultCaption, ...presets[preset].style };
  const features = [
    [
      "Find the moments",
      "Transcript, scene and audio signals rank highlights, with an explanation for every score.",
      Scissors,
    ],
    [
      "Make it short",
      "Turn selected moments into vertical cuts without changing your original.",
      Film,
    ],
    [
      "Every word, in sync",
      "Word-level transcription and editable synchronized captions.",
      Type,
    ],
    [
      "Make your type yours",
      "Explore caption templates, built-in families and custom font uploads.",
      Palette,
    ],
    [
      "Find your headline",
      "Get transcript-grounded suggestions in multiple tones.",
      Sparkles,
    ],
    [
      "Keep the subject in frame",
      "Face-guided cropping, fit mode and manual framing controls.",
      ScanFace,
    ],
    [
      "Understand the score",
      "Editorial signals help you compare candidates. Scores do not predict views.",
      BarChart3,
    ],
    [
      "Your finishing room",
      "Trim, split, undo and fine-tune each moment in the editor.",
      Wand2,
    ],
    [
      "Build your signature",
      "Save colors, fonts and logos in reusable brand kits.",
      Palette,
    ],
    [
      "Ready for the feed",
      "Export H.264 MP4 up to 1080 × 1920 when the source supports it.",
      Download,
    ],
  ] as const;
  return (
    <div className="premium-landing">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="public-header">
        <Logo />
        <nav aria-label="Main navigation">
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <a href="#pricing">Pricing</a>
          {!user && <Link to="/auth">Login</Link>}
        </nav>
        {user ? (
          <details className="landing-account">
            <summary>
              <span className="avatar" aria-hidden="true">{user.name.slice(0, 1).toUpperCase()}</span>
              Your studio <ArrowUpRight size={15} />
            </summary>
            <div className="landing-account-panel">
              <span className="eyebrow">Welcome back</span>
              <strong>{user.name}</strong>
              <p>You’re signed in. Pick up where you left off or start a new project.</p>
              <Link className="button primary" to="/studio">Continue to studio <ArrowRight size={16} /></Link>
              <Link className="button" to="/studio/new">Create a new project</Link>
            </div>
          </details>
        ) : (
          <Link className="button primary" to="/new">
            Get started <ArrowUpRight size={15} />
          </Link>
        )}
      </header>
      <main id="main-content">
        <section className="premium-hero">
          <div className="eyebrow">Create More. Edit Less.</div>
          <h1>
            Turn Long Videos Into
            <br />
            <span>Scroll-Stopping Shorts.</span>
          </h1>
          <p>
            Transform long videos into engaging short clips with AI-powered
            highlights, automatic captions, smart reframing and beautifully
            customizable editing tools.
          </p>
          <form
            className="hero-input"
            onSubmit={(e) => {
              e.preventDefault();
              saveDraft({ url, mode: "link" });
              if (user) navigate("/studio/new");
              else setShowHandoff(true);
            }}
          >
            <label className="sr-only" htmlFor="hero-link">
              Video link
            </label>
            <input
              ref={linkInput}
              id="hero-link"
              type="url"
              required
              placeholder="Paste a video link here…"
              value={url}
              onChange={(e) => {setUrl(e.target.value); setShowHandoff(false);}}
            />
            <button className="button primary">
              Generate AI Clips <ArrowRight size={16} />
            </button>
          </form>
          {showHandoff && !user && (
            <section className="clip-signin-handoff" aria-labelledby="clip-signin-title">
              <span className="eyebrow">Your next step</span>
              <h2 id="clip-signin-title" ref={handoff} tabIndex={-1}>Let’s give your clips a home.</h2>
              <p>Sign in or create an account to save your projects and clips. We’ll keep your video link ready so you can review your settings before processing starts.</p>
              <div className="handoff-actions">
                <Link className="button primary" to="/auth?mode=register">Create an account <ArrowRight size={16} /></Link>
                <Link className="button secondary" to="/auth">Sign in to continue</Link>
              </div>
              <button className="text-link" onClick={() => {setShowHandoff(false); linkInput.current?.focus();}}>Back to my video link</button>
            </section>
          )}
          <button
            className="text-link upload-link"
            onClick={() => {
              saveDraft({ mode: "upload" });
              navigate("/new");
            }}
          >
            <Upload size={15} /> Or upload a video
          </button>
          <p className="source-note">
            MP4 · MOV · MKV · WebM · Approved video URLs
            <br />
            Only process videos you own or have permission to use. Public
            YouTube retrieval depends on video availability and workspace configuration.
          </p>
        </section>
        <section
          className="product-demo"
          aria-label="Interactive caption demonstration"
        >
          <div className="demo-toolbar">
            <Logo />
            <span>Caption playground · illustrative preview</span>
            <span className="badge">9:16</span>
          </div>
          <div className="demo-grid">
            <div className="demo-context">
              <span className="eyebrow">
                A little polish. A lot of possibility.
              </span>
              <h2>
                One story.
                <br />
                Your signature.
              </h2>
              <p>
                Try a caption style. The same controls are available in your
                clip editor.
              </p>
              <div className="demo-options">
                {presets.slice(0, 6).map((p, i) => (
                  <button
                    key={p.id}
                    aria-pressed={preset === i}
                    onClick={() => setPreset(i)}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
              <div className="segmented">
                <button aria-pressed={!after} onClick={() => setAfter(false)}>
                  Before
                </button>
                <button aria-pressed={after} onClick={() => setAfter(true)}>
                  After
                </button>
              </div>
            </div>
            <div className="demo-portrait">
              <div className="demo-lines" aria-hidden="true" />
              <span className="demo-label">Your next story starts here</span>
              <div
                className="demo-caption"
                style={
                  after
                    ? {
                        fontFamily: style.font,
                        fontSize: style.size / 2.5,
                        fontWeight: style.weight,
                        color: style.color,
                        textShadow: `0 2px ${style.shadow + 2}px #000`,
                        WebkitTextStroke: `${style.stroke / 5}px #000`,
                      }
                    : { fontSize: 17, color: "#fff" }
                }
              >
                Make room for
                <br />
                <strong
                  style={{ color: after ? style.emphasis_color : "#fff" }}
                >
                  the good part.
                </strong>
              </div>
              <span className="demo-bottom">
                Typography demo · no generated video
              </span>
            </div>
          </div>
        </section>
        <section id="features" className="public-section">
          <div className="section-title">
            <span className="eyebrow">Built for your creative process</span>
            <h2>
              From the first idea
              <br />
              to the final frame.
            </h2>
          </div>
          <div className="bento-grid">
            {features.map(([name, detail, Icon], i) => (
              <article
                className={i === 0 || i === 7 ? "bento-wide" : ""}
                key={name}
              >
                <span className="feature-icon">
                  <Icon size={22} />
                </span>
                <h3>{name}</h3>
                <p>{detail}</p>
                {i === 0 && (
                  <div className="signal-bars" aria-hidden="true">
                    {[
                      24, 36, 65, 44, 92, 70, 38, 80, 56, 31, 66, 88, 53, 28,
                    ].map((n, j) => (
                      <i key={j} style={{ height: n }} />
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
        <section id="how" className="public-section">
          <div className="section-title">
            <span className="eyebrow">A simpler workflow</span>
            <h2>Less busywork. More creating.</h2>
          </div>
          <div className="how-grid">
            {[
              [
                "01",
                "Bring your video",
                "Paste an approved source link, connect an original, or upload a file.",
              ],
              [
                "02",
                "Find your moments",
                "Let the local AI pipeline transcribe and rank highlight candidates.",
              ],
              [
                "03",
                "Make it yours",
                "Refine captions, framing and titles, then export your finished cuts.",
              ],
            ].map(([n, t, d]) => (
              <article key={n}>
                <span>{n}</span>
                <h3>{t}</h3>
                <p>{d}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="public-section use-cases">
          <div>
            <span className="eyebrow">Made for the way you create</span>
            <h2>
              Your next clip is already
              <br />
              in your last video.
            </h2>
          </div>
          <div className="use-tags">
            {[
              "Podcasts",
              "Interviews",
              "Lessons",
              "Product demos",
              "Commentary",
              "Recorded talks",
            ].map((t) => (
              <span key={t}>{t}</span>
            ))}
          </div>
        </section>
        <section id="pricing" className="public-section pricing-section">
          <div>
            <span className="eyebrow">Start creating</span>
            <h2>Room to find your rhythm.</h2>
            <p>Local development access. No payment credentials required.</p>
          </div>
          <article className="pricing-card">
            <span>Trial + Free Forever</span>
            <h3>
              Free <small>/ local workspace</small>
            </h3>
            <p>90 free minutes for 7 days, then 60 free minutes every month. No card required.</p>
            <ul>
              {[
                "Your own clipping engine",
                "Caption and brand tools",
                "MP4 exports",
                "Explainable highlight scores",
              ].map((t) => (
                <li key={t}>
                  <Check size={16} />
                  {t}
                </li>
              ))}
            </ul>
            <Link to="/new" className="button primary">
              Create your first clip <ArrowRight size={15} />
            </Link>
            <small>
              Trial and free minutes do not roll over. Paid checkout is not yet available.
            </small>
          </article>
        </section>
        <section className="public-section faq">
          <span className="eyebrow">A few things to know</span>
          <h2>Good questions. Clear answers.</h2>
          {[
            [
              "Can I paste any YouTube link?",
              "When enabled, public YouTube retrieval can be attempted for videos you own or have permission to use. Restricted or blocked videos require an authorized original.",
            ],
            [
              "How long does processing take?",
              "Long videos can take several minutes on a local CPU. Progress is saved and processing continues when you leave the page.",
            ],
            [
              "Are scores a promise of engagement?",
              "No. They are explainable editorial rankings based on available transcript, scene and audio signals.",
            ],
            [
              "Can I change fonts and captions?",
              "Yes. Choose a preset, adjust styling and word timing, or upload a font you are licensed to use.",
            ],
          ].map(([q, a]) => (
            <details key={q}>
              <summary>{q}</summary>
              <p>{a}</p>
            </details>
          ))}
        </section>
      </main>
      <footer className="public-footer">
        <Logo />
        <span>Create More. Edit Less.</span>
        <Link to="/new">
          Start a project <ArrowUpRight size={14} />
        </Link>
      </footer>
    </div>
  );
}
