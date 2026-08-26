"use client";

import { useEffect, useRef, useState } from "react";

interface CountUpProps {
  value: number;
  duration?: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
}

/**
 * Animated count-up for metric reveals (SPECS premium checklist).
 *
 * Interpolates from whatever is currently on screen, not from zero. Animating
 * 0 -> value on every change made a background refetch look like the number had
 * reset and recovered.
 */
export function CountUp({ value, duration = 800, decimals = 0, suffix = "", prefix = "" }: CountUpProps) {
  const [display, setDisplay] = useState(value);
  const displayRef = useRef(value);
  const frame = useRef<number>();

  useEffect(() => {
    displayRef.current = display;
  }, [display]);

  useEffect(() => {
    const from = displayRef.current;
    if (from === value) return;

    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      setDisplay(value);
      return;
    }
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      setDisplay(from + (value - from) * eased);
      if (t < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    };
    // `display` is intentionally read through a ref so a re-render mid-tween
    // doesn't restart the animation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, duration]);

  return (
    <span>
      {prefix}
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}
