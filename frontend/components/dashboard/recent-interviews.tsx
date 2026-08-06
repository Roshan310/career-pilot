"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, Clock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, ratingToPct, cn } from "@/lib/utils";
import type { InterviewListItem } from "@/lib/types";

interface Props {
  interviews: InterviewListItem[];
  loading: boolean;
}

export function RecentInterviews({ interviews, loading }: Props) {
  const router = useRouter();
  const rows = interviews.slice(0, 4);

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between">
        <span className="text-card-title text-text-primary">Recent Interviews</span>
        <Button variant="secondary" size="sm" onClick={() => router.push("/interviews")}>
          View All
        </Button>
      </div>

      <div className="mt-5">
        {loading ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={Clock}
            title="No interviews yet"
            description="Your practice sessions and feedback reports will appear here."
          />
        ) : (
          <ol className="relative space-y-6">
            {rows.map((iv, i) => {
              const pct = ratingToPct(iv.overall_score);
              const completed = iv.status === "completed";
              return (
                <li key={iv.id} className="relative flex gap-4 pl-1">
                  {/* timeline rail */}
                  <div className="flex flex-col items-center">
                    <span
                      className={cn(
                        "z-10 flex h-4 w-4 items-center justify-center rounded-full border-2",
                        i === 0 ? "border-wine bg-wine" : "border-border bg-card",
                      )}
                    >
                      {i === 0 && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
                    </span>
                    {i < rows.length - 1 && <span className="mt-1 w-px flex-1 bg-divider" />}
                  </div>

                  <div className="flex flex-1 items-start justify-between gap-3 pb-1">
                    <div className="min-w-0">
                      <p className="truncate text-[15px] font-semibold text-text-primary">
                        {iv.job_company || "Interview"}
                        {iv.job_title ? ` — ${iv.job_title}` : ""}
                      </p>
                      <p className="mt-0.5 text-[13px] text-text-muted">
                        {formatDate(iv.started_at)}
                        {iv.duration_minutes ? ` · ${Math.round(iv.duration_minutes)} min` : ""}
                      </p>
                    </div>
                    <div className="text-right">
                      {pct !== null && (
                        <span className="text-[15px] font-semibold text-success">{pct}%</span>
                      )}
                      <button
                        onClick={() => completed && router.push(`/interviews/${iv.id}/report`)}
                        disabled={!completed}
                        className={cn(
                          "mt-0.5 flex items-center gap-1 text-[13px] font-medium",
                          completed ? "text-wine hover:underline" : "text-text-muted",
                        )}
                      >
                        {completed ? "View Report" : "In progress"}
                        {completed && <ArrowRight size={13} />}
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </Card>
  );
}
