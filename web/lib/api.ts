export type Obligation = {
  id: string;
  title: string;
  vendor: string | null;
  category: string | null;
  obligation_type: string;
  amount: number | null;
  currency: string;
  due_date: string | null;
  lead_time_days: number;
  urgency_tier: "red" | "amber" | "green" | string;
  status: string;
  verification_state: string;
  risk_score: number | null;
};

const SERVER_BACKEND =
  process.env.SUTRADHAR_BACKEND_URL ?? "http://127.0.0.1:8000";

function resolve(path: string): string {
  if (typeof window !== "undefined") return path;
  return `${SERVER_BACKEND}${path}`;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = resolve(path);
  const res = await fetch(url, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export type GraphNode = {
  id: string;
  title: string;
  category: string | null;
  due_date: string | null;
  lead_time_days: number;
  amount: number | null;
  penalty_amount: number | null;
  urgency_tier: "red" | "amber" | "green" | string;
  risk_score: number | null;
  status: string;
  verification_state: string;
};

export type GraphEdge = {
  from: string;
  to: string;
  kind: string;
  lead_time_days: number;
  is_blocking: boolean;
  legal_basis: string | null;
  confidence: number | null;
};

export type GraphResponse = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  count: { nodes: number; edges: number };
};

export type ForecastDebit = {
  obligation_id: string;
  title: string;
  amount: number;
  category: string | null;
  flexibility_window_days: number;
  penalty_amount: number | null;
};
export type DayPoint = {
  date: string;
  opening_balance: number;
  income: number;
  debits: ForecastDebit[];
  total_debit: number;
  closing_balance: number;
  breach_type: "none" | "cushion" | "floor" | string;
  breach_depth_inr: number;
};
export type Clash = {
  id: string;
  first_breach_date: string;
  last_breach_date: string;
  tier: "cushion" | "floor";
  max_depth_inr: number;
  obligations_involved: string[];
  obligation_titles: string[];
};
export type ForecastResponse = {
  horizon_days: number;
  starting_balance_inr: number;
  hard_floor_inr: number;
  soft_cushion_inr: number;
  days: DayPoint[];
  clashes: Clash[];
};

export type Fix = {
  kind: "defer" | "pause_subscription" | "reorder";
  obligation_id: string;
  obligation_title: string;
  description: string;
  new_date: string | null;
  added_penalty_inr: number;
  disruption_score: number;
  resolves_clash: boolean;
  resulting_min_balance_inr: number;
};

export type Cascade = {
  root_id: string;
  total_exposure_inr: number;
  step_count: number;
  steps: {
    obligation_id: string;
    title: string;
    direct_penalty: number;
    reason: string;
  }[];
};

export type Risk = {
  obligation_id: string;
  score: number;
  tier: "red" | "amber" | "green" | string;
  components: {
    time_urgency: number;
    penalty_severity: number;
    prerequisite_risk: number;
    cash_flow_risk: number;
    historical_miss: number;
  };
  cascade_exposure_inr: number;
  start_by: string | null;
};

export type Preferences = {
  user_id: string;
  hard_floor_inr: number;
  soft_cushion_inr: number;
  starting_balance_inr: number;
  estimated_monthly_income_inr: number;
  salary_day_of_month: number | null;
  admin_day_offset: number;
  aggressiveness: string;
  voice_enabled: boolean;
};

export type PreferencesUpdate = Partial<Omit<Preferences, "user_id">>;

export const api = {
  health: () => jsonFetch<{ status: string; product: string }>("/health"),
  timeline: () => jsonFetch<Obligation[]>("/api/timeline"),
  obligation: (id: string) => jsonFetch<Obligation>(`/api/obligation/${id}`),
  graph: () => jsonFetch<GraphResponse>("/api/graph"),
  cascade: (id: string) => jsonFetch<Cascade>(`/api/graph/cascade/${id}`),
  risk: (id: string) => jsonFetch<Risk>(`/api/graph/risk/${id}`),
  forecast: (days: number = 45) => jsonFetch<ForecastResponse>(`/api/money/forecast?days=${days}`),
  fixes: (clashId: string, days: number = 45) =>
    jsonFetch<Fix[]>(`/api/money/fixes/${clashId}?days=${days}`),
  preferences: () => jsonFetch<Preferences>("/api/preferences"),
  updatePreferences: (payload: PreferencesUpdate) =>
    jsonFetch<Preferences>("/api/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  ingestGmail: (days: number = 90, maxResults: number = 50) =>
    jsonFetch<{
      scanned: number;
      created: number;
      merged: number;
      skipped: number;
      signals: number;
      edges_linked: number;
    }>(`/api/ingest/gmail/run?days=${days}&max_results=${maxResults}`, { method: "POST" }),
  seedDemo: () =>
    jsonFetch<{ obligations_added: number; edges_added: number }>("/api/demo/seed", {
      method: "POST",
    }),
  resetDemo: () =>
    jsonFetch<{ obligations_deleted: number; edges_deleted: number }>("/api/demo/reset", {
      method: "POST",
    }),
};
