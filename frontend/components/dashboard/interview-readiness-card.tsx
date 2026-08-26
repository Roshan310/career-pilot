"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, Mic, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CountUp } from "@/components/common/count-up";
import { EmptyState } from "@/components/common/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ratingToPct } from "@/lib/utils";
import type { InterviewListItem, SessionReport } from "@/lib/types";

interface Props {
  listItem: InterviewListItem | null;
  report: SessionReport | null | undefined;
  loading: boolean;
}

export function InterviewReadinessCard({ listItem, report, loading }: Props) {
  const router = useRouter();
  const confidence = ratingToPct(listItem?.overall_score);

  // The top improvement names the gap it relates to on its exemplar turn. The
  // second branch is the pre-findings report shape, which put it at the top
  // level (see lib/types.ts) — kept so old reports still fill this in.
  const top = report?.improvement_areas?.[0];
  const weakest =
    (top && "exemplar" in top ? top.exemplar?.targets_gap : top?.targets_gap) ||
    report?.gap_coverage?.still_open?.[0] ||
    null;

  return (
    <Card className="p-6">
      <span className="text-card-title text-text-primary">Interview Readiness</span>

      {loading ? (
        <div className="mt-6 grid gap-6 sm:grid-cols-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      ) : !listItem || confidence === null ? (
        <EmptyState
          icon={Mic}
          title="No interviews yet"
          description="Practice a mock interview to build your readiness score across every skill area."
          action={<Button onClick={() => router.push("/interview")}>Start an Interview</Button>}
        />
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-[auto_1fr] lg:items-center">
          {/* Confidence score */}
          <div>
            <p className="text-[15px] font-medium text-text-secondary">Confidence Score</p>
            <p className="mt-2 text-[44px] font-bold leading-none text-wine-fg">
              <CountUp value={confidence} suffix="%" />
            </p>
          </div>

          {/* Weakest area (only when the report surfaces a real gap) */}
          {weakest && (
            <div className="rounded-2xl bg-wine-tint p-4 lg:border-l lg:border-divider">
              <div className="flex items-center gap-2 text-wine-fg">
                <ShieldCheck size={16} />
                <span className="text-[12px] font-semibold uppercase tracking-wide">Weakest Area</span>
              </div>
              <p className="mt-2 text-[16px] font-semibold text-text-primary">{weakest}</p>
              <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">
                Focus your next few sessions here to raise your overall readiness.
              </p>
              <button
                onClick={() => router.push("/interview")}
                className="mt-3 flex items-center gap-1 rounded text-[13px] font-semibold text-wine-fg hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
              >
                Practice Now <ArrowRight size={14} />
              </button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
