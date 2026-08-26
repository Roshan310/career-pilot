"use client";

import { motion, useReducedMotion } from "framer-motion";

interface RevealProps {
  children: React.ReactNode;
  className?: string;
  /** Seconds. Stagger siblings by hand rather than nesting motion containers. */
  delay?: number;
  /** Slide direction. "up" is the default; rows use "left"/"right" to converge. */
  from?: "up" | "left" | "right";
}

const OFFSET = { up: { y: 26, x: 0 }, left: { y: 0, x: -32 }, right: { y: 0, x: 32 } };

/**
 * The one reveal used across the landing page.
 *
 * `once: true` matters: re-animating on every pass makes a long page feel busy
 * and janky on the way back up. The reduced-motion branch renders the finished
 * state directly rather than animating quickly — globals.css collapses CSS
 * transition durations, but Framer Motion runs on rAF and ignores that entirely.
 *
 * Below the fold only. Anything the visitor sees before scrolling uses the
 * `.landing-rise` keyframe instead: an in-view reveal renders at zero opacity
 * and waits on an IntersectionObserver callback, which is a bad bet for content
 * that is already inside the observer's root when the page opens.
 */
export function Reveal({ children, className, delay = 0, from = "up" }: RevealProps) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, ...OFFSET[from] }}
      whileInView={{ opacity: 1, y: 0, x: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.65, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
