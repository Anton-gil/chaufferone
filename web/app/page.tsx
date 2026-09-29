import Link from "next/link";
import { api, type Obligation } from "@/lib/api";
import { CountUp } from "@/components/CountUp";

export const dynamic = "force-dynamic";

function fmtDate(iso: string | null): string {
  if (!iso) return "no due date";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function fmtAmount(amount: number | null, currency: string): string {
  if (amount == null) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}

async function fetchState(): Promise<{
  health: string | null;
  obligations: Obligation[] | null;
  error: string | null;
}> {
  try {
    const [h, t] = await Promise.all([api.health(), api.timeline()]);
    return { health: h.status, obligations: t, error: null };
  } catch (e) {
    return { health: null, obligations: null, error: (e as Error).message };
  }
}

function WalletMark() {
  return (
    <svg width="72" height="72" viewBox="0 0 96 96" fill="none" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="14" y="26" width="68" height="50" rx="10" />
      <path d="M14 38h68" />
      <circle cx="68" cy="56" r="4" fill="var(--ink)" />
      <path d="M22 20l40 4" opacity="0.6" />
    </svg>
  );
}

export default async function Home() {
  const { health, obligations, error } = await fetchState();
  const total = obligations?.length ?? 0;
  const overdue = obligations?.filter((o) => o.urgency_tier === "red").length ?? 0;

  return (
    <main style={{ maxWidth: "none", padding: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 24, marginBottom: 6 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 12 }}>Single Stake (3,3)</div>
          <h1>
            The one who holds<br />every thread of your life.
          </h1>
          <p className="muted" style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 8 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
            {overdue > 0 ? `${overdue} obligation${overdue === 1 ? "" : "s"} need attention today` : "You're on track. Next obligation in 3 days."}
          </p>
        </div>

        <div className="earnings-pill">
          <span className="icon" aria-hidden>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 7h18v10H3z" />
              <path d="M16 12h.01" />
              <path d="M3 7l4-4h10l4 4" />
            </svg>
          </span>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span className="amount">₹<CountUp value={50000} /></span>
            <span className="label">Starting Balance · Today</span>
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card-light">
          <div className="wallet-illus" aria-hidden>
            <WalletMark />
          </div>
          <button className="btn-outline">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="6" width="18" height="12" rx="2" />
              <path d="M3 10h18" />
            </svg>
            Link Bank Account
          </button>
          <p className="muted" style={{ marginTop: 16, maxWidth: 280 }}>
            Connect your bank so ORACLE can sync balances and forecast in real time.
          </p>
        </div>

        <div className="card-dark">
          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-label">
                Soft Cushion
                <span style={{ opacity: 0.55 }}>%</span>
              </span>
              <span className="stat-value">₹<CountUp value={10000} /></span>
              <div className="progress progress-inv" style={{ marginTop: 12 }}>
                <span style={{ width: "62%" }} />
              </div>
            </div>

            <div className="stat-item">
              <span className="stat-label">
                Hard Floor
                <span className="stat-badge" aria-hidden>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M7 17L17 7M9 7h8v8" /></svg>
                </span>
              </span>
              <span className="stat-value">₹<CountUp value={5000} /></span>
              <div className="progress progress-inv" style={{ marginTop: 12 }}>
                <span style={{ width: "31%" }} />
              </div>
            </div>

            <div className="stat-item">
              <span className="stat-label">
                Active Obligations
                <span style={{ opacity: 0.55 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M4 6h16M4 12h16M4 18h10" /></svg>
                </span>
              </span>
              <span className="stat-value"><CountUp value={total} /></span>
              <span className="viz-sub" style={{ marginTop: 6 }}>
                {overdue} overdue · {Math.max(0, total - overdue)} scheduled
              </span>
            </div>
          </div>
        </div>
      </div>

      <h2>Obligations Timeline</h2>

      {health ? (
        <div style={{ marginBottom: 14 }}>
          <span className="status green">Live · {health}</span>
        </div>
      ) : (
        <div className="error" style={{ marginBottom: 16 }}>
          Backend unreachable. Start FastAPI with{" "}
          <code>uv run uvicorn app.main:app --reload</code>.
          {error ? <div style={{ marginTop: 6 }}>{error}</div> : null}
        </div>
      )}

      {obligations && obligations.length === 0 ? (
        <p className="muted">
          No obligations yet. Seed demo data with{" "}
          <code>curl -X POST http://localhost:8000/api/demo/seed</code> and refresh.
        </p>
      ) : null}

      <div className="stagger">
        {obligations?.map((o) => (
          <Link key={o.id} href={`/obligation/${o.id}`} style={{ display: "block" }}>
            <div className="card">
              <div className="row">
                <span className="title">{o.title}</span>
                <span className={`status ${o.urgency_tier}`}>{o.urgency_tier}</span>
              </div>
              <div className="row">
                <span className="meta">
                  {o.category ?? "uncategorised"} · {fmtDate(o.due_date)}
                </span>
                <span className="meta" style={{ fontVariantNumeric: "tabular-nums", color: "var(--ink)", fontWeight: 500 }}>
                  {fmtAmount(o.amount, o.currency)}
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
