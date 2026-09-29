"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type Clash, type Fix } from "@/lib/api";

function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
function fmtINR(n: number): string {
  const abs = Math.abs(Math.round(n));
  return (n < 0 ? "-₹" : "₹") + abs.toLocaleString("en-IN");
}
function kindLabel(k: string): string {
  const map: Record<string, string> = {
    defer: "Defer",
    pause_subscription: "Pause",
    reorder: "Reorder",
    pull_forward: "Pull forward",
  };
  return map[k] ?? k;
}

const btnGhost: React.CSSProperties = {
  background: "transparent",
  color: "#c8c8d0",
  border: "1px solid #23232c",
  borderRadius: 6,
  padding: "6px 10px",
  fontSize: 12,
  cursor: "pointer",
};

export function ClashCard({ clash, days }: { clash: Clash; days: number }) {
  const [open, setOpen] = useState(false);
  const [fixes, setFixes] = useState<Fix[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && fixes == null && !loading) {
      setLoading(true);
      setError(null);
      try {
        const rows = await api.fixes(clash.id, days);
        setFixes(rows);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <div className="card">
      <div className="row">
        <span className="title">
          {clash.obligation_titles.join(" · ") || "Cashflow clash"}
        </span>
        <span className={`status ${clash.tier === "floor" ? "red" : "amber"}`}>
          {clash.tier}
        </span>
      </div>
      <div className="row">
        <span className="meta">
          {fmtDate(clash.first_breach_date)} → {fmtDate(clash.last_breach_date)} ·{" "}
          {clash.obligations_involved.length} obligation
          {clash.obligations_involved.length === 1 ? "" : "s"}
        </span>
        <span className="meta">max depth {fmtINR(clash.max_depth_inr)}</span>
      </div>

      <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" onClick={toggle} style={btnGhost}>
          {open ? "Hide fixes" : "Suggested fixes"}
        </button>
        {clash.obligations_involved.map((id, i) => (
          <Link
            key={id}
            href={`/obligation/${id}`}
            style={{ color: "#7ee29a", fontSize: 12, marginRight: 6 }}
          >
            {clash.obligation_titles[i] ?? "view"} →
          </Link>
        ))}
      </div>

      {open ? (
        <div style={{ marginTop: 12, borderTop: "1px solid #23232c", paddingTop: 10 }}>
          {loading ? <p className="muted" style={{ fontSize: 12 }}>Loading…</p> : null}
          {error ? <p className="error" style={{ fontSize: 12 }}>{error}</p> : null}
          {fixes && fixes.length === 0 ? (
            <p className="muted" style={{ fontSize: 12 }}>No fixes proposed.</p>
          ) : null}
          {fixes?.map((f, i) => (
            <div
              key={`${f.obligation_id}-${f.kind}-${i}`}
              style={{
                border: "1px solid #23232c",
                borderRadius: 8,
                padding: "10px 12px",
                marginBottom: 8,
                background: "#0e0e13",
              }}
            >
              <div className="row">
                <span style={{ fontSize: 13, fontWeight: 500 }}>
                  <span
                    style={{
                      display: "inline-block",
                      background: "#23232c",
                      color: "#c8c8d0",
                      padding: "2px 8px",
                      borderRadius: 999,
                      fontSize: 11,
                      marginRight: 8,
                    }}
                  >
                    {kindLabel(f.kind)}
                  </span>
                  {f.obligation_title}
                </span>
                {f.resolves_clash ? (
                  <span className="status green">resolves</span>
                ) : (
                  <span className="status">helps</span>
                )}
              </div>
              <div style={{ fontSize: 12, color: "#c8c8d0", marginTop: 6 }}>{f.description}</div>
              <div className="row" style={{ marginTop: 8 }}>
                <span className="meta">
                  disruption {f.disruption_score}/100 · penalty {fmtINR(f.added_penalty_inr)}
                </span>
                <span className="meta">
                  min balance after: {fmtINR(f.resulting_min_balance_inr)}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
