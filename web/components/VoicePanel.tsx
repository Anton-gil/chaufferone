"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Phase = "idle" | "recording" | "transcribing" | "thinking" | "speaking" | "error";

type VoiceTurnResponse = {
  speech: string;
  intent: string;
  parsed_by?: string;
  applied_moves?: unknown[];
  plan_changed?: boolean;
  proposal_id?: string | null;
};

export function VoicePanel() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [heard, setHeard] = useState<string>("");
  const [spoken, setSpoken] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const startedAt = useRef<number>(0);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => () => stopStream(), [stopStream]);

  const speak = useCallback((text: string) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.02;
    u.pitch = 1.0;
    u.onstart = () => setPhase("speaking");
    u.onend   = () => setPhase("idle");
    u.onerror = () => setPhase("idle");
    window.speechSynthesis.speak(u);
  }, []);

  const send = useCallback(async (blob: Blob) => {
    setPhase("transcribing");
    setErr(null);
    try {
      const fd = new FormData();
      fd.append("audio", blob, "clip.webm");
      const tr = await fetch("/api/voice/transcribe", { method: "POST", body: fd });
      if (!tr.ok) throw new Error(`transcribe ${tr.status}`);
      const trJson = await tr.json();
      const text: string = (trJson.text ?? "").trim();
      setHeard(text);
      if (!text) {
        setPhase("idle");
        return;
      }

      setPhase("thinking");
      const tu = await fetch("/api/voice/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!tu.ok) throw new Error(`voice/turn ${tu.status}`);
      const turn: VoiceTurnResponse = await tu.json();
      setSpoken(turn.speech ?? "");
      if (turn.speech) speak(turn.speech);
      else setPhase("idle");
    } catch (e) {
      setPhase("error");
      setErr((e as Error).message);
    }
  }, [speak]);

  const startRecording = useCallback(async () => {
    if (phase === "recording" || phase === "transcribing" || phase === "thinking") return;
    setErr(null);
    setHeard("");
    setSpoken("");
    window.speechSynthesis?.cancel();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const rec = new MediaRecorder(stream, { mimeType: mime });
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mime });
        stopStream();
        if (Date.now() - startedAt.current < 350) {
          setPhase("idle");
          return;
        }
        void send(blob);
      };
      recorderRef.current = rec;
      startedAt.current = Date.now();
      rec.start();
      setPhase("recording");
    } catch (e) {
      setErr((e as Error).message || "microphone blocked");
      setPhase("error");
    }
  }, [phase, send, stopStream]);

  const stopRecording = useCallback(() => {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
  }, []);

  useEffect(() => {
    let holding = false;
    function isTyping(target: EventTarget | null) {
      const el = target as HTMLElement | null;
      if (!el) return false;
      const tag = el.tagName;
      return tag === "INPUT" || tag === "TEXTAREA" || el.isContentEditable;
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.code !== "Space" || e.repeat || isTyping(e.target)) return;
      e.preventDefault();
      if (!holding) {
        holding = true;
        void startRecording();
      }
    }
    function onKeyUp(e: KeyboardEvent) {
      if (e.code !== "Space" || isTyping(e.target)) return;
      if (holding) {
        holding = false;
        stopRecording();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [startRecording, stopRecording]);

  const label =
    phase === "recording"    ? "Listening…" :
    phase === "transcribing" ? "Transcribing…" :
    phase === "thinking"     ? "Thinking…" :
    phase === "speaking"     ? "Speaking…" :
    phase === "error"        ? "Error" :
                               "Hold to talk";

  return (
    <div className={`voice-panel voice-phase-${phase}`}>
      <div className="voice-transcript" aria-live="polite">
        {heard || spoken ? (
          <>
            {heard ? <div className="voice-you"><span>You</span>{heard}</div> : null}
            {spoken ? <div className="voice-them"><span>Engine</span>{spoken}</div> : null}
          </>
        ) : (
          <div className="voice-hint">
            Hold <kbd>Space</kbd> or press the mic and speak.
          </div>
        )}
        {err ? <div className="voice-err">{err}</div> : null}
      </div>

      <button
        type="button"
        className="voice-mic"
        onPointerDown={(e) => { e.preventDefault(); void startRecording(); }}
        onPointerUp={(e) => { e.preventDefault(); stopRecording(); }}
        onPointerLeave={() => stopRecording()}
        onPointerCancel={() => stopRecording()}
        aria-pressed={phase === "recording"}
        aria-label={label}
        title={label}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="3" width="6" height="12" rx="3" fill="currentColor" />
          <path d="M5 11 Q 12 19, 19 11" />
          <line x1="12" y1="17" x2="12" y2="21" />
          <line x1="9" y1="21" x2="15" y2="21" />
        </svg>
        <span className="voice-mic-ring" aria-hidden="true" />
        <span className="voice-mic-label">{label}</span>
      </button>
    </div>
  );
}
