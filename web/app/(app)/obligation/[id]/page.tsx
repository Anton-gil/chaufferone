import Link from "next/link";
import { notFound } from "next/navigation";
import { api, type Cascade, type Obligation, type Risk } from "@/lib/api";

export const dynamic = "force-dynamic";

function fmtDate(iso: string | null): string {
  if (!iso) return "no date";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
function fmtINR(n: number | null | undefined): string {
  if (n == null) return "—";
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

async function fetchAll(id: string): Promise<{
  ob: Obligation | null;
  risk: Risk | null;
  cascade: Cascade | null;
  error: string | null;
}> {
  try {
    const [ob, risk, cascade] = await Promise.all([
      api.obligation(id),
      api.risk(id).catch(() => null),
      api.cascade(id).catch(() => null),
    ]);
    return { ob, risk, cascade, error: null };
  } catch (e) {
    return { ob: null, risk: null, cascade: null, error: (e as Error).message };
  }
}

type Params = Promise<{ id: string }>;

function RiskBar({ label, value }: { label: string; value: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div style={{ marginBottom: 8 }}>
      <div className="row">
        <span className="meta">{label}</span>
        <span className="meta">{Math.round(clamped)}</span>
      </div>
      <div style={{ height: 6, background: "#23232c", borderRadius: 999, overflow: "hidden" }}>
        <div
          style={{
            width: `${clamped}%`,
            height: "100%",
            background: "#7ee29a",
            opacity: 0.7,
          }}
        />
      </div>
    </div>
  );
}

export default async function ObligationDetail({ params }: { params: Params }) {
  const { id } = await params;
  const { ob, risk, cascade, error } = await fetchAll(id);

  if (error && !ob) {
    if (error.includes("404")) notFound();
    return (
      <main>
        <h1>Obligation</h1>
        <div className="error" style={{ marginTop: 16 }}>{error}</div>
      </main>
    );
  }
  if (!ob) notFound();

  return (
    <main style={{ maxWidth: 900 }}>
      <p style={{ marginBottom: 8 }}>
        <Link href="/" style={{ color: "#7ee29a", fontSize: 13 }}>← Timeline</Link>
      </p>
      <h1>{ob.title}</h1>
      <p className="muted">
        {ob.category ?? "uncategorised"} · {fmtDate(ob.due_date)} · {fmtINR(ob.amount)}
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 20 }}>
        <div className="card">
          <div className="meta">Urgency</div>
          <div>
            <span className={`status ${ob.urgency_tier}`}>{ob.urgency_tier}</span>
          </div>
        </div>
        <div className="card">
          <div className="meta">Status</div>
          <div className="title">{ob.status}</div>
        </div>
        <div className="card">
          <div className="meta">Verification</div>
          <div className="title">{ob.verification_state}</div>
        </div>
        <div className="card">
          <div className="meta">Lead time</div>
          <div className="title">{ob.lead_time_days} day{ob.lead_time_days === 1 ? "" : "s"}</div>
        </div>
      </div>

      {risk ? (
        <>
          <h2>Risk breakdown</h2>
          <div className="card">
            <div className="row" style={{ marginBottom: 12 }}>
              <div>
                <div className="meta">Score</div>
                <div style={{ fontSize: 28, fontWeight: 600 }}>{risk.score}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="meta">Tier</div>
                <span className={`status ${risk.tier}`}>{risk.tier}</span>
              </div>
            </div>
            <RiskBar label="Time urgency" value={risk.components.time_urgency} />
            <RiskBar label="Penalty severity" value={risk.components.penalty_severity} />
            <RiskBar label="Prerequisite risk" value={risk.components.prerequisite_risk} />
            <RiskBar label="Cash-flow risk" value={risk.components.cash_flow_risk} />
            <RiskBar label="Historical miss" value={risk.components.historical_miss} />
            <div className="row" style={{ marginTop: 12 }}>
              <span className="meta">Start by</span>
              <span className="meta">{fmtDate(risk.start_by)}</span>
            </div>
          </div>
        </>
      ) : null}

      {cascade && cascade.steps.length > 0 ? (
        <>
          <h2>If missed · cascade</h2>
          <p className="muted" style={{ marginBottom: 8 }}>
            Total exposure {fmtINR(cascade.total_exposure_inr)} across {cascade.step_count} step{cascade.step_count === 1 ? "" : "s"}.
          </p>
          {cascade.steps.map((s, i) => (
            <div key={`${s.obligation_id}-${i}`} className="card">
              <div className="row">
                <span className="title">
                  {i === 0 ? "" : "↳ "}
                  {s.obligation_id === ob.id ? s.title : (
                    <Link href={`/obligation/${s.obligation_id}`} style={{ color: "#e8e8ec" }}>{s.title}</Link>
                  )}
                </span>
                <span className="meta">{s.reason}</span>
              </div>
              <div className="row">
                <span className="meta">Direct penalty</span>
                <span className="meta">{fmtINR(s.direct_penalty)}</span>
              </div>
            </div>
          ))}
        </>
      ) : null}
    </main>
  );
}
