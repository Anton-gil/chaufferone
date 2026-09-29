import Link from "next/link";
import { api, type DayPoint, type ForecastResponse } from "@/lib/api";
import { CountUp } from "@/components/CountUp";

export const dynamic = "force-dynamic";

const CHART_W = 900;
const CHART_H = 260;
const PAD_L = 60;
const PAD_R = 20;
const PAD_T = 20;
const PAD_B = 30;

function fmtINR(n: number): string {
  return "₹" + Math.round(n).toLocaleString("en-IN");
}
function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function niceStep(raw: number): number {
  if (raw <= 0) return 1;
  const exp = Math.floor(Math.log10(raw));
  const base = Math.pow(10, exp);
  const rel = raw / base;
  const nice = rel < 1.5 ? 1 : rel < 3.5 ? 2 : rel < 7.5 ? 5 : 10;
  return nice * base;
}

function buildChart(forecast: ForecastResponse) {
  const days = forecast.days;
  if (days.length === 0) return null;
  const closings = days.map((d) => d.closing_balance);
  const minY = Math.min(0, forecast.hard_floor_inr, ...closings);
  const maxY = Math.max(forecast.hard_floor_inr + forecast.soft_cushion_inr, ...closings);
  const rangeY = Math.max(1, maxY - minY);
  const innerW = CHART_W - PAD_L - PAD_R;
  const innerH = CHART_H - PAD_T - PAD_B;

  const xAt = (i: number) =>
    PAD_L + (days.length > 1 ? (innerW * i) / (days.length - 1) : innerW / 2);
  const yAt = (v: number) => PAD_T + innerH - ((v - minY) / rangeY) * innerH;

  const linePath = closings
    .map((v, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`)
    .join(" ");

  const areaPath =
    linePath +
    ` L${xAt(days.length - 1).toFixed(1)},${yAt(minY).toFixed(1)}` +
    ` L${xAt(0).toFixed(1)},${yAt(minY).toFixed(1)} Z`;

  const floorY = yAt(forecast.hard_floor_inr);
  const cushionY = yAt(forecast.hard_floor_inr + forecast.soft_cushion_inr);
  const zeroY = minY < 0 ? yAt(0) : null;

  const yTicks: { v: number; y: number }[] = [];
  const step = niceStep(rangeY / 4);
  for (let v = Math.ceil(minY / step) * step; v <= maxY; v += step) {
    yTicks.push({ v, y: yAt(v) });
  }

  const xLabels: { i: number; label: string }[] = [];
  const labelEvery = Math.max(1, Math.floor(days.length / 6));
  days.forEach((d, i) => {
    if (i % labelEvery === 0 || i === days.length - 1) xLabels.push({ i, label: fmtDate(d.date) });
  });

  return { xAt, yAt, linePath, areaPath, floorY, cushionY, zeroY, yTicks, xLabels };
}

async function fetchForecast() {
  try {
    return { data: await api.forecast(45), error: null as string | null };
  } catch (e) {
    return { data: null, error: (e as Error).message };
  }
}

function BreachDot({ d }: { d: DayPoint }) {
  if (d.breach_type === "none") return null;
  const color = d.breach_type === "floor" ? "#ff8a95" : "#ffc078";
  return <circle r={4} fill={color} stroke="#0a0a0f" strokeWidth={1.2} />;
}

export default async function MoneyPage() {
  const { data, error } = await fetchForecast();

  if (error || !data) {
    return (
      <main>
        <div className="eyebrow" style={{ marginBottom: 12 }}>Cashflow · ORACLE</div>
        <h1>Money</h1>
        <p className="muted">Cashflow forecast and clashes.</p>
        <div className="error" style={{ marginTop: 16 }}>Failed to load forecast. {error}</div>
      </main>
    );
  }

  const chart = buildChart(data);
  const breachDays = data.days.filter((d) => d.breach_type !== "none");

  return (
    <main style={{ maxWidth: "none", padding: 0 }}>
      <div className="eyebrow" style={{ marginBottom: 12 }}>Cashflow · ORACLE</div>
      <h1>Ninety days as a barcode.</h1>
      <p className="muted" style={{ marginTop: 8 }}>
        Forecast · {data.horizon_days} days · starting balance {fmtINR(data.starting_balance_inr)}
      </p>

      <div className="grid-3" style={{ marginTop: 28, marginBottom: 8 }}>
        <div className="card" style={{ padding: "20px 22px" }}>
          <div className="meta" style={{ letterSpacing: "0.06em", textTransform: "uppercase", fontSize: 10.5 }}>Hard floor</div>
          <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em", marginTop: 4, color: "var(--red)" }}>
            ₹<CountUp value={data.hard_floor_inr} />
          </div>
          <div className="progress" style={{ marginTop: 10 }}><span style={{ width: "30%" }} /></div>
        </div>
        <div className="card" style={{ padding: "20px 22px" }}>
          <div className="meta" style={{ letterSpacing: "0.06em", textTransform: "uppercase", fontSize: 10.5 }}>Soft cushion</div>
          <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em", marginTop: 4, color: "var(--amber)" }}>
            ₹<CountUp value={data.soft_cushion_inr} />
          </div>
          <div className="progress" style={{ marginTop: 10 }}><span style={{ width: "62%" }} /></div>
        </div>
        <div className="card" style={{ padding: "20px 22px" }}>
          <div className="meta" style={{ letterSpacing: "0.06em", textTransform: "uppercase", fontSize: 10.5 }}>Days with breach</div>
          <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em", marginTop: 4 }}>
            <CountUp value={breachDays.length} />
            <span style={{ fontSize: 13, color: "var(--text-3)", marginLeft: 6, fontWeight: 500 }}>
              of {data.horizon_days}
            </span>
          </div>
          <div className="progress" style={{ marginTop: 10 }}>
            <span style={{ width: `${Math.min(100, (breachDays.length / Math.max(1, data.horizon_days)) * 100)}%` }} />
          </div>
        </div>
      </div>

      <h2>Balance Forecast</h2>
      {chart ? (
        <div className="viz-surface">
          <div className="viz-header">
            <div>
              <div className="viz-title">Every hairline is a day.</div>
              <div className="viz-sub">closing balance · daily · {data.horizon_days}-day horizon</div>
            </div>
            <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-inv-2)" }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: "#eaeaef" }} /> Balance
              </span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-inv-2)" }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: "#ff8a95" }} /> Floor breach
              </span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-inv-2)" }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: "#ffc078" }} /> Cushion dip
              </span>
            </div>
          </div>
          <div className="viz-svg-wrap">
            <svg width={CHART_W} height={CHART_H} viewBox={`0 0 ${CHART_W} ${CHART_H}`} role="img" aria-label="Balance forecast">
              {chart.yTicks.map((t, i) => (
                <g key={`yt${i}`}>
                  <line x1={PAD_L} x2={CHART_W - PAD_R} y1={t.y} y2={t.y} stroke="rgba(255,255,255,0.06)" />
                  <text x={PAD_L - 8} y={t.y + 3} fill="rgba(255,255,255,0.5)" fontSize={10} textAnchor="end">{fmtINR(t.v)}</text>
                </g>
              ))}

              <line x1={PAD_L} x2={CHART_W - PAD_R} y1={chart.cushionY} y2={chart.cushionY} stroke="#ffc078" strokeDasharray="4 4" strokeWidth={1} opacity={0.55} />
              <line x1={PAD_L} x2={CHART_W - PAD_R} y1={chart.floorY} y2={chart.floorY} stroke="#ff8a95" strokeDasharray="4 4" strokeWidth={1} opacity={0.55} />
              {chart.zeroY != null ? (
                <line x1={PAD_L} x2={CHART_W - PAD_R} y1={chart.zeroY} y2={chart.zeroY} stroke="rgba(255,255,255,0.24)" strokeWidth={1} />
              ) : null}

              <path d={chart.areaPath} fill="#f5f4ef" opacity={0.08} />
              <path d={chart.linePath} className="line-anim" fill="none" stroke="#f5f4ef" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" />

              {data.days.map((d, i) => (
                <g key={`bd${i}`} transform={`translate(${chart.xAt(i)},${chart.yAt(d.closing_balance)})`}>
                  <BreachDot d={d} />
                </g>
              ))}

              {chart.xLabels.map((xl) => (
                <text key={`xl${xl.i}`} x={chart.xAt(xl.i)} y={CHART_H - 10} fill="rgba(255,255,255,0.5)" fontSize={10} textAnchor="middle">{xl.label}</text>
              ))}
            </svg>
          </div>
        </div>
      ) : null}

      <h2>Clashes</h2>
      {data.clashes.length === 0 ? (
        <div className="card" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="status green">Clear</span>
          <span className="muted">No clashes in the {data.horizon_days}-day window.</span>
        </div>
      ) : (
        <div className="stagger">
          {data.clashes.map((c) => (
            <div key={c.id} className="card">
              <div className="row">
                <span className="title">
                  {c.obligation_titles.join(" · ") || "Cashflow clash"}
                </span>
                <span className={`status ${c.tier === "floor" ? "red" : "amber"}`}>
                  {c.tier}
                </span>
              </div>
              <div className="row">
                <span className="meta">
                  {fmtDate(c.first_breach_date)} → {fmtDate(c.last_breach_date)} ·{" "}
                  {c.obligations_involved.length} obligation
                  {c.obligations_involved.length === 1 ? "" : "s"}
                </span>
                <span className="meta" style={{ fontVariantNumeric: "tabular-nums" }}>max depth {fmtINR(c.max_depth_inr)}</span>
              </div>
              {c.obligations_involved.length > 0 ? (
                <div style={{ marginTop: 8, fontSize: 12, display: "flex", gap: 12, flexWrap: "wrap" }}>
                  {c.obligations_involved.map((id, i) => (
                    <Link
                      key={id}
                      href={`/obligation/${id}`}
                      style={{ color: "var(--ink)", borderBottom: "1px solid var(--line-2)", paddingBottom: 1 }}
                    >
                      {c.obligation_titles[i] ?? "view"} →
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
