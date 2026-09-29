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
    <div style={{ marginBottom: 10 }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <span className="meta">{label}</span>
        <span className="meta" style={{ fontVariantNumeric: "tabular-nums", color: "var(--text-inv)" }}>
          {Math.round(clamped)}
        </span>
      </div>
      <div className="progress progress-inv">
        <span style={{ width: `${clamped}%` }} />
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
    <main style={{ maxWidth: 960, padding: 0 }}>
      <p style={{ marginBottom: 14 }}>
        <Link
          href="/"
          style={{
            color: "var(--text-2)",
            fontSize: 12.5,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            borderBottom: "1px solid var(--line-2)",
            paddingBottom: 2,
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Back to timeline
        </Link>
      </p>

      <div className="eyebrow" style={{ marginBottom: 12 }}>Obligation</div>
      <h1>{ob.title}</h1>
      <p className="muted" style={{ marginTop: 8 }}>
        {ob.category ?? "uncategorised"} · {fmtDate(ob.due_date)} · <span style={{ color: "var(--ink)", fontWeight: 500 }}>{fmtINR(ob.amount)}</span>
      </p>

      <div className="grid-4" style={{ marginTop: 28 }}>
        <div className="card" style={{ padding: 18 }}>
          <div className="meta" style={{ textTransform: "uppercase", letterSpacing: "0.06em", fontSize: 10 }}>Urgency</div>
          <div style={{ marginTop: 10 }}><span className={`status ${ob.urgency_tier}`}>{ob.urgency_tier}</span></div>
        </div>
        <div className="card" style={{ padding: 18 }}>
          <div className="meta" style={{ textTransform: "uppercase", letterSpacing: "0.06em", fontSize: 10 }}>Status</div>
          <div className="title" style={{ marginTop: 8 }}>{ob.status}</div>
        </div>
        <div className="card" style={{ padding: 18 }}>
          <div className="meta" style={{ textTransform: "uppercase", letterSpacing: "0.06em", fontSize: 10 }}>Verification</div>
          <div className="title" style={{ marginTop: 8 }}>{ob.verification_state}</div>
        </div>
        <div className="card" style={{ padding: 18 }}>
          <div className="meta" style={{ textTransform: "uppercase", letterSpacing: "0.06em", fontSize: 10 }}>Lead time</div>
          <div className="title" style={{ marginTop: 8, fontVariantNumeric: "tabular-nums" }}>
            {ob.lead_time_days} day{ob.lead_time_days === 1 ? "" : "s"}
          </div>
        </div>
      </div>

      {risk ? (
        <>
          <h2>Risk Breakdown</h2>
          <div className="card-ink">
            <div className="row" style={{ marginBottom: 20, alignItems: "flex-end" }}>
              <div>
                <div className="meta" style={{ textTransform: "uppercase", letterSpacing: "0.08em", fontSize: 10 }}>Score</div>
                <div style={{ fontSize: 44, fontWeight: 700, letterSpacing: "-0.03em", lineHeight: 1, marginTop: 4 }}>
                  {risk.score}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="meta" style={{ textTransform: "uppercase", letterSpacing: "0.08em", fontSize: 10, marginBottom: 6 }}>Tier</div>
                <span className={`status ${risk.tier}`}>{risk.tier}</span>
              </div>
            </div>
            <RiskBar label="Time urgency" value={risk.components.time_urgency} />
            <RiskBar label="Penalty severity" value={risk.components.penalty_severity} />
            <RiskBar label="Prerequisite risk" value={risk.components.prerequisite_risk} />
            <RiskBar label="Cash-flow risk" value={risk.components.cash_flow_risk} />
            <RiskBar label="Historical miss" value={risk.components.historical_miss} />
            <div className="row" style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
              <span className="meta">Start by</span>
              <span className="meta" style={{ color: "var(--text-inv)" }}>{fmtDate(risk.start_by)}</span>
            </div>
          </div>
        </>
      ) : null}

      {cascade && cascade.steps.length > 0 ? (
        <>
          <h2>If missed · cascade</h2>
          <p className="muted" style={{ marginBottom: 12 }}>
            Total exposure <strong style={{ color: "var(--ink)" }}>{fmtINR(cascade.total_exposure_inr)}</strong> across {cascade.step_count} step{cascade.step_count === 1 ? "" : "s"}.
          </p>
          <div className="stagger">
            {cascade.steps.map((s, i) => (
              <div key={`${s.obligation_id}-${i}`} className="card">
                <div className="row">
                  <span className="title">
                    {i === 0 ? "" : (
                      <span style={{ color: "var(--text-3)", marginRight: 6 }}>↳</span>
                    )}
                    {s.obligation_id === ob.id ? s.title : (
                      <Link href={`/obligation/${s.obligation_id}`} style={{ color: "var(--ink)", borderBottom: "1px solid var(--line-2)" }}>
                        {s.title}
                      </Link>
                    )}
                  </span>
                  <span className="meta">{s.reason}</span>
                </div>
                <div className="row" style={{ marginTop: 6 }}>
                  <span className="meta">Direct penalty</span>
                  <span className="meta" style={{ fontVariantNumeric: "tabular-nums", color: "var(--red)", fontWeight: 500 }}>
                    {fmtINR(s.direct_penalty)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </main>
  );
}
