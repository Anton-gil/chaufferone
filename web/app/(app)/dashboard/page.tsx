import Link from "next/link";
import { api, type Obligation } from "@/lib/api";
import { DemoStrip } from "@/components/DemoStrip";

export const dynamic = "force-dynamic";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function parseDue(iso: string | null): Date | null {
  if (!iso) return null;
  const d = new Date(iso + "T00:00:00");
  return Number.isNaN(d.getTime()) ? null : d;
}

function fmtAmount(amount: number | null, currency: string): string {
  if (amount == null) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}

function daysBetween(from: Date, to: Date): number {
  return Math.round((to.getTime() - from.getTime()) / 86_400_000);
}

function groupByBucket(items: Obligation[]) {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const buckets: Record<string, Obligation[]> = { overdue: [], today: [], week: [], later: [], undated: [] };
  for (const o of items) {
    const d = parseDue(o.due_date);
    if (!d) { buckets.undated.push(o); continue; }
    const dd = daysBetween(now, d);
    if (dd < 0) buckets.overdue.push(o);
    else if (dd === 0) buckets.today.push(o);
    else if (dd <= 7) buckets.week.push(o);
    else buckets.later.push(o);
  }
  for (const k of Object.keys(buckets)) {
    buckets[k].sort((a, b) => (a.due_date ?? "").localeCompare(b.due_date ?? ""));
  }
  return buckets;
}

function greeting(now = new Date()): string {
  const h = now.getHours();
  if (h < 5) return "Late tonight";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  if (h < 22) return "Good evening";
  return "Late tonight";
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

export default async function DashboardPage() {
  const { health, obligations, error } = await fetchState();
  const items = obligations ?? [];
  const buckets = groupByBucket(items);
  const nextDue = [...items].filter(o => o.due_date).sort((a, b) => (a.due_date ?? "").localeCompare(b.due_date ?? ""))[0];
  const total = items.reduce((sum, o) => sum + (o.amount ?? 0), 0);
  const red = items.filter(o => o.urgency_tier === "red").length;
  const today = new Date();

  return (
    <main>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">{today.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</span>
          <h1 className="page-title">
            {greeting()}<span className="page-title-accent">— here&apos;s your plan.</span>
          </h1>
        </div>
        <div className="page-header-actions">
          {health ? <span className="status green">connected</span> : <span className="status red">offline</span>}
          <Link href="/money" className="btn-outline">Money forecast →</Link>
        </div>
      </div>

      {!health && error ? (
        <div className="error" style={{ marginBottom: 24 }}>
          Backend unreachable — <code>uv run uvicorn app.main:app --reload</code>. {error}
        </div>
      ) : null}

      {health ? <DemoStrip /> : null}

      <div className="kpi-grid">
        <div className="kpi kpi-dark">
          <div className="kpi-top">
            <span className="kpi-label">Starting balance</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="7" width="18" height="12" rx="2" /><circle cx="17" cy="13" r="1.4" fill="currentColor" /></svg>
            </span>
          </div>
          <div className="kpi-value">₹50,000</div>
          <div className="kpi-delta">Hard floor · ₹5,000</div>
          <svg className="kpi-spark" viewBox="0 0 88 30" fill="none" preserveAspectRatio="none">
            <polyline points="0,20 10,18 20,22 30,15 40,17 50,12 60,14 70,9 80,11 88,7" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Active obligations</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" /><line x1="8" y1="9" x2="16" y2="9" /><line x1="8" y1="13" x2="14" y2="13" /><line x1="8" y1="17" x2="12" y2="17" /></svg>
            </span>
          </div>
          <div className="kpi-value">{items.length}</div>
          <div className="kpi-delta">{red > 0 ? `${red} red · attention` : "Nothing urgent"}</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Owed this window</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M4 6h16M4 12h10M4 18h16" /></svg>
            </span>
          </div>
          <div className="kpi-value">{fmtAmount(total, items[0]?.currency ?? "INR")}</div>
          <div className="kpi-delta">Across {items.length} planned items</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Next due</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="8" /><polyline points="12,7 12,12 15,14" /></svg>
            </span>
          </div>
          <div className="kpi-value" style={{ fontFamily: "var(--font-pixel), VT323, monospace", fontSize: 26 }}>
            {nextDue?.due_date ? formatShortDate(nextDue.due_date) : "—"}
          </div>
          <div className="kpi-delta" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {nextDue?.title ?? "Nothing scheduled"}
          </div>
        </div>
      </div>

      <div className="panels">
        <div className="panel">
          <div className="panel-header">
            <div>
              <span className="panel-eyebrow">Obligations</span>
              <h2 className="panel-title">Upcoming timeline</h2>
            </div>
            <Link href="/graph" className="btn-outline" style={{ padding: "8px 16px", fontSize: 12 }}>View graph</Link>
          </div>

          {items.length === 0 ? (
            <div className="empty-state">
              <strong>No obligations yet.</strong>
              Seed the demo scenario to see the engine in action.
              <div><code>curl -X POST http://localhost:8000/api/demo/seed</code></div>
            </div>
          ) : (
            <>
              <TimelineGroup label="Overdue"    items={buckets.overdue} />
              <TimelineGroup label="Today"      items={buckets.today} />
              <TimelineGroup label="This week"  items={buckets.week} />
              <TimelineGroup label="Later"      items={buckets.later} />
              <TimelineGroup label="No due date" items={buckets.undated} />
            </>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <span className="panel-eyebrow">Engine</span>
              <h2 className="panel-title">System status</h2>
            </div>
            <span className="status green">live</span>
          </div>

          <StatusRow label="Backend" value={health ?? "unreachable"} ok={!!health} />
          <StatusRow label="Voice consent" value="Rules-first · LLM fallback" ok />
          <StatusRow label="Bank SMS" value="Regex templates · local" ok />
          <StatusRow label="Verification" value="Debit-matched" ok />

          <div style={{ marginTop: 16, padding: 16, borderRadius: 12, background: "var(--paper-warm)", border: "1px solid var(--line)" }}>
            <div style={{ fontFamily: "var(--font-pixel), VT323, monospace", fontSize: 13, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--mute)", marginBottom: 6 }}>
              Ingest quick actions
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="btn-outline" style={{ padding: "7px 14px", fontSize: 12 }}>API docs</a>
              <Link href="/money" className="btn-outline" style={{ padding: "7px 14px", fontSize: 12 }}>Money</Link>
              <Link href="/graph" className="btn-outline" style={{ padding: "7px 14px", fontSize: 12 }}>Graph</Link>
              <Link href="/settings" className="btn-outline" style={{ padding: "7px 14px", fontSize: 12 }}>Settings</Link>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function TimelineGroup({ label, items }: { label: string; items: Obligation[] }) {
  if (items.length === 0) return null;
  return (
    <div className="timeline-group">
      <h3 className="timeline-day">{label} · <span style={{ opacity: 0.6 }}>{items.length}</span></h3>
      {items.map(o => <ObligRow key={o.id} o={o} />)}
    </div>
  );
}

function ObligRow({ o }: { o: Obligation }) {
  const d = parseDue(o.due_date);
  return (
    <Link href={`/obligation/${o.id}`} style={{ display: "block" }}>
      <div className="oblig-row">
        <div className="oblig-day-pill">
          <span className="d">{d ? String(d.getDate()).padStart(2, "0") : "--"}</span>
          <span className="m">{d ? MONTHS[d.getMonth()] : "TBD"}</span>
        </div>
        <div className="oblig-main">
          <span className="oblig-title">{o.title}</span>
          <span className="oblig-meta">
            <span>{o.category ?? "uncategorised"}</span>
            <span className="dot">·</span>
            <span>{o.obligation_type}</span>
          </span>
        </div>
        <span className="oblig-amount">{fmtAmount(o.amount, o.currency)}</span>
        <span className={`status ${o.urgency_tier}`}>{o.urgency_tier}</span>
      </div>
    </Link>
  );
}

function StatusRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px dashed var(--line)" }}>
      <span style={{ fontFamily: "var(--font-pixel), VT323, monospace", fontSize: 13, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--mute)" }}>{label}</span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: ok ? "var(--ink)" : "#a00" }}>
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: ok ? "var(--ink)" : "#a00" }} />
        {value}
      </span>
    </div>
  );
}

function formatShortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return iso;
  return `${String(d.getDate()).padStart(2, "0")} ${MONTHS[d.getMonth()]}`;
}
