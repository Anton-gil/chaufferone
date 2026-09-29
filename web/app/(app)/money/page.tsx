import Link from "next/link";
import { api, type DayPoint, type ForecastResponse } from "@/lib/api";

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
  const filled = d.breach_type === "floor";
  return (
    <circle
      r={4.5}
      fill={filled ? "#0a0a0a" : "#ffffff"}
      stroke="#0a0a0a"
      strokeWidth={filled ? 0 : 1.5}
    />
  );
}

export default async function MoneyPage() {
  const { data, error } = await fetchForecast();

  if (error || !data) {
    return (
      <main>
        <div className="page-header">
          <div className="page-header-left">
            <span className="page-eyebrow">Money engine</span>
            <h1 className="page-title">Oracle<span className="page-title-accent">— cashflow forecast.</span></h1>
          </div>
        </div>
        <div className="error">Failed to load forecast. {error}</div>
      </main>
    );
  }

  const chart = buildChart(data);
  const breachDays = data.days.filter((d) => d.breach_type !== "none");
  const floorBreaches = data.days.filter((d) => d.breach_type === "floor").length;
  const minBalance = data.days.reduce((m, d) => Math.min(m, d.closing_balance), Infinity);
  const finalBalance = data.days[data.days.length - 1]?.closing_balance ?? data.starting_balance_inr;

  return (
    <main>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">Money engine · {data.horizon_days} days</span>
          <h1 className="page-title">Oracle<span className="page-title-accent">— cashflow forecast.</span></h1>
        </div>
        <div className="page-header-actions">
          <span className="status">starting {fmtINR(data.starting_balance_inr)}</span>
          <Link href="/graph" className="btn-outline">Graph →</Link>
        </div>
      </div>

      <div className="kpi-grid">
        <div className="kpi kpi-dark">
          <div className="kpi-top">
            <span className="kpi-label">End-of-window balance</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="7" width="18" height="12" rx="2" /><circle cx="17" cy="13" r="1.4" fill="currentColor" /></svg>
            </span>
          </div>
          <div className="kpi-value">{fmtINR(finalBalance)}</div>
          <div className="kpi-delta">After all planned debits</div>
          <svg className="kpi-spark" viewBox="0 0 88 30" fill="none" preserveAspectRatio="none">
            <polyline
              points={data.days
                .filter((_, i) => i % Math.max(1, Math.floor(data.days.length / 20)) === 0)
                .map((d, i, arr) => {
                  const x = (i / Math.max(1, arr.length - 1)) * 88;
                  const range = Math.max(1, Math.max(...arr.map(a => a.closing_balance)) - Math.min(...arr.map(a => a.closing_balance)));
                  const y = 28 - ((d.closing_balance - Math.min(...arr.map(a => a.closing_balance))) / range) * 26;
                  return `${x.toFixed(1)},${y.toFixed(1)}`;
                })
                .join(" ")}
              stroke="currentColor"
              strokeWidth="1.2"
            />
          </svg>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Hard floor</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="18" x2="20" y2="18" /><line x1="4" y1="18" x2="4" y2="14" strokeDasharray="2 2" /><line x1="20" y1="18" x2="20" y2="14" strokeDasharray="2 2" /></svg>
            </span>
          </div>
          <div className="kpi-value">{fmtINR(data.hard_floor_inr)}</div>
          <div className="kpi-delta">Cushion +{fmtINR(data.soft_cushion_inr)}</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Lowest point</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><polyline points="4,7 10,15 14,11 20,18" /><circle cx="14" cy="11" r="1.5" fill="currentColor" /></svg>
            </span>
          </div>
          <div className="kpi-value">{fmtINR(Number.isFinite(minBalance) ? minBalance : 0)}</div>
          <div className="kpi-delta">{minBalance < data.hard_floor_inr ? "Below hard floor" : "Stays above floor"}</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Breach days</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="8" /><line x1="12" y1="8" x2="12" y2="12" /><circle cx="12" cy="16" r="0.8" fill="currentColor" /></svg>
            </span>
          </div>
          <div className="kpi-value">{breachDays.length}</div>
          <div className="kpi-delta">{floorBreaches} floor · {breachDays.length - floorBreaches} cushion</div>
        </div>
      </div>

      <div className="panel money-chart-panel">
        <div className="panel-header">
          <div>
            <span className="panel-eyebrow">Daily closing balance</span>
            <h2 className="panel-title">45-day forecast</h2>
          </div>
          <div className="money-legend">
            <span className="money-legend-item"><span className="money-legend-line" /> Balance</span>
            <span className="money-legend-item"><span className="money-legend-line dashed" /> Cushion</span>
            <span className="money-legend-item"><span className="money-legend-line dashed strong" /> Floor</span>
            <span className="money-legend-item"><span className="money-legend-dot filled" /> Floor breach</span>
            <span className="money-legend-item"><span className="money-legend-dot" /> Cushion breach</span>
          </div>
        </div>
        {chart ? (
          <div className="money-chart-scroll">
            <svg width={CHART_W} height={CHART_H} viewBox={`0 0 ${CHART_W} ${CHART_H}`} role="img" aria-label="Balance forecast">
              <defs>
                <linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0a0a0a" stopOpacity="0.14" />
                  <stop offset="100%" stopColor="#0a0a0a" stopOpacity="0" />
                </linearGradient>
                <pattern id="chart-dots" width="12" height="12" patternUnits="userSpaceOnUse">
                  <circle cx="1" cy="1" r="0.8" fill="rgba(10,10,10,0.06)" />
                </pattern>
              </defs>

              <rect x={PAD_L} y={PAD_T} width={CHART_W - PAD_L - PAD_R} height={CHART_H - PAD_T - PAD_B} fill="url(#chart-dots)" />

              {chart.yTicks.map((t, i) => (
                <g key={`yt${i}`}>
                  <line x1={PAD_L} x2={CHART_W - PAD_R} y1={t.y} y2={t.y} stroke="#e6e6e2" />
                  <text x={PAD_L - 8} y={t.y + 3} fill="#8a8a83" fontSize={10} textAnchor="end" style={{ fontFamily: "var(--font-pixel), VT323, monospace", letterSpacing: "0.04em" }}>{fmtINR(t.v)}</text>
                </g>
              ))}

              <line x1={PAD_L} x2={CHART_W - PAD_R} y1={chart.cushionY} y2={chart.cushionY} stroke="#4a4a45" strokeDasharray="4 4" strokeWidth={1} opacity={0.55} />
              <line x1={PAD_L} x2={CHART_W - PAD_R} y1={chart.floorY} y2={chart.floorY} stroke="#0a0a0a" strokeDasharray="4 4" strokeWidth={1.25} opacity={0.85} />
              {chart.zeroY != null ? (
                <line x1={PAD_L} x2={CHART_W - PAD_R} y1={chart.zeroY} y2={chart.zeroY} stroke="#cfcfc8" strokeWidth={1} />
              ) : null}

              <path d={chart.areaPath} fill="url(#area-fill)" />
              <path d={chart.linePath} fill="none" stroke="#0a0a0a" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" />

              {data.days.map((d, i) => (
                <g key={`bd${i}`} transform={`translate(${chart.xAt(i)},${chart.yAt(d.closing_balance)})`}>
                  <BreachDot d={d} />
                </g>
              ))}

              {chart.xLabels.map((xl) => (
                <text key={`xl${xl.i}`} x={chart.xAt(xl.i)} y={CHART_H - 10} fill="#8a8a83" fontSize={10} textAnchor="middle" style={{ fontFamily: "var(--font-pixel), VT323, monospace", letterSpacing: "0.06em" }}>{xl.label}</text>
              ))}
            </svg>
          </div>
        ) : null}
      </div>

      <div className="panel" style={{ marginTop: 20 }}>
        <div className="panel-header">
          <div>
            <span className="panel-eyebrow">Cashflow risk</span>
            <h2 className="panel-title">Clashes</h2>
          </div>
          <span className="status">{data.clashes.length} detected</span>
        </div>

        {data.clashes.length === 0 ? (
          <div className="empty-state">
            <strong>No clashes in the {data.horizon_days}-day window.</strong>
            The engine sees no case where your balance would drop below the hard floor.
          </div>
        ) : (
          data.clashes.map((c) => (
            <div key={c.id} className="clash-card">
              <div className="clash-head">
                <div>
                  <div className="clash-title">{c.obligation_titles.join(" · ") || "Cashflow clash"}</div>
                  <div className="clash-meta">
                    <span>{fmtDate(c.first_breach_date)} → {fmtDate(c.last_breach_date)}</span>
                    <span className="dot">·</span>
                    <span>{c.obligations_involved.length} obligation{c.obligations_involved.length === 1 ? "" : "s"}</span>
                    <span className="dot">·</span>
                    <span style={{ fontFamily: "var(--font-pixel), VT323, monospace", letterSpacing: "0.04em" }}>max depth {fmtINR(c.max_depth_inr)}</span>
                  </div>
                </div>
                <span className={`status ${c.tier === "floor" ? "red" : "amber"}`}>{c.tier}</span>
              </div>
              {c.obligations_involved.length > 0 ? (
                <div className="clash-links">
                  {c.obligations_involved.map((id, i) => (
                    <Link key={id} href={`/obligation/${id}`} className="clash-link">
                      {c.obligation_titles[i] ?? "view"} <span aria-hidden="true">→</span>
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>
    </main>
  );
}
