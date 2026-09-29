import { api, type Insights } from "@/lib/api";

export const dynamic = "force-dynamic";

function fmtInr(n: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}

async function load(): Promise<{ data: Insights | null; error: string | null }> {
  try {
    return { data: await api.insights(60), error: null };
  } catch (e) {
    return { data: null, error: (e as Error).message };
  }
}

export default async function InsightsPage() {
  const { data, error } = await load();
  if (error) {
    return (
      <main>
        <h1 className="page-title">Insights</h1>
        <p className="error">{error}</p>
      </main>
    );
  }
  if (!data) return null;
  const gap = data.buffer_touch.closest_gap_to_floor_inr;
  const tone = gap < 0 ? "#ff8a95" : gap < data.buffer_touch.cushion_inr ? "#f5c469" : "#7ee29a";

  return (
    <main>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">Last {data.window_days} days</span>
          <h1 className="page-title">Insights</h1>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, marginBottom: 20 }}>
        <div className="card">
          <div className="muted">Verified spend</div>
          <div style={{ fontSize: 28, fontWeight: 600, marginTop: 6 }}>{fmtInr(data.totals.spent_inr)}</div>
          <div className="muted" style={{ fontSize: 12 }}>{data.totals.verified_count} confirmed payments</div>
        </div>
        <div className="card">
          <div className="muted">Closest to buffer floor</div>
          <div style={{ fontSize: 28, fontWeight: 600, marginTop: 6, color: tone }}>
            {gap < 0 ? `-${fmtInr(Math.abs(gap))}` : fmtInr(gap)}
          </div>
          <div className="muted" style={{ fontSize: 12 }}>
            Floor {fmtInr(data.buffer_touch.floor_inr)} · cushion {fmtInr(data.buffer_touch.cushion_inr)}
          </div>
        </div>
        <div className="card">
          <div className="muted">Dead subscriptions</div>
          <div style={{ fontSize: 28, fontWeight: 600, marginTop: 6 }}>{data.dead_subscriptions.length}</div>
          <div className="muted" style={{ fontSize: 12 }}>No debit in {data.window_days} days</div>
        </div>
      </div>

      <h2>Spend by category</h2>
      <div className="card">
        {data.by_category.length === 0 ? (
          <p className="muted" style={{ marginTop: 0 }}>
            No verified debits yet — insights fill in as bank SMS confirmations arrive.
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {data.by_category.map((row) => (
                <tr key={row.category} style={{ borderBottom: "1px solid #1a1a20" }}>
                  <td style={{ padding: "8px 0" }}>{row.category}</td>
                  <td style={{ padding: "8px 0", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                    {fmtInr(row.total_inr)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <h2>Top vendors</h2>
      <div className="card">
        {data.top_vendors.length === 0 ? (
          <p className="muted" style={{ marginTop: 0 }}>Nothing verified in the window.</p>
        ) : (
          <ol style={{ margin: 0, paddingLeft: 20 }}>
            {data.top_vendors.map((v) => (
              <li key={v.vendor} style={{ padding: "4px 0" }}>
                {v.vendor} <span className="muted">{fmtInr(v.total_inr)}</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      {data.dead_subscriptions.length > 0 ? (
        <>
          <h2>Consider pausing</h2>
          <div className="card">
            <p className="muted" style={{ marginTop: 0 }}>
              No debit in the last {data.window_days} days. Pause it in your UPI app before the next charge.
            </p>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {data.dead_subscriptions.map((s) => (
                <li key={s.id} style={{ padding: "4px 0" }}>
                  {s.title} {s.amount_inr ? <span className="muted">({fmtInr(s.amount_inr)}/mo)</span> : null}
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </main>
  );
}
