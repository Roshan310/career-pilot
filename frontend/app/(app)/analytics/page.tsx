"use client";

import { useMemo } from "react";
import Link from "next/link";
import { FileText, Mic, Target, TrendingUp } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/common/stat-card";
import { EmptyState } from "@/components/common/empty-state";
import { LineChart, type ChartPoint } from "@/components/common/line-chart";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useInterviews, useMatches, useUsage } from "@/hooks/use-data";
import { formatDate, ratingToPct, scorePct } from "@/lib/utils";

/** A dimension average is out of 5; every chart here is 0-100. */
const dimPct = (v: number | undefined) => (v == null ? null : Math.round((v / 5) * 100));

const DIMENSIONS = [
  { key: "structure", label: "Structure", color: "stroke-wine", area: "fill-wine/10" },
  { key: "specificity", label: "Specificity", color: "stroke-info", area: "fill-info/10" },
  { key: "relevance", label: "Relevance", color: "stroke-success", area: "fill-success/10" },
] as const;

export default function AnalyticsPage() {
  const { data: matches = [], isLoading: ml } = useMatches();
  const { data: interviews = [], isLoading: il } = useInterviews();
  const { data: usage } = useUsage();

  const doneMatches = matches.filter((m) => m.status === "done" && m.overall_score !== null);
  const completedInterviews = interviews.filter((i) => i.status === "completed");

  const avg = useMemo(() => {
    if (!doneMatches.length) return 0;
    return Math.round(
      (doneMatches.reduce((s, m) => s + (m.overall_score ?? 0), 0) / doneMatches.length) * 100,
    );
  }, [doneMatches]);

  const best = useMemo(() => {
    if (!doneMatches.length) return null;
    return doneMatches.reduce((a, b) => ((a.overall_score ?? 0) >= (b.overall_score ?? 0) ? a : b));
  }, [doneMatches]);

  // The API returns newest first; a trend has to read left-to-right in time.
  const matchTrend: ChartPoint[] = useMemo(
    () =>
      [...doneMatches]
        .sort((a, b) => a.created_at.localeCompare(b.created_at))
        .map((m) => ({ label: formatDate(m.created_at), value: scorePct(m.overall_score) ?? 0 })),
    [doneMatches],
  );

  const scoredInterviews = useMemo(
    () =>
      completedInterviews
        .filter((i) => i.overall_score !== null)
        .sort((a, b) => a.started_at.localeCompare(b.started_at)),
    [completedInterviews],
  );

  const readinessTrend: ChartPoint[] = useMemo(
    () =>
      scoredInterviews.map((i) => ({
        label: formatDate(i.started_at),
        value: ratingToPct(i.overall_score) ?? 0,
      })),
    [scoredInterviews],
  );

  // Reports written before dimension averages were stored have none. Those are
  // skipped rather than plotted as zero, which would invent a dip that never
  // happened.
  const dimensionTrends = useMemo(() => {
    const withDims = scoredInterviews.filter((i) => i.dimension_averages);
    return DIMENSIONS.map((d) => ({
      ...d,
      points: withDims
        .map((i) => ({
          label: formatDate(i.started_at),
          value: dimPct((i.dimension_averages as Record<string, number>)[d.key]),
        }))
        .filter((p): p is ChartPoint => p.value !== null),
    }));
  }, [scoredInterviews]);

  const loading = ml || il;

  return (
    <div className="space-y-8">
      <PageHeader title="Progress" subtitle="How your matches and interviews are trending over time." />

      {loading ? (
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-card" />
          ))}
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard icon={FileText} label="Analyses Run" value={doneMatches.length} index={0} />
          <StatCard icon={Mic} label="Interviews Completed" value={completedInterviews.length} index={1} />
          <StatCard icon={Target} label="Average Match Score" value={avg} suffix="%" index={2} />
          <StatCard
            icon={TrendingUp}
            label="Best Match"
            value={best ? (scorePct(best.overall_score) ?? 0) : 0}
            suffix="%"
            index={3}
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <CardTitle><Target size={18} className="text-wine-fg" /> Match Score Over Time</CardTitle>
          <CardContent className="mt-5">
            {loading ? (
              <Skeleton className="h-44 rounded-card" />
            ) : matchTrend.length ? (
              <LineChart
                points={matchTrend}
                ariaLabel={`Match score across ${matchTrend.length} analyses`}
              />
            ) : (
              <EmptyState
                icon={Target}
                title="No analyses yet"
                description="Match a resume against a job to start plotting your scores."
                action={
                  <Link href="/analysis">
                    <Button>Run an Analysis</Button>
                  </Link>
                }
              />
            )}
          </CardContent>
        </Card>

        <Card className="p-6">
          <CardTitle><Mic size={18} className="text-wine-fg" /> Interview Readiness Over Time</CardTitle>
          <CardContent className="mt-5">
            {loading ? (
              <Skeleton className="h-44 rounded-card" />
            ) : readinessTrend.length ? (
              <LineChart
                points={readinessTrend}
                colorClass="stroke-info"
                areaClass="fill-info/10"
                ariaLabel={`Interview readiness across ${readinessTrend.length} sessions`}
              />
            ) : (
              <EmptyState
                icon={Mic}
                title="No interviews yet"
                description="Practice a mock interview to start tracking your readiness."
                action={
                  <Link href="/interview">
                    <Button>Start an Interview</Button>
                  </Link>
                }
              />
            )}
          </CardContent>
        </Card>
      </div>

      {dimensionTrends.some((d) => d.points.length > 0) && (
        <Card className="p-6">
          <CardTitle><TrendingUp size={18} className="text-wine-fg" /> What&apos;s Improving</CardTitle>
          <p className="mt-1 text-[14px] text-text-secondary">
            How each part of your answers has scored across sessions.
          </p>
          <CardContent className="mt-6 grid gap-8 lg:grid-cols-3">
            {dimensionTrends.map((d) => (
              <div key={d.key}>
                <p className="mb-3 text-[15px] font-medium text-text-primary">{d.label}</p>
                {d.points.length ? (
                  <LineChart
                    points={d.points}
                    colorClass={d.color}
                    areaClass={d.area}
                    height={130}
                    ariaLabel={`${d.label} across ${d.points.length} sessions`}
                  />
                ) : (
                  <p className="text-[14px] text-text-muted">Not scored yet.</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card className="p-6">
        <CardTitle>This Month&apos;s Usage</CardTitle>
        <CardContent className="mt-5 space-y-5">
          {usage ? (
            <>
              <UsageBar
                label="Resume matches"
                used={usage.monthly_match_count}
                limit={usage.monthly_match_limit}
              />
              <UsageBar
                label="Mock interviews"
                used={usage.monthly_interview_count}
                limit={usage.monthly_interview_limit}
              />
              {usage.usage_reset_at && (
                <p className="text-[13px] text-text-muted">
                  Resets on {formatDate(usage.usage_reset_at)}
                </p>
              )}
            </>
          ) : (
            <Skeleton className="h-24 rounded-card" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-[14px]">
        <span className="text-text-secondary">{label}</span>
        <span className="font-semibold text-text-primary">
          {used} / {limit}
        </span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-divider">
        <div className="h-full rounded-full bg-wine" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
