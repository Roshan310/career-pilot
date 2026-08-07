"use client";

import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Briefcase, CheckCircle2, FileText, ListChecks, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { BackLink } from "@/components/common/back-link";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useJob } from "@/hooks/use-data";
import { experienceRequired, formatDate } from "@/lib/utils";

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: job, isLoading, isError } = useJob(id);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 rounded-card" />
        <Skeleton className="h-60 rounded-card" />
      </div>
    );
  }

  if (isError || !job) {
    return (
      <Card className="p-10 text-center">
        <p className="text-text-secondary">This job description could not be found.</p>
        <Button variant="secondary" className="mt-4" onClick={() => router.push("/jobs")}>
          Back to Job Descriptions
        </Button>
      </Card>
    );
  }

  // parsed_requirements is JSONB — the database guarantees no shape, and a job
  // whose LLM parse failed stores null. Dereferencing it raised past every
  // boundary and blanked the page.
  const req = job.parsed_requirements ?? {};

  return (
    <div className="space-y-6">
      <BackLink href="/jobs">Back to Job Descriptions</BackLink>

      <PageHeader
        title={job.title || "Untitled role"}
        subtitle={`${job.company || "—"} · Added ${formatDate(job.created_at)}`}
        action={<Button onClick={() => router.push(`/analysis?job=${job.id}`)}>Match a resume</Button>}
      />

      {/* Parsed requirements */}
      <Card className="p-6">
        <CardTitle><Sparkles size={18} className="text-wine-fg" /> Extracted Requirements</CardTitle>
        <CardContent className="mt-5 space-y-6">
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-[14px] text-text-secondary">
            {req.seniority_level && (
              <span className="flex items-center gap-1.5">
                <Briefcase size={15} /> {req.seniority_level}
              </span>
            )}
            {experienceRequired(req.years_experience_required) && (
              <span className="flex items-center gap-1.5">
                <CheckCircle2 size={15} /> {experienceRequired(req.years_experience_required)}
              </span>
            )}
          </div>

          {req.required_skills?.length > 0 && (
            <div>
              <p className="text-[13px] font-semibold uppercase tracking-wide text-text-muted">
                Required skills
              </p>
              <div className="mt-2.5 flex flex-wrap gap-2">
                {req.required_skills.map((s, i) => (
                  <Badge key={i} variant="wine">{s}</Badge>
                ))}
              </div>
            </div>
          )}

          {req.preferred_skills?.length > 0 && (
            <div>
              <p className="text-[13px] font-semibold uppercase tracking-wide text-text-muted">
                Preferred skills
              </p>
              <div className="mt-2.5 flex flex-wrap gap-2">
                {req.preferred_skills.map((s, i) => (
                  <Badge key={i} variant="neutral">{s}</Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Key responsibilities */}
      {req.key_responsibilities?.length > 0 && (
        <Card className="p-6">
          <CardTitle><ListChecks size={18} className="text-wine-fg" /> Key Responsibilities</CardTitle>
          <CardContent className="mt-4">
            <ul className="space-y-2">
              {req.key_responsibilities.map((r, i) => (
                <li key={i} className="flex gap-2 text-[15px] leading-relaxed text-text-secondary">
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-text-muted" />
                  {r}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Original pasted text */}
      {job.raw_text && (
        <Card className="p-6">
          <CardTitle><FileText size={18} className="text-wine-fg" /> Original Job Description</CardTitle>
          <CardContent className="mt-4">
            <p className="whitespace-pre-wrap break-words text-[15px] leading-relaxed text-text-secondary">
              {job.raw_text}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
