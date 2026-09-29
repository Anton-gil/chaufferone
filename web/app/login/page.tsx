"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { useState, type FormEvent } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<null | "google" | "email">(null);

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy("email");
    router.push("/dashboard");
  }

  function onGoogle() {
    setBusy("google");
    void signIn("google", { callbackUrl: "/dashboard" });
  }

  return (
    <div className="login-shell">
      <div className="login-stars" aria-hidden="true" />
      <div className="login-arc" aria-hidden="true">
        <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
          <g className="hero-arc-group">
            <circle cx="50" cy="50" r="49" fill="none" stroke="rgba(255,255,255,0.5)" strokeDasharray="1.4 6" strokeWidth="0.15" />
            <circle cx="50" cy="50" r="43" fill="none" stroke="rgba(255,255,255,0.4)" strokeDasharray="1 8" strokeWidth="0.15" />
          </g>
          <g className="hero-arc-group-reverse">
            <circle cx="50" cy="50" r="36" fill="none" stroke="rgba(255,255,255,0.3)" strokeDasharray="1 10" strokeWidth="0.15" />
            <circle cx="50" cy="50" r="28" fill="none" stroke="rgba(255,255,255,0.22)" strokeDasharray="1 12" strokeWidth="0.15" />
          </g>
        </svg>
      </div>

      <Link href="/" className="login-back">← Back</Link>

      <main className="login-card">
        <Link href="/" className="login-mark" aria-label="Chaufferone">
          <span />
        </Link>

        <h1 className="login-title">Sign In</h1>
        <p className="login-sub">Continue to access your dashboard</p>

        <button type="button" className="oauth-btn" onClick={onGoogle} disabled={busy !== null}>
          <GoogleG /> {busy === "google" ? "Redirecting…" : "Sign in with Google"}
        </button>

        <div className="login-divider" aria-hidden="true">
          <span>OR</span>
        </div>

        <form className="login-form" onSubmit={onSubmit}>
          <label className="field">
            <span className="field-label">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              required
              autoComplete="email"
            />
          </label>

          <label className="field">
            <span className="field-label-row">
              <span className="field-label">Password</span>
              <a href="#" className="field-forgot">Forgot Password?</a>
            </span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              autoComplete="current-password"
            />
          </label>

          <button type="submit" className="login-submit" disabled={busy === "email"}>
            {busy === "email" ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <div className="login-footer-line">
          Don&apos;t have an account? <a href="#">Create an account</a>
        </div>
      </main>
    </div>
  );
}

function GoogleG() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#4285F4" d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z" />
      <path fill="#34A853" d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z" />
      <path fill="#FBBC05" d="M11.69 28.18c-.44-1.32-.69-2.73-.69-4.18s.25-2.86.69-4.18v-5.7H4.34C2.85 17.09 2 20.45 2 24s.85 6.91 2.34 9.88l7.35-5.7z" />
      <path fill="#EA4335" d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z" />
    </svg>
  );
}
