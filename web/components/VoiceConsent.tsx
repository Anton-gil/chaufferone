"use client";

/* Voice consent (§3.7) - browser-native STT + TTS.
 *
 * Handoff-honest: local Whisper + Piper is Option C. This file uses the browser's
 * Web Speech API for the hackathon demo; swap the two helper functions at the
 * bottom (recognizeOnce, speak) with backend calls to /api/voice/stt + /tts to
 * go fully local without touching the rest of the component.
 *
 * Loop matches consent.py:
 *   1. poll /api/proposal/current
 *   2. when a new proposal opens, speak p.speech aloud (needs prior user gesture)
 *   3. hold "Talk" -> recognize -> POST /api/voice/turn -> speak reply
 *   4. if reply.plan_changed, reload the page so timeline + money strip refresh
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Proposal, type VoiceTurnResult } from "@/lib/api";

type ISpeechRecognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  continuous: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: {
    results: ArrayLike<ArrayLike<{ transcript: string; confidence: number }>>;
  }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};

type SpeechRecognitionCtor = new () => ISpeechRecognition;

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function speak(text: string): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window) || !text) {
      resolve();
      return;
    }
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 1.02;
      u.pitch = 1;
      u.onend = () => resolve();
      u.onerror = () => resolve();
      window.speechSynthesis.speak(u);
    } catch {
      resolve();
    }
  });
}

function recognizeOnce(): Promise<string> {
  return new Promise((resolve, reject) => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      reject(new Error("Speech recognition not available in this browser"));
      return;
    }
    const rec = new Ctor();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.continuous = false;
    let done = false;
    rec.onresult = (e) => {
      done = true;
      const first = e.results[0]?.[0]?.transcript ?? "";
      resolve(first.trim());
    };
    rec.onerror = (e) => {
      done = true;
      reject(new Error(e.error || "recognition error"));
    };
    rec.onend = () => {
      if (!done) resolve("");
    };
    rec.start();
  });
}

export function VoiceConsent() {
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [listening, setListening] = useState(false);
  const [heard, setHeard] = useState<string | null>(null);
  const [reply, setReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const spokenForRef = useRef<string | null>(null);
  const canSTT = typeof window !== "undefined" && getSpeechRecognitionCtor() !== null;

  // Poll for open proposals every 3s. SSE would be nicer; poll is safer.
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const p = await api.proposalCurrent();
        if (!cancelled) setProposal(p && p.status === "open" ? p : null);
      } catch {
        /* backend may be offline briefly */
      }
    };
    tick();
    const id = setInterval(tick, 3000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Speak the proposal exactly once per proposal_id (browsers block auto-speak
  // without a prior user gesture, so it only fires after "Enable voice").
  useEffect(() => {
    if (!enabled || !proposal) return;
    if (spokenForRef.current === proposal.proposal_id) return;
    spokenForRef.current = proposal.proposal_id;
    void speak(proposal.speech);
  }, [enabled, proposal]);

  const onTalk = useCallback(async () => {
    if (!canSTT || listening) return;
    setError(null);
    setHeard(null);
    setReply(null);
    setListening(true);
    try {
      const text = await recognizeOnce();
      setHeard(text || "(nothing heard)");
      if (!text) return;
      const res: VoiceTurnResult = await api.voiceTurn(text, proposal?.proposal_id ?? null);
      setReply(res.speech);
      if (enabled) await speak(res.speech);
      if (res.plan_changed) {
        setTimeout(() => window.location.reload(), 600);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setListening(false);
    }
  }, [canSTT, listening, proposal, enabled]);

  const enableVoice = useCallback(() => {
    // A user-triggered utterance unlocks speechSynthesis in Safari/Chrome.
    void speak("Voice ready.");
    setEnabled(true);
  }, []);

  const box: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
    marginBottom: 16,
  };
  const btn: React.CSSProperties = {
    background: "#0e0e13",
    color: "#e8e8ec",
    border: "1px solid #23232c",
    borderRadius: 6,
    padding: "6px 12px",
    fontSize: 12,
    cursor: "pointer",
  };
  const btnGo: React.CSSProperties = {
    ...btn,
    background: proposal ? "#7ee29a" : "#3a3a44",
    color: "#0b0b0e",
    borderColor: proposal ? "#7ee29a" : "#3a3a44",
    fontWeight: 600,
    cursor: proposal && canSTT ? "pointer" : "not-allowed",
  };

  if (!proposal && !enabled) {
    return null; // stay out of the way until there's something to consent to
  }

  return (
    <div className="card" style={box}>
      <span className="muted" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: 0.6 }}>
        Voice
      </span>
      {!enabled ? (
        <button type="button" style={btn} onClick={enableVoice}>Enable voice</button>
      ) : null}
      {proposal ? (
        <>
          <button
            type="button"
            style={btnGo}
            disabled={!canSTT || listening}
            onClick={onTalk}
          >
            {listening ? "Listening…" : canSTT ? "Talk" : "STT unsupported"}
          </button>
          <span className="muted" style={{ fontSize: 12, maxWidth: 520, overflow: "hidden", textOverflow: "ellipsis" }}>
            {proposal.speech}
          </span>
        </>
      ) : (
        <span className="muted" style={{ fontSize: 12 }}>No open proposal.</span>
      )}
      {heard ? <span style={{ fontSize: 12 }}>Heard: <em>{heard}</em></span> : null}
      {reply ? <span className="muted" style={{ fontSize: 12 }}>Replied: {reply}</span> : null}
      {error ? <span style={{ color: "#ff8a95", fontSize: 12 }}>{error}</span> : null}
    </div>
  );
}
