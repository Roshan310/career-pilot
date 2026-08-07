"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, FileSearch, TriangleAlert } from "lucide-react";
import { Card } from "@/components/ui/card";
import { ProgressRing } from "@/components/common/progress-ring";
import { CountUp } from "@/components/common/count-up";
import { EmptyState } from "@/components/common/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { scorePct, skillName } from "@/lib/utils";
import type { Match, MatchListItem } from "@/lib/types";

function scoreLabel(pct: number): string {
  if (pct >= 85) return "Excellent";
  if (pct >= 70) return "Strong";
  if (pct >= 50) return "Fair";
  return "Needs Work";
}

/**
 * Must move with `scoreLabel`. This sentence used to read "highly relevant"
 * unconditionally, so a 12% match claimed a strong fit directly beneath a ring
 * labelled "Needs Work".
 */
function scoreSummary(pct: number): string {
  if (pct >= 85) return "Your resume is an excellent match for";
  if (pct >= 70) return "Your resume is a strong match for";
  if (pct >= 50) return "Your resume partly matches";
  return "Your resume needs work to match";
}

interface Props {
  listItem: MatchListItem | null;
  detail: Match | null | undefined;
  loading: boolean;
}

export function ResumeStrengthCard({ listItem, detail, loading }: Props) {
  const router = useRouter();

  return (
    <Card className="p-6">
      <span className="text-card-title text-text-primary">Resume Strength</span>

      {loading ? (
        <div className="mt-6 flex gap-6">
          <Skeleton className="h-40 w-40 rounded-full" />
          <div className="flex-1 space-y-3 py-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-4 w-56" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-44" />
          </div>
        </div>
      ) : !listItem || listItem.overall_score === null ? (
        <EmptyState
          icon={FileSearch}
          title="No analysis yet"
          description="Run your first resume analysis to see how well you match a role."
          action={<Button onClick={() => router.push("/analysis")}>Analyze Resume</Button>}
        />
      ) : (
        <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
          <div className="flex flex-col items-center">
            <ProgressRing value={scorePct(listItem.overall_score)! / 100} size={168} thickness={10}>
              <span className="text-[34px] font-bold leading-none text-text-primary">
                <CountUp value={scorePct(listItem.overall_score)!} suffix="%" />
              </span>
              <span className="mt-1 text-[15px] font-medium text-text-secondary">
                {scoreLabel(scorePct(listItem.overall_score)!)}
              </span>
            </ProgressRing>
          </div>

          <div className="flex-1">
            <p className="text-[15px] font-semibold text-text-primary">Overall Match Score</p>
            <p className="mt-1 text-[15px] leading-relaxed text-text-secondary">
              {scoreSummary(scorePct(listItem.overall_score)!)}{" "}
              <span className="font-medium text-text-primary">{listItem.job_title || "this role"}</span>
              {listItem.job_company && (
                <>
                  {" "}at <span className="font-medium text-text-primary">{listItem.job_company}</span>
                </>
              )}
              .
            </p>

            <ul className="mt-4 space-y-2.5">
              {(detail?.matched_skills ?? []).slice(0, 2).map((s, i) => (
                <li key={`m-${i}`} className="flex items-center gap-2.5 text-[15px] text-text-primary">
                  <CheckCircle2 size={17} className="shrink-0 text-success" />
                  Strong {skillName(s)} match
                </li>
              ))}
              {(detail?.missing_skills ?? []).slice(0, 2).map((s, i) => (
                <li key={`x-${i}`} className="flex items-center gap-2.5 text-[15px] text-text-primary">
                  <TriangleAlert size={17} className="shrink-0 text-warning" />
                  {skillName(s)} missing
                </li>
              ))}
              {(detail?.matched_skills ?? []).length === 0 &&
                (detail?.missing_skills ?? []).length === 0 && (
                  <li className="text-[15px] text-text-secondary">Skill breakdown available in the full report.</li>
                )}
            </ul>
          </div>
        </div>
      )}

      {listItem && listItem.overall_score !== null && (
        <Button
          variant="outlineWine"
          size="sm"
          className="mt-6"
          onClick={() => router.push(`/analysis/${listItem.id}`)}
        >
          View Full Analysis <ArrowRight size={16} />
        </Button>
      )}
    </Card>
  );
}
