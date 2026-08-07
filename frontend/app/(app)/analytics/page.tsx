"use client";

import { useMemo } from "react";
import { FileText, Mic, Target, TrendingUp } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/common/stat-card";
import { Skeleton } from "@/components/ui/skeleton";
import { useInterviews, useMatches, useUsage } from "@/hooks/use-data";
import { formatDate, scorePct } from "@/lib/utils";

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

  const loading = ml || il;

  return (
    <div className="space-y-8">
      <PageHeader title="Analytics" subtitle="Your resume-matching activity at a glance." />

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
            value={scorePct(best?.overall_score ?? null) ?? 0}
            suffix="%"
            index={3}
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <CardTitle>Match Score Distribution</CardTitle>
          <CardContent className="mt-5 space-y-3">
            {doneMatches.length === 0 ? (
              <p className="text-[15px] text-text-secondary">Run an analysis to populate this chart.</p>
            ) : (
              doneMatches.slice(0, 8).map((m) => {
                const pct = scorePct(m.overall_score) ?? 0;
                return (
                  <div key={m.id}>
                    <div className="flex items-center justify-between text-[13px]">
                      <span className="max-w-[70%] truncate text-text-secondary">
                        {m.job_company || "Role"}
                        {m.job_title ? ` · ${m.job_title}` : ""}
                      </span>
                      <span className="font-semibold text-text-primary">{pct}%</span>
                    </div>
                    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-divider">
                      <div className="h-full rounded-full bg-wine" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

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
