"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ProgressRingProps {
  /** 0..1 fraction filled. */
  value: number;
  size?: number;
  thickness?: number;
  color?: string;
  trackColor?: string;
  className?: string;
  children?: React.ReactNode;
}

/**
 * Perfect-circle progress ring (FRONTEND.md §14): 8px default thickness, wine
 * fill, #F2F2F4 track, 800ms ease-out reveal. Center content passed as children.
 */
export function ProgressRing({
  value,
  size = 160,
  thickness = 8,
  color = "#B4232D",
  trackColor = "#F2F2F4",
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
          stroke={trackColor}
          strokeWidth={thickness}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
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
