import type { BadgeProps } from "@/components/ui/badge";
import { JOB_STATUSES, type JobStatus } from "@/lib/types";

type BadgeVariant = NonNullable<BadgeProps["variant"]>;

interface StatusMeta {
  label: string;
  variant: BadgeVariant;
  /** Shown as the section subtitle when that column has entries. */
  hint: string;
}

/**
 * Wording and colour for each pipeline stage.
 *
 * `rejected` is deliberately neutral rather than red. A job hunt produces far
 * more rejections than offers, and a board that turns mostly red is a board
 * people stop opening — which defeats the point of having it.
 */
export const JOB_STATUS_META: Record<JobStatus, StatusMeta> = {
  saved: { label: "Saved", variant: "neutral", hint: "Not applied yet" },
  applied: { label: "Applied", variant: "info", hint: "Waiting to hear back" },
  screening: { label: "Screening", variant: "info", hint: "In early conversations" },
  interviewing: { label: "Interviewing", variant: "wine", hint: "Worth practising for" },
  offer: { label: "Offer", variant: "success", hint: "Nice." },
  rejected: { label: "Closed", variant: "neutral", hint: "Didn't work out" },
};

/** Board order. `rejected` sits last so the active pipeline reads first. */
export const JOB_STATUS_ORDER: readonly JobStatus[] = JOB_STATUSES;

export function statusLabel(status: string): string {
  return JOB_STATUS_META[status as JobStatus]?.label ?? status;
}

export function statusVariant(status: string): BadgeVariant {
  return JOB_STATUS_META[status as JobStatus]?.variant ?? "neutral";
}

/**
 * Days until a deadline, or null when there isn't one.
 * Negative means it has passed.
 */
export function daysUntil(deadline: string | null): number | null {
  if (!deadline) return null;
  const target = new Date(`${deadline}T00:00:00`);
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

/** Short, human deadline copy: the thing a user actually scans for. */
export function deadlineLabel(deadline: string | null): { text: string; urgent: boolean } | null {
  const days = daysUntil(deadline);
  if (days === null) return null;
  if (days < 0) return { text: "Deadline passed", urgent: false };
  if (days === 0) return { text: "Closes today", urgent: true };
  if (days === 1) return { text: "Closes tomorrow", urgent: true };
  if (days <= 7) return { text: `Closes in ${days} days`, urgent: true };
  return { text: `Closes in ${days} days`, urgent: false };
}
