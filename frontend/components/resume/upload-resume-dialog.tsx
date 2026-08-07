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
const ALLOWED_EXTENSIONS = ["pdf", "docx", "txt"];
/** Mirrors MAX_RESUME_FILE_SIZE_MB on the API. */
const MAX_SIZE_MB = 10;

/**
 * Validates before upload. The `accept` attribute is a file-picker filter only —
 * drag-and-drop bypasses it entirely — and neither size nor type was checked, so
 * a 40MB PNG made the round trip just to come back as a generic server error.
 */
function validateFile(f: File): string | null {
  const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return `${ext ? `.${ext} files aren't` : "That file type isn't"} supported. Use PDF, DOCX, or TXT.`;
  }
  if (f.size > MAX_SIZE_MB * 1024 * 1024) {
    return `That file is ${(f.size / 1024 / 1024).toFixed(1)}MB. The limit is ${MAX_SIZE_MB}MB.`;
  }
  if (f.size === 0) return "That file is empty.";
  return null;
}

export function UploadResumeDialog({ open, onOpenChange, onUploaded }: Props) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  function selectFile(f: File | null) {
    if (!f) {
      setFile(null);
      setFileError(null);
      return;
    }
    const problem = validateFile(f);
    // Keep the name on screen either way, so the message refers to something visible.
    setFile(f);
    setFileError(problem);
  }

  function reset() {
    setFile(null);
    setFileError(null);
    setDragging(false);
    setUploading(false);
  }

  async function handleUpload() {
    if (!file || fileError) return;
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
            selectFile(e.dataTransfer.files?.[0] ?? null);
          }}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          aria-label="Choose a resume file"
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40",
            fileError
              ? "border-error bg-error-bg"
              : dragging
                ? "border-wine bg-wine-tint"
                : "border-border hover:border-border-hover",
          )}
        >
          <div
            className={cn(
              "flex h-12 w-12 items-center justify-center rounded-full",
              fileError ? "bg-error-bg" : "bg-wine-tint",
            )}
          >
            <UploadCloud size={22} className={fileError ? "text-error" : "text-wine-fg"} />
          </div>
          <p className="mt-3 text-[15px] font-medium text-text-primary">
            {file ? file.name : "Click to browse or drag a file here"}
          </p>
          <p className="mt-1 text-[13px] text-text-muted">
            {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : `PDF, DOCX, TXT · up to ${MAX_SIZE_MB}MB`}
          </p>
          {fileError && (
            <p role="alert" className="mt-2 text-[13px] font-medium text-error">
              {fileError}
            </p>
          )}
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
          />
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={uploading}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={!file || !!fileError || uploading}>
            {uploading && <Loader2 size={18} className="animate-spin" />}
            {uploading ? "Parsing..." : "Upload & Parse"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
