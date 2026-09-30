import Link from "next/link";
import { api, type Obligation, type ObligationSource } from "@/lib/api";

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

function isRecurring(o: Obligation): boolean {
  if (o.obligation_type === "renewal" || o.obligation_type === "event") return true;
  if ((o.category ?? "").toLowerCase() === "subscription") return true;
  return false;
}

function isGmailSource(type: string): boolean {
  const t = type.toLowerCase();
  return t === "gmail" || t === "email";
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

async function fetchState(): Promise<{ health: string | null; items: Obligation[]; error: string | null }> {
  try {
    const [h, t] = await Promise.all([api.health(), api.timeline()]);
    return { health: h.status, items: t.filter(isRecurring), error: null };
  } catch (e) {
    return { health: null, items: [], error: (e as Error).message };
  }
}

export default async function SubscriptionsPage() {
  const { health, items, error } = await fetchState();

  const gmailItems = items.filter((o) => (o.sources ?? []).some((s) => isGmailSource(s.type)));
  const totalValue = items.reduce((sum, o) => sum + (o.amount ?? 0), 0);
  const autopay = items.filter((o) => o.verification_state?.startsWith("pre_debit")).length;
  const buckets = groupByBucket(items);

  const sourceCounts = new Map<string, number>();
  for (const o of items) {
    for (const s of o.sources ?? []) {
      const key = s.type.toLowerCase();
      sourceCounts.set(key, (sourceCounts.get(key) ?? 0) + 1);
    }
  }

  return (
    <main>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">Recurring</span>
          <h1 className="page-title">
            Subscriptions<span className="page-title-accent">— every renewal, one glance.</span>
          </h1>
        </div>
        <div className="page-header-actions">
          {health ? <span className="status green">connected</span> : <span className="status red">offline</span>}
          <Link href="/settings" className="btn-outline">Scan inbox →</Link>
        </div>
      </div>

      {!health && error ? (
        <div className="error" style={{ marginBottom: 24 }}>
          Backend unreachable — <code>uv run uvicorn app.main:app --reload</code>. {error}
        </div>
      ) : null}

      <div className="kpi-grid">
        <div className="kpi kpi-dark">
          <div className="kpi-top">
            <span className="kpi-label">From Gmail</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 7l9 6 9-6" /></svg>
            </span>
          </div>
          <div className="kpi-value">{gmailItems.length}</div>
          <div className="kpi-delta">Parsed straight from your inbox</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Recurring items</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 0 1 4-4h14" /><polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 0 1-4 4H3" /></svg>
            </span>
          </div>
          <div className="kpi-value">{items.length}</div>
          <div className="kpi-delta">Renewals, events & subscriptions</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Total value</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M4 6h16M4 12h10M4 18h16" /></svg>
            </span>
          </div>
          <div className="kpi-value">{fmtAmount(totalValue, items[0]?.currency ?? "INR")}</div>
          <div className="kpi-delta">Across {items.length} tracked items</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">On UPI AutoPay</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="7" width="18" height="12" rx="2" /><circle cx="17" cy="13" r="1.4" fill="currentColor" /></svg>
            </span>
          </div>
          <div className="kpi-value">{autopay}</div>
          <div className="kpi-delta">Confirmed via bank pre-debit SMS</div>
        </div>
      </div>

      <div className="panels">
        <div className="panel">
          <div className="panel-header">
            <div>
              <span className="panel-eyebrow">Timeline</span>
              <h2 className="panel-title">Recurring & renewals</h2>
            </div>
          </div>

          {items.length === 0 ? (
            <div className="empty-state">
              <strong>No recurring obligations yet.</strong>
              Connect Gmail and scan your inbox to pull in renewals and subscriptions.
              <div><code>Settings → Connect Gmail → Scan inbox now</code></div>
            </div>
          ) : (
            <>
              <SubGroup label="Overdue" items={buckets.overdue} />
              <SubGroup label="Today" items={buckets.today} />
              <SubGroup label="This week" items={buckets.week} />
              <SubGroup label="Later" items={buckets.later} />
              <SubGroup label="No due date" items={buckets.undated} />
            </>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <span className="panel-eyebrow">Provenance</span>
              <h2 className="panel-title">Where these came from</h2>
            </div>
          </div>

          {sourceCounts.size === 0 ? (
            <p className="muted">No sources yet.</p>
          ) : (
            [...sourceCounts.entries()]
              .sort((a, b) => b[1] - a[1])
              .map(([type, count]) => <SourceCountRow key={type} label={type} count={count} />)
          )}

          <div style={{ marginTop: 16, padding: 16, borderRadius: 12, background: "var(--paper-warm)", border: "1px solid var(--line)" }}>
            <div style={{ fontFamily: "var(--font-pixel), VT323, monospace", fontSize: 13, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--mute)", marginBottom: 6 }}>
              Quick actions
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Link href="/settings" className="btn-outline" style={{ padding: "7px 14px", fontSize: 12 }}>Connect Gmail</Link>
              <Link href="/settings" className="btn-outline" style={{ padding: "7px 14px", fontSize: 12 }}>Scan inbox now</Link>
              <Link href="/dashboard" className="btn-outline" style={{ padding: "7px 14px", fontSize: 12 }}>Timeline</Link>
            </div>
          </div>
        </div>
      </div>

      <p className="muted" style={{ marginTop: 20, fontSize: 12 }}>
        Chaufferone never touches your UPI mandate. Pause or cancel from your UPI app; we&apos;ll pick up the change from the next bank SMS.
      </p>
    </main>
  );
}

function SubGroup({ label, items }: { label: string; items: Obligation[] }) {
  if (items.length === 0) return null;
  return (
    <div className="timeline-group">
      <h3 className="timeline-day">{label} · <span style={{ opacity: 0.6 }}>{items.length}</span></h3>
      {items.map((o) => <SubRow key={o.id} o={o} />)}
    </div>
  );
}

function SubRow({ o }: { o: Obligation }) {
  const d = parseDue(o.due_date);
  const sources = o.sources ?? [];
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
            {sources.length > 0 ? <span className="dot">·</span> : null}
            {sources.map((s: ObligationSource, i: number) => (
              <span key={i} className={`source-tag ${isGmailSource(s.type) ? "gmail" : ""}`} title={s.label ?? s.ref}>
                {s.type}
              </span>
            ))}
          </span>
        </div>
        <span className="oblig-amount">{fmtAmount(o.amount, o.currency)}</span>
        <span className={`status ${o.urgency_tier}`}>{o.urgency_tier}</span>
      </div>
    </Link>
  );
}

function SourceCountRow({ label, count }: { label: string; count: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px dashed var(--line)" }}>
      <span style={{ fontFamily: "var(--font-pixel), VT323, monospace", fontSize: 13, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--mute)" }}>
        {label}
      </span>
      <span style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)" }}>{count}</span>
    </div>
  );
}
