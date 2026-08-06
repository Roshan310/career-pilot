"use client";

import { useParams, useRouter } from "next/navigation";
import { AlertCircle, ArrowLeft, CheckCircle2, Lightbulb, Loader2, TriangleAlert } from "lucide-react";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProgressRing } from "@/components/common/progress-ring";
import { CountUp } from "@/components/common/count-up";
import { useJob, useMatchPolling } from "@/hooks/use-data";
import { scorePct, skillName } from "@/lib/utils";

function scoreLabel(pct: number) {
  if (pct >= 85) return "Excellent";
  if (pct >= 70) return "Strong";
  if (pct >= 50) return "Fair";
  return "Needs Work";
}

function SubScore({ label, score }: { label: string; score: number | null }) {
  const pct = scorePct(score) ?? 0;
  return (
    <div>
      <div className="flex items-center justify-between text-[14px]">
        <span className="text-text-secondary">{label}</span>
        <span className="font-semibold text-text-primary">{pct}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-divider">
        <div className="h-full rounded-full bg-wine transition-all duration-700" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function MatchReportPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: match, isLoading } = useMatchPolling(id);
  const { data: job } = useJob(match?.status === "done" ? match.job_id : "");

  const back = (
    <button
      onClick={() => router.push("/analysis")}
      className="flex items-center gap-1.5 text-sm font-medium text-text-secondary hover:text-text-primary"
    >
      <ArrowLeft size={16} /> Back to Analysis
    </button>
  );

  if (isLoading || !match) {
    return (
      <div className="space-y-6">
        {back}
        <Card className="p-14 text-center">
          <Loader2 size={28} className="mx-auto animate-spin text-wine" />
          <p className="mt-4 text-text-secondary">Loading analysis…</p>
        </Card>
      </div>
    );
  }

  if (match.status === "pending" || match.status === "processing") {
    return (
      <div className="space-y-6">
        {back}
        <Card className="p-14 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-wine-tint">
            <Loader2 size={26} className="animate-spin text-wine" />
          </div>
          <h3 className="mt-5 text-h3 text-text-primary">Analyzing your resume…</h3>
          <p className="mt-2 text-text-secondary">
            We&apos;re scoring the match and generating suggestions. This usually takes a few seconds.
          </p>
        </Card>
      </div>
    );
  }

  if (match.status === "failed") {
    return (
      <div className="space-y-6">
        {back}
        <Card className="p-14 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-error-bg">
            <AlertCircle size={26} className="text-error" />
          </div>
          <h3 className="mt-5 text-h3 text-text-primary">Analysis failed</h3>
          <p className="mt-2 text-text-secondary">{match.error_message || "Something went wrong while scoring this match."}</p>
          <Button className="mt-5" onClick={() => router.push("/analysis")}>Try another analysis</Button>
        </Card>
      </div>
    );
  }

  // done
  const pct = scorePct(match.overall_score) ?? 0;
  const matched = match.matched_skills ?? [];
  const missing = match.missing_skills ?? [];
  const suggestions = match.suggestions ?? [];

  return (
    <div className="space-y-6">
      {back}

      {/* Score hero */}
      <Card className="p-6">
        <div className="flex flex-col items-center gap-8 sm:flex-row">
          <ProgressRing value={pct / 100} size={176} thickness={11}>
            <span className="text-[38px] font-bold leading-none text-text-primary">
              <CountUp value={pct} suffix="%" />
            </span>
            <span className="mt-1 text-[15px] font-medium text-text-secondary">{scoreLabel(pct)}</span>
          </ProgressRing>
          <div className="flex-1">
            <p className="text-[15px] font-semibold text-text-primary">Overall Match Score</p>
            <p className="mt-1 text-[15px] text-text-secondary">
              Against{" "}
              <span className="font-medium text-text-primary">{job?.title || "the selected role"}</span>
              {job?.company ? ` at ${job.company}` : ""}.
            </p>
            <div className="mt-5 grid max-w-md gap-4">
              <SubScore label="Semantic Similarity" score={match.semantic_score} />
              <SubScore label="Skill Overlap" score={match.skill_overlap_score} />
              <SubScore label="Experience Match" score={match.experience_match_score} />
              <SubScore label="Keyword Density" score={match.keyword_density_score} />
            </div>
          </div>
        </div>
      </Card>

      {/* Skills */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <CardTitle><CheckCircle2 size={18} className="text-success" /> Matched Skills</CardTitle>
          <CardContent className="mt-4 flex flex-wrap gap-2">
            {matched.length ? (
              matched.map((s, i) => <Badge key={i} variant="success">{skillName(s)}</Badge>)
            ) : (
              <p className="text-[15px] text-text-secondary">No overlapping skills detected.</p>
            )}
          </CardContent>
        </Card>

        <Card className="p-6">
          <CardTitle><TriangleAlert size={18} className="text-warning" /> Missing Skills</CardTitle>
          <CardContent className="mt-4 flex flex-wrap gap-2">
            {missing.length ? (
              missing.map((s, i) => <Badge key={i} variant="warning">{skillName(s)}</Badge>)
            ) : (
              <p className="text-[15px] text-text-secondary">Great — no required skills are missing.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Suggestions */}
      <Card className="p-6">
        <CardTitle><Lightbulb size={18} className="text-wine" /> Rewrite Suggestions</CardTitle>
        <CardContent className="mt-4 space-y-4">
          {suggestions.length ? (
            suggestions.map((s, i) => (
              <div key={i} className="rounded-2xl border border-border bg-background p-4">
                {s.missing_skill && (
                  <Badge variant="wine" className="mb-2">{s.missing_skill}</Badge>
                )}
                <p className="text-[15px] leading-relaxed text-text-primary">{s.suggestion}</p>
                {s.has_honest_connection === false && (
                  <p className="mt-2 text-[13px] text-warning">
                    Note: only use this if it reflects genuine experience.
                  </p>
                )}
              </div>
            ))
          ) : (
            <p className="text-[15px] text-text-secondary">
              No rewrite suggestions were generated for this match.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
