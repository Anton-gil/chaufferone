"use client";

import { useEffect, useRef, type ReactNode, type ElementType } from "react";

type Props = {
  children: ReactNode;
  as?: ElementType;
  delay?: 0 | 1 | 2 | 3 | 4;
  className?: string;
};

export function Reveal({ children, as: Tag = "div", delay = 0, className = "" }: Props) {
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("is-visible");
            io.unobserve(e.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const delayCls = delay ? `reveal-delay-${delay}` : "";
  return (
    <Tag ref={ref as never} className={`reveal ${delayCls} ${className}`.trim()}>
      {children}
    </Tag>
  );
}

export function LandingNavShrink() {
  useEffect(() => {
    const nav = document.querySelector<HTMLElement>(".landing-nav");
    if (!nav) return;
    const hero = document.querySelector<HTMLElement>(".hero");
    const getThreshold = () => Math.max(200, (hero?.offsetHeight ?? window.innerHeight) - 120);
    const onScroll = () => {
      if (window.scrollY > getThreshold()) nav.classList.add("scrolled");
      else nav.classList.remove("scrolled");
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);
  return null;
}
