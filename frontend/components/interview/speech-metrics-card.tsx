"use client";

import { Gauge, MessageSquareDashed, Timer } from "lucide-react";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import type { SpeechMetrics } from "@/lib/types";

/** Conversational speech sits roughly here; outside it we say so, gently. */
const COMFORTABLE_WPM = { min: 120, max: 160 };

function paceNote(wpm: number | undefined): string {
  if (!wpm) return "Not enough speech to measure";
  if (wpm < COMFORTABLE_WPM.min) return "On the slower side — room to sound more assured";
  if (wpm > COMFORTABLE_WPM.max) return "Quite fast — slowing down reads as more confident";
  return "A comfortable interview pace";
}

function Metric({
  icon,
  value,
  label,
  note,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
  note?: string;
}) {
  return (
    <div className="rounded-card border border-border p-4">
      <div className="flex items-center gap-2 text-text-muted">
        {icon}
        <span className="text-[13px] font-medium">{label}</span>
      </div>
      <p className="mt-2 text-[26px] font-bold leading-none text-text-primary">{value}</p>
      {note && <p className="mt-1.5 text-[13px] text-text-secondary">{note}</p>}
    </div>
  );
}

/**
 * SPECS.md §7.4. Computed server-side (see docs/decisions.md) so these numbers
 * stay comparable if the voice provider is ever swapped.
 */
export function SpeechMetricsCard({ metrics }: { metrics: SpeechMetrics | null }) {
  if (!metrics || !metrics.turns_measured) return null;

  const pause = metrics.longest_pause_ms;

  return (
    <Card className="p-6">
      <CardTitle>
        <Gauge size={18} className="text-wine" /> Delivery
      </CardTitle>
      <CardContent className="mt-4 grid gap-4 sm:grid-cols-3">
        <Metric
          icon={<Gauge size={14} />}
          label="Speaking pace"
          value={metrics.avg_wpm ? `${Math.round(metrics.avg_wpm)} wpm` : "—"}
          note={paceNote(metrics.avg_wpm)}
        />
        <Metric
          icon={<MessageSquareDashed size={14} />}
          label="Filler words"
          value={String(metrics.total_filler_count ?? 0)}
          note={`across ${metrics.turns_measured} answered ${metrics.turns_measured === 1 ? "question" : "questions"}`}
        />
        <Metric
          icon={<Timer size={14} />}
          label="Longest pause"
          value={pause == null ? "—" : `${(pause / 1000).toFixed(1)}s`}
          note={pause == null ? "No timing data for this session" : "Mid-answer, not thinking time"}
        />
      </CardContent>
    </Card>
  );
}
