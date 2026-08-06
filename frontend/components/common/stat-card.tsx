"use client";

import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { CountUp } from "./count-up";

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: number;
  decimals?: number;
  suffix?: string;
  /** small line under the metric, e.g. "↑ 3 this week" */
  delta?: React.ReactNode;
  index?: number;
}

/** Bottom-row statistics card (FRONTEND.md §21): 48x48 tinted icon, left-aligned. */
export function StatCard({ icon: Icon, label, value, decimals = 0, suffix = "", delta, index = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, delay: index * 0.05 }}
      className="flex items-center gap-4 rounded-card border border-border bg-card p-5 shadow-card transition-shadow duration-[180ms] hover:shadow-card-hover"
    >
      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-wine-tint">
        <Icon size={20} className="text-wine" strokeWidth={2} />
      </div>
      <div className="min-w-0">
        <p className="text-sm text-text-secondary">{label}</p>
        <p className="mt-1 text-[28px] font-bold leading-none text-text-primary">
          <CountUp value={value} decimals={decimals} suffix={suffix} />
        </p>
        {delta && <p className="mt-1.5 text-[13px]">{delta}</p>}
      </div>
    </motion.div>
  );
}
