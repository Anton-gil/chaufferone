import Link from "next/link";
import { api, type GraphEdge, type GraphNode } from "@/lib/api";

export const dynamic = "force-dynamic";

type Positioned = GraphNode & { x: number; y: number; level: number };

const NODE_W = 200;
const NODE_H = 68;
const COL_GAP = 80;
const ROW_GAP = 22;
const MARGIN_X = 40;
const MARGIN_Y = 40;

function layout(nodes: GraphNode[], edges: GraphEdge[]): {
  positioned: Positioned[];
  width: number;
  height: number;
} {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const preds = new Map<string, string[]>();
  const succs = new Map<string, string[]>();
  for (const n of nodes) {
    preds.set(n.id, []);
    succs.set(n.id, []);
  }
  for (const e of edges) {
    if (byId.has(e.from) && byId.has(e.to)) {
      preds.get(e.to)!.push(e.from);
      succs.get(e.from)!.push(e.to);
    }
  }

  const level = new Map<string, number>();
  const remaining = new Map(nodes.map((n) => [n.id, preds.get(n.id)!.length]));
  const queue = nodes.filter((n) => preds.get(n.id)!.length === 0).map((n) => n.id);
  for (const id of queue) level.set(id, 0);
  while (queue.length) {
    const id = queue.shift()!;
    for (const s of succs.get(id)!) {
      level.set(s, Math.max(level.get(s) ?? 0, (level.get(id) ?? 0) + 1));
      const r = (remaining.get(s) ?? 0) - 1;
      remaining.set(s, r);
      if (r === 0) queue.push(s);
    }
  }

  const groups = new Map<number, GraphNode[]>();
  for (const n of nodes) {
    const lv = level.get(n.id) ?? 0;
    if (!groups.has(lv)) groups.set(lv, []);
    groups.get(lv)!.push(n);
  }
  for (const arr of groups.values()) {
    arr.sort((a, b) => {
      const da = a.due_date ?? "9999";
      const db = b.due_date ?? "9999";
      if (da !== db) return da < db ? -1 : 1;
      return a.title.localeCompare(b.title);
    });
  }

  const levels = [...groups.keys()].sort((a, b) => a - b);
  const positioned: Positioned[] = [];
  let maxRows = 0;
  for (const lv of levels) {
    const col = groups.get(lv)!;
    if (col.length > maxRows) maxRows = col.length;
    col.forEach((n, i) => {
      positioned.push({
        ...n,
        level: lv,
        x: MARGIN_X + lv * (NODE_W + COL_GAP),
        y: MARGIN_Y + i * (NODE_H + ROW_GAP),
      });
    });
  }

  const width = MARGIN_X * 2 + levels.length * NODE_W + Math.max(0, levels.length - 1) * COL_GAP;
  const height = MARGIN_Y * 2 + maxRows * NODE_H + Math.max(0, maxRows - 1) * ROW_GAP;
  return { positioned, width, height };
}

function tierFill(tier: string): string {
  if (tier === "red")   return "#0a0a0a";
  return "#ffffff";
}
function tierStroke(tier: string): string {
  if (tier === "red")   return "#0a0a0a";
  return "#cfcfc8";
}
function tierText(tier: string): string {
  return tier === "red" ? "#ffffff" : "#0a0a0a";
}
function tierMeta(tier: string): string {
  return tier === "red" ? "rgba(255,255,255,0.65)" : "#8a8a83";
}
function tierAccent(tier: string): string {
  if (tier === "red")   return "#ffffff";
  if (tier === "amber") return "#0a0a0a";
  if (tier === "green") return "#4a4a45";
  return "#8a8a83";
}

function fmtDue(iso: string | null): string {
  if (!iso) return "no due date";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

async function fetchGraph() {
  try {
    const data = await api.graph();
    return { data, error: null as string | null };
  } catch (e) {
    return { data: null, error: (e as Error).message };
  }
}

export default async function GraphPage() {
  const { data, error } = await fetchGraph();

  if (error || !data) {
    return (
      <main>
        <div className="page-header">
          <div className="page-header-left">
            <span className="page-eyebrow">Obligation graph</span>
            <h1 className="page-title">Nexus<span className="page-title-accent">— dependency map.</span></h1>
          </div>
        </div>
        <div className="error">Failed to load graph. {error}</div>
      </main>
    );
  }

  const { positioned, width, height } = layout(data.nodes, data.edges);
  const posById = new Map(positioned.map((p) => [p.id, p]));
  const red   = positioned.filter(p => p.urgency_tier === "red").length;
  const withPrereq = new Set(data.edges.map(e => e.to)).size;

  return (
    <main>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">Obligation graph</span>
          <h1 className="page-title">Nexus<span className="page-title-accent">— dependency map.</span></h1>
        </div>
        <div className="page-header-actions">
          <span className="status">click a node</span>
          <Link href="/dashboard" className="btn-outline">← Timeline</Link>
        </div>
      </div>

      <div className="kpi-grid">
        <div className="kpi kpi-dark">
          <div className="kpi-top">
            <span className="kpi-label">Obligations</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>
            </span>
          </div>
          <div className="kpi-value">{data.count.nodes}</div>
          <div className="kpi-delta">Nodes in the graph</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Prerequisites</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="12" x2="20" y2="12" /><polyline points="15,7 20,12 15,17" /></svg>
            </span>
          </div>
          <div className="kpi-value">{data.count.edges}</div>
          <div className="kpi-delta">{withPrereq} tasks need something first</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Red tier</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="8" /><line x1="12" y1="8" x2="12" y2="12" /><circle cx="12" cy="16" r="0.8" fill="currentColor" /></svg>
            </span>
          </div>
          <div className="kpi-value">{red}</div>
          <div className="kpi-delta">Needs attention now</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Legend</span>
            <span className="kpi-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="7" cy="7" r="3" fill="currentColor" /><circle cx="7" cy="17" r="3" /><line x1="14" y1="7" x2="20" y2="7" /><line x1="14" y1="17" x2="20" y2="17" /></svg>
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4, fontSize: 12, color: "var(--mute-strong)" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 12, height: 10, background: "var(--ink)", borderRadius: 2 }} /> Red · overdue / at-risk
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 12, height: 10, background: "var(--paper)", border: "1px solid var(--line-strong)", borderRadius: 2 }} /> Amber / green
            </span>
          </div>
        </div>
      </div>

      <div className="graph-canvas">
        <div className="graph-canvas-header">
          <div>
            <span className="panel-eyebrow">Directed acyclic graph</span>
            <h2 className="panel-title">Prerequisite flow</h2>
          </div>
          <span className="muted" style={{ fontSize: 12 }}>Arrows show what must happen first</span>
        </div>
        <div className="graph-canvas-scroll">
          <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Obligation graph">
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="#4a4a45" />
              </marker>
              <pattern id="graph-dots" width="14" height="14" patternUnits="userSpaceOnUse">
                <circle cx="1" cy="1" r="1" fill="rgba(10,10,10,0.09)" />
              </pattern>
            </defs>

            <rect x={0} y={0} width={width} height={height} fill="url(#graph-dots)" />

            {data.edges.map((e, i) => {
              const a = posById.get(e.from);
              const b = posById.get(e.to);
              if (!a || !b) return null;
              const x1 = a.x + NODE_W;
              const y1 = a.y + NODE_H / 2;
              const x2 = b.x;
              const y2 = b.y + NODE_H / 2;
              const mx = (x1 + x2) / 2;
              const d = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
              return (
                <path
                  key={`e${i}`}
                  d={d}
                  fill="none"
                  stroke="#4a4a45"
                  strokeWidth={1.25}
                  strokeDasharray={e.is_blocking ? undefined : "4 4"}
                  markerEnd="url(#arrow)"
                  opacity={0.85}
                />
              );
            })}

            {positioned.map((n) => {
              const fill = tierFill(n.urgency_tier);
              const stroke = tierStroke(n.urgency_tier);
              const text = tierText(n.urgency_tier);
              const meta = tierMeta(n.urgency_tier);
              const accent = tierAccent(n.urgency_tier);
              return (
                <Link key={n.id} href={`/obligation/${n.id}`}>
                  <g transform={`translate(${n.x},${n.y})`} style={{ cursor: "pointer" }} className="graph-node">
                    <rect
                      width={NODE_W}
                      height={NODE_H}
                      rx={12}
                      ry={12}
                      fill={fill}
                      stroke={stroke}
                      strokeWidth={1.25}
                    />
                    <rect x={0} y={0} width={3} height={NODE_H} rx={1.5} fill={accent} opacity={0.85} />
                    <text x={14} y={22} fill={text} fontSize={13} fontWeight={600} letterSpacing="-0.005em">
                      {truncate(n.title, 26)}
                    </text>
                    <text x={14} y={38} fill={meta} fontSize={11}>
                      {n.category ?? "uncategorised"}
                    </text>
                    <text x={14} y={57} fill={meta} fontSize={11} fontWeight={500} style={{ fontFamily: "var(--font-pixel), VT323, monospace", letterSpacing: "0.06em" }}>
                      {fmtDue(n.due_date)}
                    </text>
                    {n.amount != null ? (
                      <text
                        x={NODE_W - 14}
                        y={57}
                        fill={text}
                        fontSize={12}
                        textAnchor="end"
                        style={{ fontFamily: "var(--font-pixel), VT323, monospace", letterSpacing: "0.02em" }}
                      >
                        ₹{n.amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                      </text>
                    ) : null}
                  </g>
                </Link>
              );
            })}
          </svg>
        </div>
      </div>
    </main>
  );
}
