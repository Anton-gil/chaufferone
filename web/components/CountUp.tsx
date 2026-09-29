"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  value: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
  locale?: string;
  decimals?: number;
  className?: string;
};

export function CountUp({
  value,
  duration = 1100,
  prefix = "",
  suffix = "",
  locale,
  decimals = 0,
  className,
}: Props) {
  const [n, setN] = useState(0);
  const startedAt = useRef<number | null>(null);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    startedAt.current = null;
    if (raf.current) cancelAnimationFrame(raf.current);
    const from = 0;
    const to = value;
    const step = (t: number) => {
      if (startedAt.current == null) startedAt.current = t;
      const elapsed = t - startedAt.current;
      const p = Math.min(1, elapsed / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(from + (to - from) * eased);
      if (p < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [value, duration]);

  const rounded = decimals > 0 ? n.toFixed(decimals) : Math.round(n).toString();
  const formatted =
    decimals === 0
      ? Number(rounded).toLocaleString(locale)
      : Number(rounded).toLocaleString(locale, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        });

  return (
    <span className={className}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
}
