"use client";

import { useEffect, useState } from "react";
import { api, type SampleSms } from "@/lib/api";

type Busy = null | "scenario" | "pre_debit" | "debit";

export function DemoStrip() {
  const [samples, setSamples] = useState<SampleSms | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .demoSampleSms()
      .then((s) => {
        if (!cancelled) setSamples(s);
      })
      .catch(() => {}); // silent — samples fetched from a live backend only
    return () => {
      cancelled = true;
    };
  }, []);

  async function run(kind: Busy, fn: () => Promise<unknown>, done: string) {
    setBusy(kind);
    setError(null);
    setMessage(null);
    try {
      await fn();
      setMessage(done);
      setTimeout(() => window.location.reload(), 400);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const btn: React.CSSProperties = {
    background: "#0e0e13",
    color: "#e8e8ec",
    border: "1px solid #23232c",
    borderRadius: 6,
    padding: "6px 12px",
    fontSize: 12,
    cursor: "pointer",
  };
  const btnGo: React.CSSProperties = { ...btn, background: "#7ee29a", color: "#0b0b0e", borderColor: "#7ee29a", fontWeight: 600 };

  return (
    <div
      className="card"
      style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 16 }}
    >
      <span className="muted" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: 0.6 }}>
        Demo
      </span>
      <button type="button" style={btnGo} disabled={busy !== null} onClick={() =>
        run("scenario", () => api.demoScenario(), "Scenario loaded")
      }>
        {busy === "scenario" ? "Loading…" : "Load hero scenario"}
      </button>
      <button
        type="button"
        style={btn}
        disabled={busy !== null || !samples}
        onClick={() => samples && run(
          "pre_debit",
          () => api.demoInjectSms("AX-HDFCBK-S", samples.pre_debit),
          "Pre-debit SMS injected",
        )}
      >
        {busy === "pre_debit" ? "Injecting…" : "Inject pre-debit SMS"}
      </button>
      <button
        type="button"
        style={btn}
        disabled={busy !== null || !samples}
        onClick={() => samples && run(
          "debit",
          () => api.demoInjectSms("AX-HDFCBK-S", samples.debit),
          "Debit SMS injected",
        )}
      >
        {busy === "debit" ? "Injecting…" : "Inject debit SMS"}
      </button>
      {message ? <span className="muted" style={{ fontSize: 12 }}>{message}</span> : null}
      {error ? <span style={{ color: "#ff8a95", fontSize: 12 }}>{error}</span> : null}
    </div>
  );
}
