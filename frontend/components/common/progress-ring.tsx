"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ProgressRingProps {
  /** 0..1 fraction filled. */
  value: number;
  size?: number;
  thickness?: number;
  /** Tailwind stroke class, e.g. "stroke-success". Defaults to the brand fill. */
  colorClass?: string;
  trackClass?: string;
  className?: string;
  children?: React.ReactNode;
}

/**
 * Perfect-circle progress ring (FRONTEND.md §14): 8px default thickness, wine
 * fill, token-driven track, 800ms ease-out reveal. Center content as children.
 *
 * Stroke is set with a class, not the `stroke` attribute: a CSS variable in a
 * presentation attribute is not reliably resolved, so a themed track has to come
 * through the cascade.
 */
export function ProgressRing({
  value,
  size = 160,
  thickness = 8,
  colorClass = "stroke-wine",
  trackClass = "stroke-ring-track",
  className,
  children,
}: ProgressRingProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped);

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className={trackClass}
          strokeWidth={thickness}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className={colorClass}
          strokeWidth={thickness}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        {children}
      </div>
    </div>
  );
}
