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

// Uses .btn-ghost from design system.

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
        <button type="button" onClick={toggle} className="btn-ghost">
          {open ? "Hide fixes" : "Suggested fixes →"}
        </button>
        {clash.obligations_involved.map((id, i) => (
          <Link
            key={id}
            href={`/obligation/${id}`}
            style={{ color: "var(--ink)", fontSize: 12, borderBottom: "1px solid var(--line-2)", paddingBottom: 1 }}
          >
            {clash.obligation_titles[i] ?? "view"} →
          </Link>
        ))}
      </div>

      {open ? (
        <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
          {loading ? <p className="muted" style={{ fontSize: 12 }}>Loading…</p> : null}
          {error ? <p className="error" style={{ fontSize: 12 }}>{error}</p> : null}
          {fixes && fixes.length === 0 ? (
            <p className="muted" style={{ fontSize: 12 }}>No fixes proposed.</p>
          ) : null}
          {fixes?.map((f, i) => (
            <div
              key={`${f.obligation_id}-${f.kind}-${i}`}
              style={{
                border: "1px solid var(--line)",
                borderRadius: 12,
                padding: "12px 14px",
                marginBottom: 8,
                background: "var(--paper-2)",
              }}
            >
              <div className="row">
                <span style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>
                  <span
                    style={{
                      display: "inline-block",
                      background: "var(--ink)",
                      color: "var(--text-inv)",
                      padding: "2px 10px",
                      borderRadius: 999,
                      fontSize: 10.5,
                      marginRight: 8,
                      letterSpacing: "0.05em",
                      textTransform: "uppercase",
                      fontWeight: 600,
                    }}
                  >
                    {kindLabel(f.kind)}
                  </span>
                  {f.obligation_title}
                </span>
                {f.resolves_clash ? (
                  <span className="status green">resolves</span>
                ) : (
                  <span className="status amber">helps</span>
                )}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 6 }}>{f.description}</div>
              <div className="row" style={{ marginTop: 8 }}>
                <span className="meta">
                  disruption {f.disruption_score}/100 · penalty {fmtINR(f.added_penalty_inr)}
                </span>
                <span className="meta" style={{ fontVariantNumeric: "tabular-nums" }}>
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
