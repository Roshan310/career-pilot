"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { createJob } from "@/lib/api/jobs";
import { ApiError } from "@/lib/api/client";
import type { Job } from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (job: Job) => void;
}

/**
 * A one-character description technically passed the old check and was sent
 * straight to the LLM. This is roughly the shortest text that can yield a usable
 * parse.
 */
const MIN_JD_LENGTH = 80;

export function CreateJobDialog({ open, onOpenChange, onCreated }: Props) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [rawText, setRawText] = useState("");
  const [saving, setSaving] = useState(false);
  const [jdError, setJdError] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  const dirty = title.trim() !== "" || company.trim() !== "" || rawText.trim() !== "";

  function reset() {
    setTitle("");
    setCompany("");
    setRawText("");
    setJdError(null);
  }

  /** Escape, overlay click and Cancel all land here. */
  function requestClose() {
    if (dirty) {
      setConfirmDiscard(true);
      return;
    }
    onOpenChange(false);
    reset();
  }

  function validateJd(text: string): string | null {
    const trimmed = text.trim();
    if (!trimmed) return "Paste the job description text first.";
    if (trimmed.length < MIN_JD_LENGTH)
      return `That's too short to parse — paste the full posting (at least ${MIN_JD_LENGTH} characters).`;
    return null;
  }

  async function handleSave() {
    const problem = validateJd(rawText);
    setJdError(problem);
    if (problem) return;
    setSaving(true);
    try {
      const job = await createJob({ title: title || null, company: company || null, raw_text: rawText });
      toast.success("Job description added and parsed.");
      qc.invalidateQueries({ queryKey: ["jobs"] });
      onCreated?.(job);
      onOpenChange(false);
      reset();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save job description.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
    <Dialog
      open={open}
      onOpenChange={(o) => {
        // Closing must go through requestClose — a stray Escape used to wipe a
        // long pasted description with no warning.
        if (o) onOpenChange(true);
        else requestClose();
      }}
    >
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Add Job Description</DialogTitle>
          <DialogDescription>
            Paste a job posting and we&apos;ll extract the required skills and seniority automatically.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="title">Role title</Label>
              <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Senior Backend Engineer" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="company">Company</Label>
              <Input id="company" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Stripe" />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="jd">Job description</Label>
            <Textarea
              id="jd"
              rows={9}
              value={rawText}
              onChange={(e) => {
                setRawText(e.target.value);
                if (jdError) setJdError(validateJd(e.target.value));
              }}
              error={jdError}
              placeholder="Paste the full job description here..."
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={requestClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving && <Loader2 size={18} className="animate-spin" />}
            {saving ? "Parsing..." : "Add & Parse"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>

    <ConfirmDialog
      open={confirmDiscard}
      onOpenChange={setConfirmDiscard}
      title="Discard this job description?"
      description="What you've pasted here will be lost."
      confirmLabel="Discard"
      cancelLabel="Keep editing"
      destructive
      onConfirm={() => {
        setConfirmDiscard(false);
        onOpenChange(false);
        reset();
      }}
    />
    </>
  );
}
