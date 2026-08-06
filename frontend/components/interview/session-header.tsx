"use client";

import { Clock } from "lucide-react";
import type { SessionProgress } from "@/lib/types";
import { cn, formatClock } from "@/lib/utils";

interface SessionHeaderProps {
  title: string;
  subtitle?: string | null;
  progress: SessionProgress | null;
  secondsRemaining: number | null;
  right?: React.ReactNode;
}

export function SessionHeader({ title, subtitle, progress, secondsRemaining, right }: SessionHeaderProps) {
  const planned = progress?.main_questions_planned ?? 0;
  const answered = progress?.main_questions_answered ?? 0;
  // The question you're on is the next one, capped at the plan length.
  const current = planned ? Math.min(answered + 1, planned) : answered + 1;
  const fraction = planned ? Math.min(1, answered / planned) : 0;

  const lowOnTime = secondsRemaining !== null && secondsRemaining <= 120;

  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-3xl items-center gap-4 px-6 py-4">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold text-text-primary">{title}</p>
          {subtitle && <p className="truncate text-[13px] text-text-muted">{subtitle}</p>}
        </div>

        {planned > 0 && (
          <span className="hidden shrink-0 text-[13px] font-medium text-text-secondary sm:block">
            Question {current} of {planned}
          </span>
        )}

        {secondsRemaining !== null && (
          <span
            className={cn(
              "flex shrink-0 items-center gap-1.5 tabular-nums text-[13px] font-medium",
              lowOnTime ? "text-warning" : "text-text-secondary",
            )}
          >
            <Clock size={14} />
            {formatClock(secondsRemaining)}
          </span>
        )}

        {right}
      </div>

      <div className="h-[3px] w-full bg-divider">
        <div
          className="h-full bg-wine transition-[width] duration-500 ease-out"
          style={{ width: `${fraction * 100}%` }}
        />
      </div>
    </header>
  );
}
