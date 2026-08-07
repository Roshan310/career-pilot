"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Mic, Target, ThumbsUp, TriangleAlert } from "lucide-react";
import { BackLink } from "@/components/common/back-link";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProgressRing } from "@/components/common/progress-ring";
import { CountUp } from "@/components/common/count-up";
import { FindingList } from "@/components/interview/report-findings";
import { SpeechMetricsCard } from "@/components/interview/speech-metrics-card";
import { TurnBreakdown } from "@/components/interview/turn-breakdown";
import { Skeleton } from "@/components/ui/skeleton";
import { useInterview, useInterviewReport, useJob } from "@/hooks/use-data";
import { ratingToPct } from "@/lib/utils";
import { markReportReviewed } from "@/hooks/use-reviewed-reports";

export default function InterviewReportPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: report, isLoading, isError } = useInterviewReport(id);
  // The session carries the per-question transcripts and scores; the report
  // carries the aggregate. Both are needed for the full picture.
  const { data: session } = useInterview(id);
  // Names the role this interview was for. The heading was the literal string
  // "Interview Feedback" and that context appeared nowhere on the page.
  const { data: job } = useJob(session?.job_id ?? "");

  /** Re-run the same pairing. Carries the ids so the picker arrives filled in. */
  const practiceHref = session?.resume_id && session?.job_id
    ? `/interview?resume=${session.resume_id}&job=${session.job_id}` +
      (session.match_id ? `&match=${session.match_id}` : "")
    : "/interview";

  // Ticks "Feedback reviewed" on the dashboard. Only once the report actually
  // rendered — reaching the route with an error state is not reading it.
  useEffect(() => {
    if (report) markReportReviewed(id);
  }, [report, id]);

  const back = (
    <BackLink href="/interviews">Back to History</BackLink>
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
            {(job?.title || job?.company) && (
              <p className="mt-1 text-[15px] font-medium text-text-primary">
                {[job.title, job.company].filter(Boolean).join(" · ")}
              </p>
            )}
            <p className="mt-1.5 text-[15px] text-text-secondary">
              Aggregate score across all answered questions, weighting main questions above follow-ups.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <Button onClick={() => router.push(practiceHref)}>
                <Mic size={18} /> Practice again
              </Button>
              <span className="text-[13px] text-text-muted">
                {stillOpen.length
                  ? `${stillOpen.length} gap${stillOpen.length === 1 ? "" : "s"} still to cover.`
                  : "Fresh questions, same role."}
              </span>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <CardTitle><ThumbsUp size={18} className="text-success" /> Strengths</CardTitle>
          <CardContent className="mt-4 space-y-4">
            <FindingList
              items={strengths}
              variant="strength"
              empty="Nothing stood out as a strength this session — start with the areas to improve."
            />
          </CardContent>
        </Card>

        <Card className="p-6">
          <CardTitle><TriangleAlert size={18} className="text-warning" /> Areas to Improve</CardTitle>
          <CardContent className="mt-4 space-y-4">
            <FindingList
              items={improvements}
              variant="improvement"
              empty="Nothing to flag — a strong session all round."
            />
          </CardContent>
        </Card>
      </div>

      <SpeechMetricsCard metrics={report.speech_metrics} />

      <Card className="p-6">
        <CardTitle><Target size={18} className="text-wine-fg" /> Gap Coverage</CardTitle>
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
                stillOpen.map((g) => (
                  <button
                    key={g}
                    onClick={() => router.push(practiceHref)}
                    title={`Practise ${g} again`}
                    className="rounded-badge focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
                  >
                    <Badge variant="warning" className="cursor-pointer hover:opacity-80">
                      {g}
                    </Badge>
                  </button>
                ))
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
