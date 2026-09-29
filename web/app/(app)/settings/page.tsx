"use client";

import { useEffect, useState } from "react";
import { api, type Preferences, type PreferencesUpdate } from "@/lib/api";

type FormState = {
  hard_floor_inr: string;
  soft_cushion_inr: string;
  starting_balance_inr: string;
  estimated_monthly_income_inr: string;
  salary_day_of_month: string;
  admin_day_offset: string;
  aggressiveness: string;
  voice_enabled: boolean;
};

function toForm(p: Preferences): FormState {
  return {
    hard_floor_inr: String(p.hard_floor_inr),
    soft_cushion_inr: String(p.soft_cushion_inr),
    starting_balance_inr: String(p.starting_balance_inr),
    estimated_monthly_income_inr: String(p.estimated_monthly_income_inr),
    salary_day_of_month: p.salary_day_of_month == null ? "" : String(p.salary_day_of_month),
    admin_day_offset: String(p.admin_day_offset),
    aggressiveness: p.aggressiveness,
    voice_enabled: p.voice_enabled,
  };
}

function toPayload(f: FormState): PreferencesUpdate {
  const num = (s: string): number | undefined => (s.trim() === "" ? undefined : Number(s));
  const intOrNull = (s: string): number | null | undefined => (s.trim() === "" ? null : Number(s));
  return {
    hard_floor_inr: num(f.hard_floor_inr),
    soft_cushion_inr: num(f.soft_cushion_inr),
    starting_balance_inr: num(f.starting_balance_inr),
    estimated_monthly_income_inr: num(f.estimated_monthly_income_inr),
    salary_day_of_month: intOrNull(f.salary_day_of_month),
    admin_day_offset: num(f.admin_day_offset),
    aggressiveness: f.aggressiveness,
    voice_enabled: f.voice_enabled,
  };
}

const fieldStyle: React.CSSProperties = {
  background: "#0e0e13",
  color: "#e8e8ec",
  border: "1px solid #23232c",
  borderRadius: 6,
  padding: "8px 10px",
  fontSize: 14,
  width: "100%",
};
const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 12,
  color: "#8a8a94",
  marginBottom: 4,
};

const btnPrimary: React.CSSProperties = {
  background: "#7ee29a",
  color: "#0b0b0e",
  border: 0,
  borderRadius: 6,
  padding: "8px 14px",
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
};
const btnGhost: React.CSSProperties = {
  background: "transparent",
  color: "#c8c8d0",
  border: "1px solid #23232c",
  borderRadius: 6,
  padding: "8px 14px",
  fontSize: 13,
  cursor: "pointer",
};

export default function SettingsPage() {
  const [form, setForm] = useState<FormState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [running, setRunning] = useState<null | "ingest" | "seed" | "reset">(null);
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    api
      .preferences()
      .then((p) => setForm(toForm(p)))
      .catch((e: Error) => setLoadError(e.message));
  }, []);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((f) => (f ? { ...f, [k]: v } : f));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSaving(true);
    setSaveError(null);
    try {
      const p = await api.updatePreferences(toPayload(form));
      setForm(toForm(p));
      setSavedAt(Date.now());
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function runIngest() {
    setRunning("ingest");
    setMessage(null);
    setActionError(null);
    try {
      const r = await api.ingestGmail();
      setMessage(
        `Scanned ${r.scanned} · created ${r.created} · merged ${r.merged} · skipped ${r.skipped} · edges linked ${r.edges_linked}`,
      );
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setRunning(null);
    }
  }

  async function runSeed() {
    setRunning("seed");
    setMessage(null);
    setActionError(null);
    try {
      const r = await api.seedDemo();
      setMessage(`Seeded ${r.obligations_added} obligations, ${r.edges_added} edges.`);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setRunning(null);
    }
  }

  async function runReset() {
    if (!confirm("Delete all obligations and edges for the default user?")) return;
    setRunning("reset");
    setMessage(null);
    setActionError(null);
    try {
      const r = await api.resetDemo();
      setMessage(`Deleted ${r.obligations_deleted} obligations and ${r.edges_deleted} edges.`);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setRunning(null);
    }
  }

  return (
    <main style={{ maxWidth: 900 }}>
      <h1>Settings</h1>
      <p className="muted">Preferences, data sources, and demo tools.</p>

      <h2>Preferences</h2>
      {loadError ? <div className="error">{loadError}</div> : null}
      {!form && !loadError ? <p className="muted">Loading…</p> : null}
      {form ? (
        <form onSubmit={save}>
          <div className="card">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label style={labelStyle}>Starting balance (INR)</label>
                <input style={fieldStyle} type="number" value={form.starting_balance_inr} onChange={(e) => set("starting_balance_inr", e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Est. monthly income (INR)</label>
                <input style={fieldStyle} type="number" value={form.estimated_monthly_income_inr} onChange={(e) => set("estimated_monthly_income_inr", e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Hard floor (INR)</label>
                <input style={fieldStyle} type="number" value={form.hard_floor_inr} onChange={(e) => set("hard_floor_inr", e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Soft cushion (INR)</label>
                <input style={fieldStyle} type="number" value={form.soft_cushion_inr} onChange={(e) => set("soft_cushion_inr", e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Salary day of month (1-31, blank = none)</label>
                <input style={fieldStyle} type="number" min={1} max={31} value={form.salary_day_of_month} onChange={(e) => set("salary_day_of_month", e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Admin day offset (days after payday)</label>
                <input style={fieldStyle} type="number" min={0} value={form.admin_day_offset} onChange={(e) => set("admin_day_offset", e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Aggressiveness</label>
                <select style={fieldStyle} value={form.aggressiveness} onChange={(e) => set("aggressiveness", e.target.value)}>
                  <option value="conservative">conservative</option>
                  <option value="balanced">balanced</option>
                  <option value="aggressive">aggressive</option>
                </select>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input id="voice" type="checkbox" checked={form.voice_enabled} onChange={(e) => set("voice_enabled", e.target.checked)} />
                <label htmlFor="voice" style={{ fontSize: 13 }}>Voice enabled</label>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
            <button type="submit" disabled={saving} style={btnPrimary}>
              {saving ? "Saving…" : "Save preferences"}
            </button>
            {savedAt ? <span className="muted">Saved.</span> : null}
            {saveError ? <span className="error">{saveError}</span> : null}
          </div>
        </form>
      ) : null}

      <h2>Gmail</h2>
      <div className="card">
        <p className="muted" style={{ marginTop: 0 }}>
          Connect your inbox so Chaufferone can extract obligations. OAuth only, read-only scope.
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <a href="http://localhost:8000/api/auth/google/start" style={{ ...btnGhost, textDecoration: "none", display: "inline-block" }}>
            Connect Gmail
          </a>
          <button type="button" onClick={runIngest} disabled={running !== null} style={btnPrimary}>
            {running === "ingest" ? "Scanning…" : "Scan inbox now"}
          </button>
        </div>
      </div>

      <h2>Calendar</h2>
      <div className="card">
        <p className="muted" style={{ marginTop: 0 }}>
          Subscribe from Google, Apple or Outlook Calendar. Every obligation shows up on its <em>start-by</em> day,
          not its due date, so what you see there is what to begin today.
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <a
            href="http://localhost:8000/api/calendar.ics"
            style={{ ...btnGhost, textDecoration: "none", display: "inline-block" }}
          >
            Download .ics
          </a>
          <button
            type="button"
            onClick={() => {
              navigator.clipboard.writeText("http://localhost:8000/api/calendar.ics");
              setMessage("Feed URL copied. Paste into Google Calendar → Other calendars → From URL.");
            }}
            style={btnPrimary}
          >
            Copy subscribe URL
          </button>
        </div>
      </div>

      <h2>Demo data</h2>
      <div className="card">
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button type="button" onClick={runSeed} disabled={running !== null} style={btnGhost}>
            {running === "seed" ? "Seeding…" : "Seed demo obligations"}
          </button>
          <button type="button" onClick={runReset} disabled={running !== null} style={{ ...btnGhost, color: "#ff8a95", borderColor: "#3a1a1f" }}>
            {running === "reset" ? "Deleting…" : "Reset (delete all)"}
          </button>
        </div>
      </div>

      {message ? <p className="muted" style={{ marginTop: 12 }}>{message}</p> : null}
      {actionError ? <p className="error" style={{ marginTop: 12 }}>{actionError}</p> : null}
    </main>
  );
}
