"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, UploadCloud } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { uploadResume } from "@/lib/api/resumes";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { Resume } from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploaded?: (resume: Resume) => void;
}

const ACCEPT = ".pdf,.docx,.txt";

export function UploadResumeDialog({ open, onOpenChange, onUploaded }: Props) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  function reset() {
    setFile(null);
    setDragging(false);
    setUploading(false);
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    try {
      const resume = await uploadResume(file);
      toast.success("Resume uploaded and parsed successfully.");
      qc.invalidateQueries({ queryKey: ["resumes"] });
      onUploaded?.(resume);
      onOpenChange(false);
      reset();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
    } finally {
      setUploading(false);
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
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload Resume</DialogTitle>
          <DialogDescription>
            We&apos;ll extract and parse the content automatically. PDF, DOCX, or TXT up to 10MB.
          </DialogDescription>
        </DialogHeader>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) setFile(f);
          }}
          onClick={() => inputRef.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors",
            dragging ? "border-wine bg-wine-tint" : "border-border hover:border-border-hover",
          )}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-wine-tint">
            <UploadCloud size={22} className="text-wine" />
          </div>
          <p className="mt-3 text-[15px] font-medium text-text-primary">
            {file ? file.name : "Click to browse or drag a file here"}
          </p>
          <p className="mt-1 text-[13px] text-text-muted">
            {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "PDF, DOCX, TXT"}
          </p>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={uploading}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={!file || uploading}>
            {uploading && <Loader2 size={18} className="animate-spin" />}
            {uploading ? "Parsing..." : "Upload & Parse"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
