"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Briefcase, ExternalLink, Pencil, Plus, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { CreateJobDialog } from "@/components/job/create-job-dialog";
import { EditJobDialog } from "@/components/job/edit-job-dialog";
import { useJobs, useMatches } from "@/hooks/use-data";
import { deleteJob, updateJob } from "@/lib/api/jobs";
import { ApiError } from "@/lib/api/client";
import { JOB_STATUS_META, JOB_STATUS_ORDER, deadlineLabel } from "@/lib/job-status";
import { cn, formatDate, scorePct } from "@/lib/utils";
import type { JobListItem, JobStatus } from "@/lib/types";

export default function JobsPage() {
  const qc = useQueryClient();
  const { data: jobs = [], isLoading } = useJobs();
  // Best score per job, so a card can say whether it's worth pursuing. The
  // matches list is already fetched elsewhere and cached — no new endpoint.
  const { data: matches = [] } = useMatches();

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<JobListItem | null>(null);
  const [pendingDelete, setPendingDelete] = useState<JobListItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [movingId, setMovingId] = useState<string | null>(null);

  const bestScoreByJob = useMemo(() => {
    const best = new Map<string, number>();
    for (const m of matches) {
      if (m.status !== "done" || m.overall_score === null) continue;
      const current = best.get(m.job_id);
      if (current === undefined || m.overall_score > current) best.set(m.job_id, m.overall_score);
    }
    return best;
  }, [matches]);

  const grouped = useMemo(() => {
    const byStatus = new Map<JobStatus, JobListItem[]>();
    for (const status of JOB_STATUS_ORDER) byStatus.set(status, []);
    for (const job of jobs) {
      // An unrecognised status (older row, hand-edited data) still has to appear
      // somewhere rather than vanishing from the board.
      const bucket = byStatus.get(job.status) ?? byStatus.get("saved")!;
      bucket.push(job);
    }
    return byStatus;
  }, [jobs]);

  async function moveTo(job: JobListItem, status: JobStatus) {
    setMovingId(job.id);
    try {
      // Stamp the application date the first time it's marked applied, so the
      // common case needs no trip through the edit dialog.
      const body =
        status === "applied" && !job.applied_at
          ? { status, applied_at: new Date().toISOString().slice(0, 10) }
          : { status };
      await updateJob(job.id, body);
      qc.invalidateQueries({ queryKey: ["jobs"] });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update this application.");
    } finally {
      setMovingId(null);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await deleteJob(pendingDelete.id);
      toast.success("Application removed.");
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["matches"] });
      setPendingDelete(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete this application.");
    } finally {
      setDeleting(false);
    }
  }

  const active = jobs.filter((j) => j.status !== "rejected" && j.status !== "offer").length;

  return (
    <div>
      <PageHeader
        title="Applications"
        subtitle={
          jobs.length
            ? `${jobs.length} tracked · ${active} still in play`
            : "Track the roles you're going after, and prep against each one."
        }
        action={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus size={18} /> Add Job
          </Button>
        }
      />

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-card" />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <Card className="p-6">
          <EmptyState
            icon={Briefcase}
            title="No applications yet"
            description="Add a job posting to extract its requirements, match your resume against it, and track where it goes."
            action={<Button onClick={() => setCreateOpen(true)}>Add Job Description</Button>}
          />
        </Card>
      ) : (
        <div className="space-y-8">
          {JOB_STATUS_ORDER.map((status) => {
            const rows = grouped.get(status) ?? [];
            if (rows.length === 0) return null;
            const meta = JOB_STATUS_META[status];

            return (
              <section key={status}>
                <div className="mb-3 flex items-baseline gap-3">
                  <h2 className="text-card-title text-text-primary">{meta.label}</h2>
                  <span className="text-[13px] text-text-muted">
                    {rows.length} · {meta.hint}
                  </span>
                </div>

                <div className="space-y-3">
                  {rows.map((job) => {
                    const score = scorePct(bestScoreByJob.get(job.id) ?? null);
                    const closing = deadlineLabel(job.deadline);

                    return (
                      <Card key={job.id} className="flex flex-wrap items-center gap-4 p-4">
                        {/* min-w-0 lets the title truncate instead of pushing the
                            controls off the card on a narrow screen. */}
                        <div className="flex min-w-0 flex-1 items-center gap-3">
                          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-wine-tint">
                            <Briefcase size={18} className="text-wine-fg" />
                          </div>
                          <div className="min-w-0">
                            <Link
                              href={`/jobs/${job.id}`}
                              className="block truncate rounded text-[16px] font-semibold text-text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
                            >
                              {job.title || "Untitled role"}
                            </Link>
                            <p className="mt-0.5 flex flex-wrap items-center gap-x-2 truncate text-[13px] text-text-secondary">
                              <span>{job.company || "—"}</span>
                              {job.priority === "high" && (
                                <Badge variant="warning" className="h-5 px-2 text-[11px]">
                                  High priority
                                </Badge>
                              )}
                              {closing && (
                                <span className={cn(closing.urgent && "font-medium text-warning")}>
                                  · {closing.text}
                                </span>
                              )}
                              {job.applied_at && <span>· Applied {formatDate(job.applied_at)}</span>}
                            </p>
                          </div>
                        </div>

                        <div className="flex shrink-0 items-center gap-2">
                          {score !== null ? (
                            <Link
                              href="/analysis"
                              className="rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
                              title="Best match score for this role"
                            >
                              <Badge variant={score >= 70 ? "success" : score >= 50 ? "info" : "warning"}>
                                {score}% match
                              </Badge>
                            </Link>
                          ) : (
                            <Link
                              href={`/analysis?job=${job.id}`}
                              className="rounded text-[13px] font-medium text-wine-fg hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
                            >
                              Run analysis
                            </Link>
                          )}

                          {job.source_url && (
                            <a
                              href={job.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              aria-label="Open the original posting"
                              className="flex h-9 w-9 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-hover hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
                            >
                              <ExternalLink size={16} />
                            </a>
                          )}

                          <Select
                            aria-label={`Stage for ${job.title || "this role"}`}
                            value={job.status}
                            disabled={movingId === job.id}
                            onChange={(e) => moveTo(job, e.target.value as JobStatus)}
                            className="h-9 w-[142px] text-[14px]"
                          >
                            {JOB_STATUS_ORDER.map((s) => (
                              <option key={s} value={s}>
                                {JOB_STATUS_META[s].label}
                              </option>
                            ))}
                          </Select>

                          <button
                            onClick={() => setEditing(job)}
                            aria-label={`Edit ${job.title || "this application"}`}
                            className="flex h-9 w-9 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-hover hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
                          >
                            <Pencil size={16} />
                          </button>
                          <button
                            onClick={() => setPendingDelete(job)}
                            aria-label={`Delete ${job.title || "this application"}`}
                            className="flex h-9 w-9 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-error-bg hover:text-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-error/40"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      )}

      <CreateJobDialog open={createOpen} onOpenChange={setCreateOpen} />
      <EditJobDialog job={editing} onOpenChange={(open) => !open && setEditing(null)} />

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        title="Delete this application?"
        description={`"${pendingDelete?.title || "This role"}" and every resume analysis run against it will be permanently removed. Past interviews are kept, but lose their link to this role.`}
        confirmLabel="Delete application"
        destructive
        pending={deleting}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
