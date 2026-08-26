"use client";

import { useMemo, useState } from "react";
import { FileText, Mic, Target } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { useInterviewReport, useInterviews, useMatch, useMatches, useResumes } from "@/hooks/use-data";
import { HeroSection } from "@/components/dashboard/hero-section";
import { ResumeStrengthCard } from "@/components/dashboard/resume-strength-card";
import { InterviewReadinessCard } from "@/components/dashboard/interview-readiness-card";
import { RecentAnalyses } from "@/components/dashboard/recent-analyses";
import { RecentInterviews } from "@/components/dashboard/recent-interviews";
import { StatCard } from "@/components/common/stat-card";
import { UploadResumeDialog } from "@/components/resume/upload-resume-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useReviewedReports } from "@/hooks/use-reviewed-reports";

function withinLastWeek(iso: string): boolean {
  const then = new Date(iso).getTime();
  return Date.now() - then <= 7 * 24 * 60 * 60 * 1000;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [uploadOpen, setUploadOpen] = useState(false);

  const { data: resumes = [] } = useResumes();
  const { data: matches = [], isLoading: matchesLoading } = useMatches();
  const { data: interviews = [], isLoading: interviewsLoading } = useInterviews();

  const latestDoneMatch = useMemo(
    () => matches.find((m) => m.status === "done" && m.overall_score !== null) ?? null,
    [matches],
  );
  const { data: matchDetail, isLoading: detailLoading } = useMatch(latestDoneMatch?.id);

  const latestInterview = useMemo(
    () => interviews.find((i) => i.status === "completed" && i.overall_score !== null) ?? null,
    [interviews],
  );
  const { data: report, isLoading: reportLoading } = useInterviewReport(latestInterview?.id ?? "");
  const { hasAny: hasReviewedFeedback } = useReviewedReports();

  // ---- derived stats ----
  const doneMatches = matches.filter((m) => m.status === "done");
  const completedInterviews = interviews.filter((i) => i.status === "completed");
  const avgScore = useMemo(() => {
    const scored = doneMatches.filter((m) => m.overall_score !== null);
    if (!scored.length) return 0;
    return Math.round(
      (scored.reduce((sum, m) => sum + (m.overall_score ?? 0), 0) / scored.length) * 100,
    );
  }, [doneMatches]);

  // Without this the cards mount showing 0 and count up to the real figure once
  // the queries land, which looks like a glitch rather than a reveal.
  const statsLoading = matchesLoading || interviewsLoading;

  const matchesThisWeek = doneMatches.filter((m) => withinLastWeek(m.created_at)).length;
  const interviewsThisWeek = completedInterviews.filter((i) => withinLastWeek(i.started_at)).length;

  // ---- progress ----
  // Every item is derived from something real. The previous list had two entries
  // hardcoded to `false`, so the ring could never pass 3/5, and "Feedback
  // reviewed" was aliased to "interview completed" — it ticked whether or not the
  // report was ever opened.
  const hasResume = resumes.length > 0;
  const hasAnalysis = doneMatches.length > 0;
  const hasInterview = completedInterviews.length > 0;
  const progressItems = [
    { label: "Resume uploaded", done: hasResume },
    { label: "Resume analyzed", done: hasAnalysis },
    { label: "Interview completed", done: hasInterview },
    { label: "Feedback reviewed", done: hasReviewedFeedback },
  ];
  const progressDone = progressItems.filter((i) => i.done).length;

  // A green "↑ 0 this week" on a brand-new account reads as a broken widget.
  const up = (n: number, unit: string) =>
    n > 0 ? (
      <span className="text-success">↑ {n} {unit}</span>
    ) : (
      <span className="text-text-muted">No change {unit}</span>
    );

  return (
    <div className="space-y-8">
      <HeroSection
        user={user}
        progress={{ done: progressDone, total: progressItems.length, items: progressItems }}
        onUpload={() => setUploadOpen(true)}
      />

      <section className="grid gap-6 lg:grid-cols-2">
        <ResumeStrengthCard
          listItem={latestDoneMatch}
          detail={matchDetail}
          loading={matchesLoading || (!!latestDoneMatch && detailLoading)}
        />
        <InterviewReadinessCard
          listItem={latestInterview}
          report={report}
          loading={interviewsLoading || (!!latestInterview && reportLoading)}
        />
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <RecentAnalyses matches={matches} loading={matchesLoading} />
        </div>
        <RecentInterviews interviews={interviews} loading={interviewsLoading} />
      </section>

      <section className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
        {statsLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-[88px] rounded-card" />
          ))
        ) : (
          <>
        <StatCard
          icon={FileText}
          label="Resumes Analyzed"
          value={doneMatches.length}
          delta={up(matchesThisWeek, "this week")}
          index={0}
        />
        <StatCard
          icon={Mic}
          label="Interviews Completed"
          value={completedInterviews.length}
          delta={up(interviewsThisWeek, "this week")}
          index={1}
        />
        <StatCard
          icon={Target}
          label="Average Match Score"
          value={avgScore}
          suffix="%"
          index={2}
        />
          </>
        )}
      </section>

      <UploadResumeDialog open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  );
}
