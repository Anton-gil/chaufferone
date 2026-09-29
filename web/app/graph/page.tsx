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
  if (tier === "red") return "#3a1a1f";
  if (tier === "amber") return "#3a2c1a";
  if (tier === "green") return "#1c3020";
  return "#23232c";
}
function tierStroke(tier: string): string {
  if (tier === "red") return "#ff8a95";
  if (tier === "amber") return "#ffc078";
  if (tier === "green") return "#7ee29a";
  return "#4a4a55";
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
        <h1>NEXUS</h1>
        <p className="muted">Obligation dependency graph.</p>
        <div className="error" style={{ marginTop: 16 }}>
          Failed to load graph. {error}
        </div>
      </main>
    );
  }

  const { positioned, width, height } = layout(data.nodes, data.edges);
  const posById = new Map(positioned.map((p) => [p.id, p]));

  return (
    <main style={{ maxWidth: "none", padding: "32px 24px" }}>
      <div style={{ maxWidth: 960, margin: "0 auto 24px" }}>
        <h1>NEXUS</h1>
        <p className="muted">
          {data.count.nodes} obligations · {data.count.edges} prerequisite{data.count.edges === 1 ? "" : "s"} · click a node for details
        </p>
      </div>

      <div style={{ overflowX: "auto", background: "#0e0e13", border: "1px solid #23232c", borderRadius: 12, padding: 8 }}>
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Obligation graph">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="#6a6a75" />
            </marker>
          </defs>

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
                stroke="#6a6a75"
                strokeWidth={1.5}
                markerEnd="url(#arrow)"
              />
            );
          })}

          {positioned.map((n) => {
            const fill = tierFill(n.urgency_tier);
            const stroke = tierStroke(n.urgency_tier);
            return (
              <Link key={n.id} href={`/obligation/${n.id}`}>
                <g transform={`translate(${n.x},${n.y})`} style={{ cursor: "pointer" }}>
                  <rect
                    width={NODE_W}
                    height={NODE_H}
                    rx={8}
                    ry={8}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={1}
                  />
                  <text x={12} y={22} fill="#e8e8ec" fontSize={13} fontWeight={500}>
                    {truncate(n.title, 26)}
                  </text>
                  <text x={12} y={40} fill="#8a8a94" fontSize={11}>
                    {n.category ?? "uncategorised"}
                  </text>
                  <text x={12} y={57} fill={stroke} fontSize={11} fontWeight={500}>
                    {fmtDue(n.due_date)}
                  </text>
                  {n.amount != null ? (
                    <text x={NODE_W - 12} y={57} fill="#c8c8d0" fontSize={11} textAnchor="end">
                      ₹{n.amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                    </text>
                  ) : null}
                </g>
              </Link>
            );
          })}
        </svg>
      </div>
    </main>
  );
}
