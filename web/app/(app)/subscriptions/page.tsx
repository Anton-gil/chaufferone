import Link from "next/link";
import { api, type Obligation, type ObligationSource } from "@/lib/api";

export const dynamic = "force-dynamic";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function fmtAmount(amount: number | null, currency: string): string {
  if (amount == null) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}

function isRecurring(o: Obligation): boolean {
  if (o.obligation_type === "renewal" || o.obligation_type === "event") return true;
  if ((o.category ?? "").toLowerCase() === "subscription") return true;
  return false;
}

function sourceColor(type: string): { bg: string; fg: string } {
  const t = type.toLowerCase();
  if (t === "gmail" || t === "email") return { bg: "#1a2f1e", fg: "#7ee29a" };
  if (t === "whatsapp") return { bg: "#0f2b28", fg: "#4bd3b7" };
  if (t === "sms") return { bg: "#2b1f0f", fg: "#f0c674" };
  if (t === "manual") return { bg: "#231a2b", fg: "#c69cf0" };
  return { bg: "#1a1a22", fg: "#8a8a94" };
}

function SourceBadge({ s }: { s: ObligationSource }) {
  const { bg, fg } = sourceColor(s.type);
  return (
    <span
      title={s.label ?? `${s.type}: ${s.ref}`}
      style={{
        background: bg,
        color: fg,
        border: `1px solid ${fg}22`,
        borderRadius: 4,
        padding: "2px 6px",
        fontSize: 11,
        fontFamily: "ui-monospace, monospace",
        whiteSpace: "nowrap",
      }}
    >
      {s.type}
    </span>
  );
}

async function load(): Promise<{ items: Obligation[]; error: string | null }> {
  try {
    const t = await api.timeline();
    return { items: t.filter(isRecurring), error: null };
  } catch (e) {
    return { items: [], error: (e as Error).message };
  }
}

export default async function SubscriptionsPage() {
  const { items, error } = await load();
  const gmailCount = items.filter((o) =>
    (o.sources ?? []).some((s) => s.type.toLowerCase() === "gmail" || s.type.toLowerCase() === "email"),
  ).length;

  return (
    <main style={{ maxWidth: 1100 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1>Subscriptions & recurring</h1>
          <p className="muted" style={{ marginTop: 4 }}>
            Renewals, recurring events, and subscription-category items. Source badges show where each one came from.
          </p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span className="muted" style={{ fontSize: 13 }}>
            {items.length} recurring · {gmailCount} from Gmail
          </span>
          <Link href="/settings" className="btn-outline" style={{ padding: "6px 12px", fontSize: 13 }}>
            Scan inbox
          </Link>
        </div>
      </div>

      {error ? <div className="error">{error}</div> : null}

      {items.length === 0 && !error ? (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
            No recurring obligations yet. Try <Link href="/settings">Scan inbox now</Link> after connecting Gmail.
          </p>
        </div>
      ) : null}

      {items.length > 0 ? (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#0e0e13", color: "#8a8a94", textAlign: "left" }}>
                <th style={cellStyle}>Title</th>
                <th style={cellStyle}>Vendor</th>
                <th style={cellStyle}>Type</th>
                <th style={cellStyle}>Category</th>
                <th style={{ ...cellStyle, textAlign: "right" }}>Amount</th>
                <th style={cellStyle}>Due</th>
                <th style={cellStyle}>Source</th>
              </tr>
            </thead>
            <tbody>
              {items.map((o) => (
                <tr key={o.id} style={{ borderTop: "1px solid #1a1a22" }}>
                  <td style={cellStyle}>
                    <Link href={`/obligation/${o.id}`} style={{ color: "#e8e8ec" }}>
                      {o.title}
                    </Link>
                  </td>
                  <td style={{ ...cellStyle, color: "#c8c8d0" }}>{o.vendor ?? "—"}</td>
                  <td style={{ ...cellStyle, color: "#c8c8d0" }}>{o.obligation_type}</td>
                  <td style={{ ...cellStyle, color: "#c8c8d0" }}>{o.category ?? "—"}</td>
                  <td style={{ ...cellStyle, textAlign: "right", color: "#e8e8ec" }}>
                    {fmtAmount(o.amount, o.currency)}
                  </td>
                  <td style={{ ...cellStyle, color: "#c8c8d0" }}>{fmtDate(o.due_date)}</td>
                  <td style={cellStyle}>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {(o.sources ?? []).length === 0 ? (
                        <span className="muted" style={{ fontSize: 11 }}>—</span>
                      ) : (
                        (o.sources ?? []).map((s, i) => <SourceBadge key={i} s={s} />)
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </main>
  );
}

const cellStyle: React.CSSProperties = {
  padding: "10px 14px",
  verticalAlign: "top",
};
