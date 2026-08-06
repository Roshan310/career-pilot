"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Plus, Sparkles, Upload } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { RecentAnalyses } from "@/components/dashboard/recent-analyses";
import { UploadResumeDialog } from "@/components/resume/upload-resume-dialog";
import { CreateJobDialog } from "@/components/job/create-job-dialog";
import { useJobs, useMatches, useResumes } from "@/hooks/use-data";
import { createMatch } from "@/lib/api/matches";
import { ApiError } from "@/lib/api/client";

export default function AnalysisPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: resumes = [] } = useResumes();
  const { data: jobs = [] } = useJobs();
  const { data: matches = [], isLoading: matchesLoading } = useMatches();

  const [resumeId, setResumeId] = useState("");
  const [jobId, setJobId] = useState("");
  const [running, setRunning] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [jobOpen, setJobOpen] = useState(false);

  async function runAnalysis() {
    if (!resumeId || !jobId) {
      toast.error("Select both a resume and a job description.");
      return;
    }
    setRunning(true);
    try {
      const res = await createMatch(resumeId, jobId);
      qc.invalidateQueries({ queryKey: ["matches"] });
      router.push(`/analysis/${res.id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not start analysis.");
      setRunning(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Resume Analysis"
        subtitle="Match a resume against a job description for a multi-signal score and gap analysis."
      />

      <Card className="p-6">
        <CardTitle><Sparkles size={18} className="text-wine" /> New Analysis</CardTitle>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Resume</Label>
            {resumes.length === 0 ? (
              <Button variant="secondary" className="w-full justify-start" onClick={() => setUploadOpen(true)}>
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
              <Button variant="secondary" className="w-full justify-start" onClick={() => setJobOpen(true)}>
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
        </div>

        <div className="mt-6 flex items-center gap-3">
          <Button onClick={runAnalysis} disabled={running || !resumeId || !jobId}>
            {running && <Loader2 size={18} className="animate-spin" />}
            {running ? "Starting…" : "Run Analysis"}
          </Button>
          <span className="text-[13px] text-text-muted">
            Analysis runs in the background — you&apos;ll see live progress.
          </span>
        </div>
      </Card>

      <RecentAnalyses matches={matches} loading={matchesLoading} />

      <UploadResumeDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onUploaded={(r) => setResumeId(r.id)}
      />
      <CreateJobDialog open={jobOpen} onOpenChange={setJobOpen} onCreated={(j) => setJobId(j.id)} />
    </div>
  );
}
