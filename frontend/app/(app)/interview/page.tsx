"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Clock, Info, Loader2, Mic, Plus, Sparkles, Upload } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { RecentInterviews } from "@/components/dashboard/recent-interviews";
import { UploadResumeDialog } from "@/components/resume/upload-resume-dialog";
import { CreateJobDialog } from "@/components/job/create-job-dialog";
import { useInterviews, useJobs, useMatches, useResumes } from "@/hooks/use-data";
import { createInterview } from "@/lib/api/interviews";
import { ApiError } from "@/lib/api/client";
import { isRecordingSupported } from "@/lib/voice";

/**
 * Question generation blocks for 5-15s (deliberately synchronous — see
 * docs/decisions.md), so name what's happening instead of showing a bare
 * spinner for fifteen seconds.
 */
const PREPARING_STEPS = [
  "Reading your resume…",
  "Studying the job description…",
  "Drafting questions about your gaps…",
];

export default function InterviewPracticePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: resumes = [] } = useResumes();
  const { data: jobs = [] } = useJobs();
  const { data: matches = [] } = useMatches();
  const { data: interviews = [], isLoading: interviewsLoading } = useInterviews();

  const [resumeId, setResumeId] = useState("");
  const [jobId, setJobId] = useState("");
  const [matchId, setMatchId] = useState("");
  const [starting, setStarting] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [jobOpen, setJobOpen] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(true);

  // Has to wait for the client — there's no SSR-safe answer. Note this asks
  // whether the browser can *record*, not whether it has speech recognition:
  // transcription happens on the server now, so recording is the only
  // requirement and effectively every browser meets it.
  useEffect(() => setVoiceSupported(isRecordingSupported()), []);

  useEffect(() => {
    if (!starting) return;
    const id = setInterval(() => setStepIndex((i) => Math.min(i + 1, PREPARING_STEPS.length - 1)), 4000);
    return () => clearInterval(id);
  }, [starting]);

  /** Only completed analyses of the selected resume+job can inform the questions. */
  const usableMatches = useMemo(
    () =>
      matches.filter(
        (m) =>
          m.status === "done" &&
          (!resumeId || m.resume_id === resumeId) &&
          (!jobId || m.job_id === jobId),
      ),
    [matches, resumeId, jobId],
  );

  useEffect(() => {
    if (matchId && !usableMatches.some((m) => m.id === matchId)) setMatchId("");
  }, [usableMatches, matchId]);

  const resumable = interviews.filter(
    (i) => i.status === "in_progress" || i.status === "wrapping_up",
  );

  async function start() {
    if (!resumeId || !jobId) {
      toast.error("Pick both a resume and a job description.");
      return;
    }
    setStarting(true);
    setStepIndex(0);
    try {
      const session = await createInterview({
        resume_id: resumeId,
        job_id: jobId,
        match_id: matchId || null,
      });
      qc.invalidateQueries({ queryKey: ["interviews"] });
      router.push(`/interview/${session.id}/session`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not start the interview.");
      setStarting(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Interview Practice"
        subtitle="Voice-driven mock interviews tailored to your resume and target role."
      />

      {resumable.length > 0 && (
        <Card className="flex flex-wrap items-center justify-between gap-4 p-5">
          <div className="flex items-center gap-3">
            <Clock size={18} className="text-wine" />
            <span className="text-[15px] text-text-primary">
              You have an interview in progress.
            </span>
          </div>
          <Button
            variant="secondary"
            onClick={() => router.push(`/interview/${resumable[0].id}/session`)}
          >
            Resume it
          </Button>
        </Card>
      )}

      <Card className="p-6">
        <CardTitle>
          <Mic size={18} className="text-wine" /> New Interview
        </CardTitle>

        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Resume</Label>
            {resumes.length === 0 ? (
              <Button
                variant="secondary"
                className="w-full justify-start"
                onClick={() => setUploadOpen(true)}
              >
                <Upload size={16} /> Upload a resume first
              </Button>
            ) : (
              <Select value={resumeId} onChange={(e) => setResumeId(e.target.value)}>
                <option value="">Select a resume…</option>
                {resumes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.file_name || "Untitled resume"} (v{r.version})
                  </option>
                ))}
              </Select>
            )}
          </div>

          <div className="space-y-2">
            <Label>Job Description</Label>
            {jobs.length === 0 ? (
              <Button
                variant="secondary"
                className="w-full justify-start"
                onClick={() => setJobOpen(true)}
              >
                <Plus size={16} /> Add a job description first
              </Button>
            ) : (
              <Select value={jobId} onChange={(e) => setJobId(e.target.value)}>
                <option value="">Select a job…</option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {[j.title, j.company].filter(Boolean).join(" · ") || "Untitled role"}
                  </option>
                ))}
              </Select>
            )}
          </div>

          <div className="space-y-2 md:col-span-2">
            <Label>Gap analysis (optional)</Label>
            <Select
              value={matchId}
              onChange={(e) => setMatchId(e.target.value)}
              disabled={usableMatches.length === 0}
            >
              <option value="">
                {usableMatches.length === 0
                  ? "No completed analysis for this pairing"
                  : "Don't use one — general questions"}
              </option>
              {usableMatches.map((m) => (
                <option key={m.id} value={m.id}>
                  {[m.job_title, m.job_company].filter(Boolean).join(" · ") || "Analysis"}
                  {m.overall_score !== null ? ` — ${Math.round(m.overall_score * 100)}% match` : ""}
                </option>
              ))}
            </Select>
            <p className="text-[13px] text-text-muted">
              With an analysis attached, questions probe the specific skills you&apos;re missing
              instead of asking generically.
            </p>
          </div>
        </div>

        {!voiceSupported && (
          <div className="mt-5 flex items-start gap-2.5 rounded-card border border-border bg-info-bg px-4 py-3 text-[14px] text-info">
            <Info size={17} className="mt-0.5 shrink-0" />
            <span>
              This browser can&apos;t record audio, so you&apos;ll answer by typing. Questions are
              still read aloud.
            </span>
          </div>
        )}

        <div className="mt-6 flex items-center gap-3">
          <Button onClick={start} disabled={starting || !resumeId || !jobId}>
            {starting ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
            {starting ? "Preparing your interview…" : "Start Interview"}
          </Button>
          <span className="text-[13px] text-text-muted">
            {starting
              ? PREPARING_STEPS[stepIndex]
              : "Up to 8 questions or 20 minutes, whichever comes first."}
          </span>
        </div>
      </Card>

      <RecentInterviews interviews={interviews} loading={interviewsLoading} />

      <UploadResumeDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onUploaded={(r) => setResumeId(r.id)}
      />
      <CreateJobDialog open={jobOpen} onOpenChange={setJobOpen} onCreated={(j) => setJobId(j.id)} />
    </div>
  );
}
