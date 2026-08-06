"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, Clock, Mic } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/empty-state";
import { InterviewStatusBadge } from "@/components/common/status-badge";
import { useInterviews } from "@/hooks/use-data";
import { formatDate, ratingToPct } from "@/lib/utils";

export default function InterviewsPage() {
  const router = useRouter();
  const { data: interviews = [], isLoading } = useInterviews();

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
            return (
              <Card key={iv.id} className="flex flex-wrap items-center justify-between gap-4 p-5">
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-wine-tint">
                    <Mic size={20} className="text-wine" />
                  </div>
                  <div>
                    <p className="text-[16px] font-semibold text-text-primary">
                      {iv.job_company || "Interview"}
                      {iv.job_title ? ` — ${iv.job_title}` : ""}
                    </p>
                    <p className="mt-0.5 text-[13px] text-text-muted">
                      {formatDate(iv.started_at)}
                      {iv.duration_minutes ? ` · ${Math.round(iv.duration_minutes)} min` : ""}
                      {" · "}
                      {iv.mode.replace("_", " ")}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-5">
                  {pct !== null && (
                    <div className="text-right">
                      <p className="text-[22px] font-bold leading-none text-text-primary">{pct}%</p>
                      <p className="text-[12px] text-text-muted">score</p>
                    </div>
                  )}
                  <InterviewStatusBadge status={iv.status} />
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
    </div>
  );
}
