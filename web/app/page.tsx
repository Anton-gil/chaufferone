import Link from "next/link";
import { api, type Obligation } from "@/lib/api";

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

export default async function Home() {
  const { health, obligations, error } = await fetchState();

  return (
    <main style={{ padding: 0, maxWidth: "none" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "32px" }}>
        <div>
          <h1>Dashboard Overview</h1>
          <p className="muted" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            Next obligation due soon
          </p>
        </div>
        <div style={{ background: 'var(--card-dark)', padding: '16px 24px', borderRadius: '12px', color: 'white', display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(255,255,255,0.1)', padding: '8px', borderRadius: '8px' }}></div>
          <div>
            <div style={{ fontSize: '24px', fontWeight: 'bold' }}>₹50,000</div>
            <div style={{ fontSize: '12px', color: '#8a8a94' }}>Starting Balance</div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card-light">
          <div className="wallet-icon"></div>
          <button className="btn-outline">Link Bank Account</button>
          <p className="muted" style={{ marginTop: '16px' }}>Connect your bank to sync balances</p>
        </div>

        <div className="card-dark">
          <div className="stats-grid">
            <div className="stat-item" style={{ position: 'relative' }}>
              <span className="stat-label">Soft Cushion</span>
              <span className="stat-value">₹10,000</span>
              <span style={{ position: 'absolute', top: 0, right: 0, color: '#8a8a94', cursor: 'pointer' }}>*</span>
            </div>
            
            <div className="stat-item" style={{ position: 'relative' }}>
              <span className="stat-label">Hard Floor</span>
              <span className="stat-value">₹5,000</span>
              <div style={{ position: 'absolute', right: 0, bottom: 0, background: 'white', color: 'black', width: '24px', height: '24px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px', fontWeight: 'bold' }}></div>
            </div>

            <div className="stat-item" style={{ position: 'relative' }}>
              <span className="stat-label">Active Obligations</span>
              <span className="stat-value">{obligations?.length ?? 0}</span>
              <span style={{ position: 'absolute', right: 0, bottom: 0, color: '#8a8a94' }}></span>
            </div>
          </div>
        </div>
      </div>

      <h2>Obligations Timeline</h2>
      {health ? (
        <span className="status green" style={{ marginBottom: '16px', display: 'inline-block' }}>connected · {health}</span>
      ) : (
        <div className="error" style={{ marginBottom: '16px' }}>
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
      {obligations?.map((o) => (
        <Link
          key={o.id}
          href={`/obligation/${o.id}`}
          style={{ textDecoration: "none", display: "block" }}
        >
          <div className="card">
            <div className="row">
              <span className="title">{o.title}</span>
              <span className={`status ${o.urgency_tier}`}>{o.urgency_tier}</span>
            </div>
            <div className="row">
              <span className="meta">
                {o.category ?? "uncategorised"} · {fmtDate(o.due_date)}
              </span>
              <span className="meta">{fmtAmount(o.amount, o.currency)}</span>
            </div>
          </div>
        </Link>
      ))}
    </main>
  );
}
