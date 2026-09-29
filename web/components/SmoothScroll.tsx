"use client";

import { useEffect } from "react";

/**
 * Landing-only smooth scroll: intercepts wheel + touch and lerps the window
 * scrollTop toward a target using rAF. Feels like Lenis without the dep.
 * Kept off if the user prefers reduced motion, and cleans up on unmount so
 * routing to /login or /dashboard restores native scroll instantly.
 */
export function SmoothScroll() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mql.matches) return;
    if (window.matchMedia("(pointer: coarse)").matches) return;

    let target = window.scrollY;
    let current = window.scrollY;
    let lastDelta = 0;
    let lastTs = 0;
    let raf = 0;
    let running = true;

    // Frame-rate-independent lerp: same feel at 60/90/120Hz.
    const easePerSec = 12;
    const wheelMultiplier = 0.7;

    function clamp(v: number) {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      if (v < 0) return 0;
      if (v > max) return max;
      return v;
    }

    function loop(ts: number) {
      if (!running) return;
      const dt = lastTs ? Math.min(0.05, (ts - lastTs) / 1000) : 1 / 60;
      lastTs = ts;
      const t = 1 - Math.exp(-easePerSec * dt);
      current += (target - current) * t;
      if (Math.abs(target - current) < 0.35) current = target;
      window.scrollTo(0, Math.round(current));
      raf = requestAnimationFrame(loop);
    }

    function onWheel(e: WheelEvent) {
      if (e.ctrlKey) return;
      e.preventDefault();

      const dy = e.deltaY;
      // Direction reversal: snap the tween back to the real scroll position so
      // the new direction responds instantly instead of dragging the leftover
      // momentum in the old direction (this is the "up feels laggy" culprit).
      if (dy * lastDelta < 0) {
        current = window.scrollY;
        target = current;
      }
      lastDelta = dy;

      target = clamp(target + dy * wheelMultiplier);
    }

    function onKey(e: KeyboardEvent) {
      const step = window.innerHeight;
      const small = 80;
      if (["PageDown", " "].includes(e.key)) { target = clamp(target + step * 0.9); e.preventDefault(); }
      else if (e.key === "PageUp")          { target = clamp(target - step * 0.9); e.preventDefault(); }
      else if (e.key === "Home")            { target = 0; e.preventDefault(); }
      else if (e.key === "End")             { target = clamp(document.documentElement.scrollHeight); e.preventDefault(); }
      else if (e.key === "ArrowDown")       { target = clamp(target + small); }
      else if (e.key === "ArrowUp")         { target = clamp(target - small); }
    }

    function onAnchorClick(e: MouseEvent) {
      const a = (e.target as HTMLElement)?.closest?.("a[href^='#']") as HTMLAnchorElement | null;
      if (!a) return;
      const id = a.getAttribute("href")!.slice(1);
      if (!id) return;
      const el = document.getElementById(id);
      if (!el) return;
      e.preventDefault();
      const y = el.getBoundingClientRect().top + window.scrollY - 24;
      target = clamp(y);
    }

    function onResize() {
      target = clamp(target);
    }

    // Keep tween in sync if something else moves the page (e.g. focus scroll).
    function onNativeScroll() {
      if (Math.abs(window.scrollY - current) > 4 && Math.abs(target - current) < 1) {
        current = window.scrollY;
        target = current;
      }
    }

    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onNativeScroll, { passive: true });
    document.addEventListener("click", onAnchorClick);

    raf = requestAnimationFrame(loop);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onNativeScroll);
      document.removeEventListener("click", onAnchorClick);
    };
  }, []);

  return null;
}
