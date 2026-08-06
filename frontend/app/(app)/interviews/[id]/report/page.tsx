"use client";

import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, Target, ThumbsUp, TriangleAlert } from "lucide-react";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProgressRing } from "@/components/common/progress-ring";
import { CountUp } from "@/components/common/count-up";
import { SpeechMetricsCard } from "@/components/interview/speech-metrics-card";
import { TurnBreakdown } from "@/components/interview/turn-breakdown";
import { Skeleton } from "@/components/ui/skeleton";
import { useInterview, useInterviewReport } from "@/hooks/use-data";
import { ratingToPct } from "@/lib/utils";

export default function InterviewReportPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: report, isLoading, isError } = useInterviewReport(id);
  // The session carries the per-question transcripts and scores; the report
  // carries the aggregate. Both are needed for the full picture.
  const { data: session } = useInterview(id);

  const back = (
    <button
      onClick={() => router.push("/interviews")}
      className="flex items-center gap-1.5 text-sm font-medium text-text-secondary hover:text-text-primary"
    >
      <ArrowLeft size={16} /> Back to History
    </button>
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        {back}
        <Skeleton className="h-52 rounded-card" />
        <Skeleton className="h-40 rounded-card" />
      </div>
    );
  }

  if (isError || !report) {
    return (
      <div className="space-y-6">
        {back}
        <Card className="p-14 text-center">
          <p className="text-text-secondary">This report isn&apos;t available — the interview may not be completed yet.</p>
          <Button variant="secondary" className="mt-4" onClick={() => router.push("/interviews")}>
            Back to History
          </Button>
        </Card>
      </div>
    );
  }

  const pct = ratingToPct(report.overall_score) ?? 0;
  const strengths = report.strengths ?? [];
  const improvements = report.improvement_areas ?? [];
  const addressed = report.gap_coverage?.addressed ?? [];
  const stillOpen = report.gap_coverage?.still_open ?? [];

  return (
    <div className="space-y-6">
      {back}

      <Card className="p-6">
        <div className="flex flex-col items-center gap-8 sm:flex-row">
          <ProgressRing value={pct / 100} size={168} thickness={10}>
            <span className="text-[34px] font-bold leading-none text-text-primary">
              <CountUp value={pct} suffix="%" />
            </span>
            <span className="mt-1 text-[14px] text-text-secondary">readiness</span>
          </ProgressRing>
          <div className="flex-1">
            <h1 className="text-h3 text-text-primary">Interview Feedback</h1>
            <p className="mt-1.5 text-[15px] text-text-secondary">
              Aggregate score across all answered questions, weighting main questions above follow-ups.
            </p>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <CardTitle><ThumbsUp size={18} className="text-success" /> Strengths</CardTitle>
          <CardContent className="mt-4 space-y-3">
            {strengths.length ? (
              strengths.map((s) => (
                <div key={s.turn_number} className="flex gap-2.5 text-[15px] text-text-primary">
                  <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-success" />
                  {s.question_text}
                </div>
              ))
            ) : (
              <p className="text-[15px] text-text-secondary">No standout strengths recorded this session.</p>
            )}
          </CardContent>
        </Card>

        <Card className="p-6">
          <CardTitle><TriangleAlert size={18} className="text-warning" /> Areas to Improve</CardTitle>
          <CardContent className="mt-4 space-y-3">
            {improvements.length ? (
              improvements.map((s) => (
                <div key={s.turn_number} className="flex gap-2.5 text-[15px] text-text-primary">
                  <TriangleAlert size={17} className="mt-0.5 shrink-0 text-warning" />
                  <span>
                    {s.question_text}
                    {s.targets_gap && (
                      <span className="ml-1.5 text-[13px] text-text-muted">({s.targets_gap})</span>
                    )}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-[15px] text-text-secondary">No weak areas flagged — nicely done.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <SpeechMetricsCard metrics={report.speech_metrics} />

      <Card className="p-6">
        <CardTitle><Target size={18} className="text-wine" /> Gap Coverage</CardTitle>
        <CardContent className="mt-4 grid gap-6 sm:grid-cols-2">
          <div>
            <p className="mb-2 text-[14px] font-medium text-text-secondary">Addressed</p>
            <div className="flex flex-wrap gap-2">
              {addressed.length ? (
                addressed.map((g) => <Badge key={g} variant="success">{g}</Badge>)
              ) : (
                <span className="text-[14px] text-text-muted">None yet</span>
              )}
            </div>
          </div>
          <div>
            <p className="mb-2 text-[14px] font-medium text-text-secondary">Still Open</p>
            <div className="flex flex-wrap gap-2">
              {stillOpen.length ? (
                stillOpen.map((g) => <Badge key={g} variant="warning">{g}</Badge>)
              ) : (
                <span className="text-[14px] text-text-muted">None</span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {session && <TurnBreakdown turns={session.turns} />}
    </div>
  );
}
