"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { updateJob } from "@/lib/api/jobs";
import { ApiError } from "@/lib/api/client";
import { JOB_STATUS_META, JOB_STATUS_ORDER } from "@/lib/job-status";
import { JOB_PRIORITIES, type JobListItem, type JobUpdateRequest } from "@/lib/types";

interface Props {
  job: JobListItem | null;
  onOpenChange: (open: boolean) => void;
}

/** "" from an empty date/text input means "no value", which the API takes as null. */
const orNull = (value: string) => (value.trim() === "" ? null : value);

export function EditJobDialog({ job, onOpenChange }: Props) {
  const qc = useQueryClient();
  const [saving, setSaving] = useState(false);

  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [status, setStatus] = useState("saved");
  const [priority, setPriority] = useState("normal");
  const [appliedAt, setAppliedAt] = useState("");
  const [deadline, setDeadline] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [notes, setNotes] = useState("");

  // Reload the form whenever a different job is opened. Without this the dialog
  // keeps the previous job's values, which would silently overwrite them.
  useEffect(() => {
    if (!job) return;
    setTitle(job.title ?? "");
    setCompany(job.company ?? "");
    setStatus(job.status);
    setPriority(job.priority);
    setAppliedAt(job.applied_at ?? "");
    setDeadline(job.deadline ?? "");
    setSourceUrl(job.source_url ?? "");
    setNotes(job.notes ?? "");
  }, [job]);

  async function save() {
    if (!job) return;
    setSaving(true);
    const body: JobUpdateRequest = {
      title: orNull(title),
      company: orNull(company),
      status: status as JobUpdateRequest["status"],
      priority: priority as JobUpdateRequest["priority"],
      applied_at: orNull(appliedAt),
      deadline: orNull(deadline),
      source_url: orNull(sourceUrl),
      notes: orNull(notes),
    };
    try {
      await updateJob(job.id, body);
      toast.success("Application updated.");
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job", job.id] });
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save changes.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={job !== null} onOpenChange={(o) => !saving && onOpenChange(o)}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Edit application</DialogTitle>
          <DialogDescription>
            The posting text itself can&apos;t be edited — changing it would invalidate the
            analyses already run against this job.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="edit-title">Role title</Label>
              <Input id="edit-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-company">Company</Label>
              <Input id="edit-company" value={company} onChange={(e) => setCompany(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-status">Stage</Label>
              <Select
                id="edit-status"
                value={status}
                onValueChange={setStatus}
                options={JOB_STATUS_ORDER.map((s) => ({
                  value: s,
                  label: JOB_STATUS_META[s].label,
                }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-priority">Priority</Label>
              <Select
                id="edit-priority"
                value={priority}
                onValueChange={setPriority}
                options={JOB_PRIORITIES.map((p) => ({
                  value: p,
                  label: p[0].toUpperCase() + p.slice(1),
                }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-applied">Applied on</Label>
              <Input
                id="edit-applied"
                type="date"
                value={appliedAt}
                onChange={(e) => setAppliedAt(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-deadline">Closes on</Label>
              <Input
                id="edit-deadline"
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-url">Posting link</Label>
            <Input
              id="edit-url"
              type="url"
              inputMode="url"
              placeholder="https://…"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-notes">Notes</Label>
            <Textarea
              id="edit-notes"
              rows={4}
              placeholder="Referrer, recruiter name, salary range, anything you'll want later…"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving && <Loader2 size={18} className="animate-spin" />}
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
