"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, HelpCircle, Mic, ShieldCheck } from "lucide-react";
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

  const weakest =
    report?.improvement_areas?.[0]?.targets_gap ||
    report?.gap_coverage?.still_open?.[0] ||
    null;

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2">
        <span className="text-card-title text-text-primary">Interview Readiness</span>
        <HelpCircle size={16} className="text-text-muted" />
      </div>

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
        />
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-[auto_1fr] lg:items-center">
          {/* Confidence score */}
          <div>
            <p className="text-[15px] font-medium text-text-secondary">Confidence Score</p>
            <p className="mt-2 text-[44px] font-bold leading-none text-wine">
              <CountUp value={confidence} suffix="%" />
            </p>
          </div>

          {/* Weakest area (only when the report surfaces a real gap) */}
          {weakest && (
            <div className="rounded-2xl bg-wine-tint p-4 lg:border-l lg:border-divider">
              <div className="flex items-center gap-2 text-wine">
                <ShieldCheck size={16} />
                <span className="text-[12px] font-semibold uppercase tracking-wide">Weakest Area</span>
              </div>
              <p className="mt-2 text-[16px] font-semibold text-text-primary">{weakest}</p>
              <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">
                Focus your next few sessions here to raise your overall readiness.
              </p>
              <button
                onClick={() => router.push("/interview")}
                className="mt-3 flex items-center gap-1 text-[13px] font-semibold text-wine hover:underline"
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
