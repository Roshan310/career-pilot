"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Clock, Mic, Repeat } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/empty-state";
import { InterviewStatusBadge } from "@/components/common/status-badge";
import { ReplayDialog } from "@/components/interview/replay-dialog";
import { useInterviews } from "@/hooks/use-data";
import { formatDate, ratingToPct } from "@/lib/utils";

export default function InterviewsPage() {
  const router = useRouter();
  const { data: interviews = [], isLoading } = useInterviews();
  const [replayingId, setReplayingId] = useState<string | null>(null);

  /**
   * Previous attempt's score, per session — what makes "Attempt 2 of 3" mean
   * something rather than just count. Built once over the whole list, because
   * the API already returns every session and searching per row would be
   * quadratic on a long history.
   */
  const previousScore = useMemo(() => {
    const byChain = new Map<string, typeof interviews>();
    for (const iv of interviews) {
      const root = iv.replay_of_session_id ?? iv.id;
      byChain.set(root, [...(byChain.get(root) ?? []), iv]);
    }
    const scores = new Map<string, number>();
    for (const chain of byChain.values()) {
      const ordered = [...chain].sort((a, b) => a.attempt_number - b.attempt_number);
      ordered.forEach((iv, index) => {
        const before = ordered[index - 1]?.overall_score;
        if (before != null) scores.set(iv.id, before);
      });
    }
    return scores;
  }, [interviews]);

  return (
    <div>
      <PageHeader
        title="Interview History"
        subtitle="Review your past practice sessions and feedback reports."
        action={
          <Button variant="secondary" onClick={() => router.push("/interview")}>
            <Mic size={18} /> New Interview
          </Button>
        }
      />

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-card" />
          ))}
        </div>
      ) : interviews.length === 0 ? (
        <Card className="p-6">
          <EmptyState
            icon={Clock}
            title="No interviews yet"
            description="Start a practice session and your feedback reports will appear here."
            action={
              <Button onClick={() => router.push("/interview")}>
                <Mic size={18} /> Start an interview
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {interviews.map((iv) => {
            const pct = ratingToPct(iv.overall_score);
            const completed = iv.status === "completed";
            // A session that never finished has no report — send the user back
            // into it instead of at a 404.
            const resumable = iv.status === "in_progress" || iv.status === "wrapping_up";
            // Only a finished session has questions worth re-running, and only
            // a finished one has stopped moving through its plan.
            const replayable = completed || iv.status === "abandoned";
            const before = ratingToPct(previousScore.get(iv.id) ?? null);
            const delta = pct !== null && before !== null ? pct - before : null;
            return (
              <Card key={iv.id} className="flex flex-wrap items-center justify-between gap-4 p-5">
                {/* min-w-0 lets the long "company — title" line truncate instead
                    of forcing the right-hand cluster off the card on narrow screens. */}
                <div className="flex min-w-0 flex-1 items-center gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-wine-tint">
                    <Mic size={20} className="text-wine-fg" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-[16px] font-semibold text-text-primary">
                      {iv.job_company || "Interview"}
                      {iv.job_title ? ` — ${iv.job_title}` : ""}
                    </p>
                    <p className="mt-0.5 truncate text-[13px] text-text-muted">
                      {formatDate(iv.started_at)}
                      {iv.duration_minutes ? ` · ${Math.round(iv.duration_minutes)} min` : ""}
                      {" · "}
                      {iv.mode.replace("_", " ")}
                      {/* Only worth saying once a chain exists — "Attempt 1 of 1"
                          on every row is noise. */}
                      {iv.total_attempts > 1 && ` · Attempt ${iv.attempt_number} of ${iv.total_attempts}`}
                      {!iv.allow_follow_ups && " · main questions only"}
                    </p>
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-4 sm:gap-5">
                  {pct !== null && (
                    <div className="text-right">
                      <p className="text-[22px] font-bold leading-none text-text-primary">{pct}%</p>
                      {/* The point of practising again: whether it moved. */}
                      {delta !== null ? (
                        <p
                          className={
                            delta > 0
                              ? "text-[12px] font-medium text-success"
                              : delta < 0
                                ? "text-[12px] font-medium text-warning"
                                : "text-[12px] text-text-muted"
                          }
                        >
                          {delta > 0 ? `+${delta}` : delta} vs last
                        </p>
                      ) : (
                        <p className="text-[12px] text-text-muted">score</p>
                      )}
                    </div>
                  )}
                  <InterviewStatusBadge status={iv.status} />
                  {replayable && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setReplayingId(iv.id)}
                      title="Same questions, no waiting to generate them"
                    >
                      <Repeat size={15} /> Practise again
                    </Button>
                  )}
                  <Button
                    variant="outlineWine"
                    size="sm"
                    disabled={!completed && !resumable}
                    onClick={() =>
                      router.push(
                        resumable ? `/interview/${iv.id}/session` : `/interviews/${iv.id}/report`,
                      )
                    }
                  >
                    {resumable ? "Resume" : "View Report"} <ArrowRight size={15} />
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* One dialog for the whole list — `replayingId` is which row opened it. */}
      {replayingId && (
        <ReplayDialog
          open
          onOpenChange={(next) => !next && setReplayingId(null)}
          sessionId={replayingId}
        />
      )}
    </div>
  );
}
