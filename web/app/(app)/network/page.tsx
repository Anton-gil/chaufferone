import { api, type NetworkLog } from "@/lib/api";

export const dynamic = "force-dynamic";

async function load(): Promise<{ data: NetworkLog | null; error: string | null }> {
  try {
    return { data: await api.networkLog(200), error: null };
  } catch (e) {
    return { data: null, error: (e as Error).message };
  }
}

function fmt(at: string | null): string {
  if (!at) return "—";
  try {
    return new Date(at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return at;
  }
}

export default async function NetworkPage() {
  const { data, error } = await load();

  return (
    <main>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">Privacy</span>
          <h1 className="page-title">Network</h1>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <p style={{ marginTop: 0 }}>
          Every outbound connection this engine has made. Nothing else leaves your device.
          No message bodies, no auth tokens, no user data — only the host we reached and why.
        </p>
        {data ? (
          <p className="muted" style={{ marginBottom: 0 }}>
            {data.count} calls · hosts contacted: {data.hosts.length === 0 ? "none yet" : data.hosts.join(", ")}
          </p>
        ) : null}
      </div>

      {error ? <p className="error">{error}</p> : null}

      <h2>Recent calls</h2>
      <div className="card">
        {!data || data.rows.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            No outbound calls yet — try connecting Gmail or running an ingest.
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", color: "#8a8a94" }}>
                <th style={{ padding: "6px 0" }}>When</th>
                <th style={{ padding: "6px 0" }}>Host</th>
                <th style={{ padding: "6px 0" }}>Purpose</th>
                <th style={{ padding: "6px 0" }}>Result</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.id} style={{ borderTop: "1px solid #1a1a20" }}>
                  <td style={{ padding: "6px 0", color: "#a0a0aa", fontVariantNumeric: "tabular-nums" }}>{fmt(r.at)}</td>
                  <td style={{ padding: "6px 0" }}>{r.host}</td>
                  <td style={{ padding: "6px 0", color: "#c8c8d0" }}>{r.purpose}</td>
                  <td style={{ padding: "6px 0", color: r.ok ? "#7ee29a" : "#ff8a95" }}>
                    {r.ok ? "ok" : r.reason ?? "failed"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
