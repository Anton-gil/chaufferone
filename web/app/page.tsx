import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { Reveal, LandingNavShrink } from "@/components/Reveal";
import { SmoothScroll } from "@/components/SmoothScroll";
import { authOptions } from "@/lib/auth";

export const dynamic = "force-dynamic";

type StepArt = "ingest" | "extract" | "sequence" | "voice";

const steps: { n: string; title: string; body: string; art: StepArt }[] = [
  {
    n: "Step 1",
    title: "Ingest, zero typing",
    body: "Live Android SMS, backup XML, Gmail, .eml files, WhatsApp exports. Nothing to configure at 2am.",
    art: "ingest",
  },
  {
    n: "Step 2",
    title: "Extract the obligation",
    body: "Bank SMS through deterministic regex on your machine. Emails and chats through a labelled LLM into a strict schema.",
    art: "extract",
  },
  {
    n: "Step 3",
    title: "Sequence with dependencies",
    body: "Backward-schedules from every deadline through its prerequisites — insurance needs a valid PUC, so PUC lands on Sunday.",
    art: "sequence",
  },
  {
    n: "Step 4",
    title: "Approve by voice",
    body: "It speaks the trade-off. You answer. Your UPI PIN approves each payment. The bank's own debit SMS marks it verified.",
    art: "voice",
  },
];

function StepArt({ kind }: { kind: StepArt }) {
  const common = {
    xmlns: "http://www.w3.org/2000/svg",
    viewBox: "0 0 240 130",
    className: "step-art-svg",
    "aria-hidden": true as const,
  };
  if (kind === "ingest") {
    return (
      <svg {...common}>
        <g fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="70" y="20" width="60" height="92" rx="8" />
          <line x1="70" y1="32" x2="130" y2="32" />
          <circle cx="100" cy="26" r="1" fill="currentColor" />
          <rect x="78" y="42" width="44" height="14" rx="3" />
          <rect x="78" y="62" width="34" height="10" rx="3" />
          <rect x="78" y="78" width="44" height="10" rx="3" />
          <g className="step-art-fly">
            <rect x="150" y="30" width="60" height="22" rx="4" />
            <line x1="156" y1="38" x2="196" y2="38" />
            <line x1="156" y1="44" x2="186" y2="44" />
          </g>
          <g className="step-art-fly step-art-fly-2">
            <rect x="150" y="60" width="60" height="22" rx="4" />
            <line x1="156" y1="68" x2="196" y2="68" />
            <line x1="156" y1="74" x2="180" y2="74" />
          </g>
          <path d="M140 44 L150 44 M140 74 L150 74" strokeDasharray="2 3" />
        </g>
      </svg>
    );
  }
  if (kind === "extract") {
    return (
      <svg {...common}>
        <g fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="24" y="18" width="72" height="94" rx="6" />
          <line x1="34" y1="34" x2="86" y2="34" />
          <line x1="34" y1="46" x2="80" y2="46" />
          <line x1="34" y1="56" x2="72" y2="56" />
          <line x1="34" y1="66" x2="82" y2="66" />
          <line x1="34" y1="76" x2="66" y2="76" />
          <line x1="34" y1="86" x2="78" y2="86" />
          <path d="M96 64 C 118 64, 118 40, 140 40" strokeDasharray="3 3" />
          <path d="M96 74 C 118 74, 118 68, 140 68" strokeDasharray="3 3" />
          <path d="M96 84 C 118 84, 118 96, 140 96" strokeDasharray="3 3" />
          <rect x="140" y="28" width="76" height="24" rx="4" />
          <text x="146" y="43" fontFamily="ui-monospace, monospace" fontSize="8" fill="currentColor">due · 2026-10-14</text>
          <rect x="140" y="56" width="76" height="24" rx="4" />
          <text x="146" y="71" fontFamily="ui-monospace, monospace" fontSize="8" fill="currentColor">amount · ₹12,480</text>
          <rect x="140" y="84" width="76" height="24" rx="4" />
          <text x="146" y="99" fontFamily="ui-monospace, monospace" fontSize="8" fill="currentColor">needs · PUC</text>
        </g>
      </svg>
    );
  }
  if (kind === "sequence") {
    return (
      <svg {...common}>
        <g fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="20" y1="100" x2="220" y2="100" strokeDasharray="3 4" opacity="0.4" />
          <g>
            <circle cx="40" cy="100" r="8" fill="currentColor" />
            <text x="40" y="118" textAnchor="middle" fontSize="8" fill="currentColor">Sun</text>
          </g>
          <g>
            <circle cx="100" cy="100" r="6" />
            <text x="100" y="118" textAnchor="middle" fontSize="8" fill="currentColor">Tue</text>
          </g>
          <g>
            <circle cx="160" cy="100" r="6" />
            <text x="160" y="118" textAnchor="middle" fontSize="8" fill="currentColor">Fri</text>
          </g>
          <g>
            <circle cx="210" cy="100" r="9" fill="currentColor" />
            <text x="210" y="118" textAnchor="middle" fontSize="8" fill="currentColor">Sat</text>
          </g>
          <path d="M46 96 C 70 60, 84 60, 96 92" markerEnd="url(#arrow-a)" />
          <path d="M106 96 C 128 66, 142 66, 156 92" markerEnd="url(#arrow-a)" />
          <path d="M166 96 C 186 68, 200 68, 208 92" markerEnd="url(#arrow-a)" />
          <rect x="26" y="28" width="34" height="18" rx="3" />
          <text x="43" y="40" textAnchor="middle" fontSize="8" fill="currentColor">PUC</text>
          <rect x="188" y="28" width="46" height="18" rx="3" fill="currentColor" />
          <text x="211" y="40" textAnchor="middle" fontSize="8" fill="#fff">Insurance</text>
          <defs>
            <marker id="arrow-a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0 0 L10 5 L0 10 z" fill="currentColor" />
            </marker>
          </defs>
        </g>
      </svg>
    );
  }
  // voice
  return (
    <svg {...common}>
      <g fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="102" y="30" width="36" height="52" rx="18" fill="currentColor" />
        <line x1="120" y1="82" x2="120" y2="98" />
        <line x1="108" y1="98" x2="132" y2="98" />
        <path d="M84 56 Q 120 100, 156 56" opacity="0.6" />
        <g className="step-art-wave">
          <line x1="60" y1="60" x2="60" y2="72" />
          <line x1="72" y1="52" x2="72" y2="80" />
          <line x1="84" y1="44" x2="84" y2="88" />
        </g>
        <g className="step-art-wave step-art-wave-2">
          <line x1="156" y1="44" x2="156" y2="88" />
          <line x1="168" y1="52" x2="168" y2="80" />
          <line x1="180" y1="60" x2="180" y2="72" />
        </g>
      </g>
    </svg>
  );
}

type FeatureIcon = "local" | "graph" | "money" | "voice" | "verify" | "audit";

const features: { icon: FeatureIcon; title: string; body: string }[] = [
  { icon: "local",  title: "Local-first engine", body: "Database, planner, forecast, and bank-SMS parsing run on your laptop. There is no Chaufferone server." },
  { icon: "graph",  title: "Obligation graph",   body: "Knows which tasks share money and which have hard prerequisites — regulator-mandated ones too." },
  { icon: "money",  title: "Money engine",       body: "45-day daily forecast with a hard emergency floor. Every proposed fix is re-simulated before it's offered." },
  { icon: "voice",  title: "Voice consent",      body: "Rules parse your reply first. Hosted LLM only kicks in as a fallback — one env flag turns it off." },
  { icon: "verify", title: "Verification loop",  body: "A payment is only 'done' when the bank's own debit SMS matches. No optimistic ticks." },
  { icon: "audit",  title: "Auditable",          body: "Every voice decision, every plan change, in one consent log. Nothing hidden behind a model call." },
];

function FeatureGlyph({ kind }: { kind: FeatureIcon }) {
  const p = {
    xmlns: "http://www.w3.org/2000/svg",
    viewBox: "0 0 24 24",
    width: 20,
    height: 20,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };
  switch (kind) {
    case "local":
      return (
        <svg {...p}>
          <rect x="3" y="5" width="18" height="12" rx="2" />
          <line x1="7" y1="20" x2="17" y2="20" />
          <line x1="12" y1="17" x2="12" y2="20" />
          <circle cx="8" cy="10" r="0.9" fill="currentColor" />
        </svg>
      );
    case "graph":
      return (
        <svg {...p}>
          <circle cx="6" cy="6" r="2.2" />
          <circle cx="18" cy="7" r="2.2" />
          <circle cx="12" cy="17" r="2.4" fill="currentColor" />
          <line x1="7.4" y1="7.5" x2="10.5" y2="15" />
          <line x1="16.5" y1="8.5" x2="13.5" y2="15" />
          <line x1="8" y1="6" x2="16" y2="7" />
        </svg>
      );
    case "money":
      return (
        <svg {...p}>
          <polyline points="3,17 7,12 11,14 15,8 21,10" />
          <line x1="3" y1="20" x2="21" y2="20" strokeDasharray="2 2" />
          <circle cx="7" cy="12" r="1.2" fill="currentColor" />
          <circle cx="15" cy="8" r="1.2" fill="currentColor" />
        </svg>
      );
    case "voice":
      return (
        <svg {...p}>
          <rect x="9" y="3" width="6" height="10" rx="3" fill="currentColor" />
          <path d="M5 11 Q 12 19, 19 11" />
          <line x1="12" y1="17" x2="12" y2="21" />
          <line x1="9" y1="21" x2="15" y2="21" />
        </svg>
      );
    case "verify":
      return (
        <svg {...p}>
          <circle cx="12" cy="12" r="8" />
          <polyline points="8.5,12.5 11,15 16,9.5" />
        </svg>
      );
    case "audit":
      return (
        <svg {...p}>
          <rect x="4" y="3" width="16" height="18" rx="2" />
          <line x1="7" y1="8" x2="17" y2="8" />
          <line x1="7" y1="12" x2="15" y2="12" />
          <line x1="7" y1="16" x2="13" y2="16" />
        </svg>
      );
  }
}

export default async function Landing() {
  const session = await getServerSession(authOptions);
  if (session) redirect("/dashboard");
  return (
    <div className="landing">
      <LandingNavShrink />
      <SmoothScroll />

      <nav className="landing-nav">
        <Link href="/" className="landing-logo">
          <span className="landing-logo-mark" />
          Chaufferone
        </Link>
        <div className="landing-nav-links">
          <a href="#how">How it works</a>
          <a href="#features">Features</a>
          <a href="#privacy">Privacy</a>
        </div>
        <Link href="/login" className="btn-primary">Sign in</Link>
      </nav>

      <section className="hero">
        <div className="hero-stars" aria-hidden="true">
          <span className="hero-star-pulse" />
          <span className="hero-star-pulse" />
          <span className="hero-star-pulse" />
          <span className="hero-star-pulse" />
        </div>

        <div className="hero-ticks hero-ticks-left" aria-hidden="true">
          <div className="hero-ticks-grid">
            {Array.from({ length: 20 }).map((_, i) => <span key={i} />)}
          </div>
        </div>
        <div className="hero-ticks hero-ticks-right" aria-hidden="true">
          <div className="hero-ticks-grid">
            {Array.from({ length: 20 }).map((_, i) => <span key={i} />)}
          </div>
        </div>

        <Reveal>
          <h1 className="hero-title">
            <span className="hero-title-line">Work Normally.</span>
            <span className="hero-title-line">Chaufferone Does The Rest.</span>
          </h1>
        </Reveal>

        <Reveal delay={1}>
          <p className="hero-sub">
            Every message becomes an obligation. Every obligation knows what it depends on and what it costs.
            You get one sequenced plan instead of thirty alerts.
          </p>
        </Reveal>

        <Reveal delay={2}>
          <div className="hero-actions">
            <Link href="/login" className="btn-primary hero-google-btn">
              <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#4285F4" d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z" />
                <path fill="#34A853" d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z" />
                <path fill="#FBBC05" d="M11.69 28.18c-.44-1.32-.69-2.73-.69-4.18s.25-2.86.69-4.18v-5.7H4.34C2.85 17.09 2 20.45 2 24s.85 6.91 2.34 9.88l7.35-5.7z" />
                <path fill="#EA4335" d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z" />
              </svg>
              Sign in with Google
            </Link>
            <a href="#how" className="btn-outline">
              See how it works
              <span className="hero-outline-glyphs" aria-hidden="true">◐ ◇ ◈</span>
            </a>
          </div>
        </Reveal>

        <div className="hero-arc-glow" aria-hidden="true" />
        <div className="hero-arc" aria-hidden="true">
          <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
            <g className="hero-arc-group">
              <circle className="arc-a" cx="50" cy="50" r="49" />
              <circle className="arc-a" cx="50" cy="50" r="46" />
              <circle className="arc-a" cx="50" cy="50" r="43" />
            </g>
            <g className="hero-arc-group-reverse">
              <circle className="arc-b" cx="50" cy="50" r="39" />
              <circle className="arc-b" cx="50" cy="50" r="35" />
              <circle className="arc-c" cx="50" cy="50" r="30" />
              <circle className="arc-c" cx="50" cy="50" r="24" />
            </g>
          </svg>
        </div>

        <div className="hero-logos">
          <span className="hero-logos-label">Ingests from</span>
          <span className="hero-logo-chip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <rect x="4" y="6" width="16" height="12" rx="2" />
              <line x1="7" y1="20" x2="17" y2="20" />
              <line x1="8" y1="10" x2="16" y2="10" />
              <line x1="8" y1="13" x2="14" y2="13" />
            </svg>
            Android SMS
          </span>
          <span className="hero-logo-chip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="5" width="18" height="14" rx="2" />
              <polyline points="3,7 12,14 21,7" />
            </svg>
            Gmail
          </span>
          <span className="hero-logo-chip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3a9 9 0 0 0-7.7 13.6L3 21l4.5-1.2A9 9 0 1 0 12 3Z" />
            </svg>
            WhatsApp
          </span>
          <span className="hero-logo-chip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 3h8l4 4v14H6z" />
              <polyline points="14,3 14,7 18,7" />
            </svg>
            .eml files
          </span>
          <span className="hero-logo-chip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 6a8 4 0 1 0 16 0a8 4 0 1 0 -16 0" />
              <path d="M4 6v12a8 4 0 0 0 16 0V6" />
              <path d="M4 12a8 4 0 0 0 16 0" />
            </svg>
            Backup XML
          </span>
        </div>
      </section>

      <div className="marquee" aria-hidden="true">
        <div className="marquee-track">
          <span>Rent</span><span>Insurance</span><span>Loan EMI</span>
          <span>Tuition</span><span>Utilities</span><span>Subscriptions</span>
          <span>Taxes</span><span>PUC</span><span>Renewals</span>
          <span>Rent</span><span>Insurance</span><span>Loan EMI</span>
          <span>Tuition</span><span>Utilities</span><span>Subscriptions</span>
          <span>Taxes</span><span>PUC</span><span>Renewals</span>
        </div>
      </div>

      <section id="how" className="section">
        <Reveal>
          <h2 className="section-heading">Work normally. Chaufferone does the rest.</h2>
        </Reveal>
        <Reveal delay={1}>
          <p className="section-sub">
            Four beats, one plan. Every step is inspectable — there's a URL for the graph, the forecast, and the consent log.
          </p>
        </Reveal>

        <div className="steps">
          {steps.map((s, i) => (
            <Reveal key={s.n} delay={((i % 4) + 1) as 1 | 2 | 3 | 4} className="step">
              <div className="step-num">{s.n}</div>
              <div className="step-title">{s.title}</div>
              <p className="step-body">{s.body}</p>
              <div className="step-art">
                <StepArt kind={s.art} />
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section id="features" className="section">
        <Reveal>
          <h2 className="section-heading">Not a to-do list. An engine.</h2>
        </Reveal>
        <Reveal delay={1}>
          <p className="section-sub">
            Deterministic where it needs to be. LLM-labelled where it helps. Local by default.
          </p>
        </Reveal>

        <div className="features">
          {features.map((f, i) => (
            <Reveal key={f.title} delay={((i % 4) + 1) as 1 | 2 | 3 | 4} className="feature">
              <div className="feature-icon" aria-hidden="true"><FeatureGlyph kind={f.icon} /></div>
              <div className="feature-title">{f.title}</div>
              <p className="feature-body">{f.body}</p>
            </Reveal>
          ))}
        </div>
      </section>

      <section id="privacy" className="section" style={{ paddingTop: 0 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 40, alignItems: "center" }}>
          <Reveal>
            <span className="eyebrow">Privacy</span>
            <h2 className="section-heading" style={{ textAlign: "left", marginTop: 8 }}>
              Your life administration<br />belongs to you.
            </h2>
          </Reveal>
          <Reveal delay={1}>
            <p style={{ color: "var(--mute-strong)", fontSize: 16, lineHeight: 1.6 }}>
              The engine, the database, the money forecast, and every bank-SMS parser run on your own laptop.
              Hosted AI is only used for email/WhatsApp extraction and as an optional voice fallback — both are labelled,
              and voice can be switched off with a single env flag. We never hold money, credentials, or auto-debit mandates.
            </p>
          </Reveal>
        </div>
      </section>

      <div className="cta">
        <Reveal>
          <h2>One plan. One voice. Zero missed deadlines.</h2>
        </Reveal>
        <Reveal delay={1}>
          <p>Chaufferone is local-first, auditable, and built to run for the whole month — not just the demo.</p>
        </Reveal>
        <Reveal delay={2}>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/dashboard" className="btn-primary">Open the dashboard →</Link>
            <a href="http://localhost:8000/docs" className="btn-outline" target="_blank" rel="noreferrer">API docs</a>
          </div>
        </Reveal>
      </div>

      <footer className="landing-footer">
        <div>Chaufferone · The obligation engine</div>
        <div>Local-first · Voice-approved · Bank-verified</div>
      </footer>
    </div>
  );
}
