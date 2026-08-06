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
import { createJob } from "@/lib/api/jobs";
import { ApiError } from "@/lib/api/client";
import type { Job } from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (job: Job) => void;
}

export function CreateJobDialog({ open, onOpenChange, onCreated }: Props) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [rawText, setRawText] = useState("");
  const [saving, setSaving] = useState(false);

  function reset() {
    setTitle("");
    setCompany("");
    setRawText("");
  }

  async function handleSave() {
    if (rawText.trim().length < 1) {
      toast.error("Paste the job description text first.");
      return;
    }
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
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) reset();
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
              onChange={(e) => setRawText(e.target.value)}
              placeholder="Paste the full job description here..."
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving && <Loader2 size={18} className="animate-spin" />}
            {saving ? "Parsing..." : "Add & Parse"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
