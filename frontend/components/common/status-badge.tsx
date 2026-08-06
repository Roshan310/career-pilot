import { Badge } from "@/components/ui/badge";

const MATCH_STATUS: Record<string, { label: string; variant: "success" | "warning" | "error" | "info" | "neutral" }> = {
  done: { label: "Done", variant: "success" },
  processing: { label: "Processing", variant: "info" },
  pending: { label: "Pending", variant: "warning" },
  failed: { label: "Failed", variant: "error" },
};

const INTERVIEW_STATUS: Record<string, { label: string; variant: "success" | "warning" | "error" | "info" | "neutral" }> = {
  completed: { label: "Completed", variant: "success" },
  in_progress: { label: "In progress", variant: "info" },
  wrapping_up: { label: "Wrapping up", variant: "warning" },
  abandoned: { label: "Abandoned", variant: "neutral" },
};

export function MatchStatusBadge({ status }: { status: string }) {
  const cfg = MATCH_STATUS[status] ?? { label: status, variant: "neutral" as const };
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

export function InterviewStatusBadge({ status }: { status: string }) {
  const cfg = INTERVIEW_STATUS[status] ?? { label: status, variant: "neutral" as const };
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

/** Score badge whose color tier follows the percentage (green/blue/orange). */
export function ScoreBadge({ pct }: { pct: number | null }) {
  if (pct === null) return <Badge variant="neutral">—</Badge>;
  const variant = pct >= 85 ? "success" : pct >= 70 ? "info" : "warning";
  return <Badge variant={variant}>{pct}%</Badge>;
}
