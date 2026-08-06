"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileText, FolderClosed, Trash2, Upload } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/empty-state";
import { UploadResumeDialog } from "@/components/resume/upload-resume-dialog";
import { useResumes } from "@/hooks/use-data";
import { deleteResume } from "@/lib/api/resumes";
import { ApiError } from "@/lib/api/client";
import { formatDate } from "@/lib/utils";

export default function ResumesPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: resumes = [], isLoading } = useResumes();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Delete this resume? This cannot be undone.")) return;
    setDeletingId(id);
    try {
      await deleteResume(id);
      toast.success("Resume deleted.");
      qc.invalidateQueries({ queryKey: ["resumes"] });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete resume.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div>
      <PageHeader
        title="Resume Library"
        subtitle="Upload and manage the resumes you match against jobs."
        action={
          <Button onClick={() => setUploadOpen(true)}>
            <Upload size={18} /> Upload Resume
          </Button>
        }
      />

      {isLoading ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-card" />
          ))}
        </div>
      ) : resumes.length === 0 ? (
        <Card className="p-6">
          <EmptyState
            icon={FolderClosed}
            title="Your library is empty"
            description="Upload your first resume to start analyzing it against job descriptions."
            action={<Button onClick={() => setUploadOpen(true)}>Upload Resume</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {resumes.map((r) => (
            <Card
              key={r.id}
              onClick={() => router.push(`/resumes/${r.id}`)}
              className="group cursor-pointer p-5 transition-all duration-[180ms] hover:-translate-y-0.5 hover:shadow-card-hover"
            >
              <div className="flex items-start justify-between">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-wine-tint">
                  <FileText size={20} className="text-wine" />
                </div>
                <button
                  onClick={(e) => handleDelete(r.id, e)}
                  disabled={deletingId === r.id}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-text-muted opacity-0 transition-all hover:bg-error-bg hover:text-error group-hover:opacity-100"
                  aria-label="Delete resume"
                >
                  <Trash2 size={16} />
                </button>
              </div>
              <p className="mt-4 truncate text-[16px] font-semibold text-text-primary">
                {r.file_name || "Untitled resume"}
              </p>
              <div className="mt-2 flex items-center gap-2">
                <Badge variant="neutral">v{r.version}</Badge>
                <span className="text-[13px] text-text-muted">Uploaded {formatDate(r.created_at)}</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      <UploadResumeDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onUploaded={(resume) => router.push(`/resumes/${resume.id}`)}
      />
    </div>
  );
}
