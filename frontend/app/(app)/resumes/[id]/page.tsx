"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { Award, Briefcase, Download, FolderGit2, GraduationCap, ListChecks, Loader2, Mail, MapPin, Phone, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { BackLink } from "@/components/common/back-link";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useResume } from "@/hooks/use-data";
import { downloadResumeFile } from "@/lib/api/resumes";
import { ApiError } from "@/lib/api/client";
import { formatDate } from "@/lib/utils";

export default function ResumeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: resume, isLoading, isError } = useResume(id);
  const [downloading, setDownloading] = useState(false);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 rounded-card" />
        <Skeleton className="h-60 rounded-card" />
      </div>
    );
  }

  if (isError || !resume) {
    return (
      <Card className="p-10 text-center">
        <p className="text-text-secondary">This resume could not be found.</p>
        <Button variant="secondary" className="mt-4" onClick={() => router.push("/resumes")}>
          Back to Library
        </Button>
      </Card>
    );
  }

  // Same JSONB caveat as the job page — nullable in the database.
  const p = resume.parsed_data ?? {};
  const contact = p.contact ?? {};

  async function download() {
    if (!resume) return;
    setDownloading(true);
    try {
      // The file is behind the JWT, so it arrives as a blob rather than an href.
      const blob = await downloadResumeFile(resume.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = resume.file_name || "resume";
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Revoking immediately can cancel the download in some browsers.
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not download this file.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-6">
      <BackLink href="/resumes">Back to Library</BackLink>

      <PageHeader
        title={resume.file_name || "Resume"}
        subtitle={`Version ${resume.version} · Uploaded ${formatDate(resume.created_at)}`}
        action={
          <div className="flex flex-wrap gap-3">
            {resume.has_file && (
              <Button variant="secondary" onClick={download} disabled={downloading}>
                {downloading ? <Loader2 size={18} className="animate-spin" /> : <Download size={18} />}
                {downloading ? "Preparing…" : "Download original"}
              </Button>
            )}
            <Button onClick={() => router.push(`/analysis?resume=${resume.id}`)}>
              Analyze this resume
            </Button>
          </div>
        }
      />

      {/* Contact + summary */}
      <Card className="p-6">
        {contact.name && (
          <h2 className="text-h3 text-text-primary">{contact.name}</h2>
        )}
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-[14px] text-text-secondary">
          {contact.email && (
            <span className="flex items-center gap-1.5"><Mail size={15} /> {contact.email}</span>
          )}
          {contact.phone && (
            <span className="flex items-center gap-1.5"><Phone size={15} /> {contact.phone}</span>
          )}
          {contact.location && (
            <span className="flex items-center gap-1.5"><MapPin size={15} /> {contact.location}</span>
          )}
        </div>
        {p.summary && (
          <p className="mt-4 border-t border-divider pt-4 text-[15px] leading-relaxed text-text-secondary">
            {p.summary}
          </p>
        )}
      </Card>

      {/* Skills */}
      {p.skills?.length > 0 && (
        <Card className="p-6">
          <CardTitle><Sparkles size={18} className="text-wine-fg" /> Skills</CardTitle>
          <CardContent className="mt-4 flex flex-wrap gap-2">
            {p.skills.map((s, i) => (
              <Badge key={i} variant="wine">{s}</Badge>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Experience */}
      {p.experience?.length > 0 && (
        <Card className="p-6">
          <CardTitle><Briefcase size={18} className="text-wine-fg" /> Experience</CardTitle>
          <CardContent className="mt-5 space-y-6">
            {p.experience.map((exp, i) => (
              <div key={i} className="border-l-2 border-divider pl-4">
                <p className="text-[16px] font-semibold text-text-primary">
                  {exp.title || "Role"}
                  {exp.company && <span className="text-text-secondary"> · {exp.company}</span>}
                </p>
                {(exp.start_date || exp.end_date) && (
                  <p className="mt-0.5 text-[13px] text-text-muted">
                    {exp.start_date || "?"} — {exp.end_date || "Present"}
                  </p>
                )}
                {exp.bullets?.length > 0 && (
                  <ul className="mt-2.5 space-y-1.5">
                    {exp.bullets.map((b, j) => (
                      <li key={j} className="flex gap-2 text-[15px] leading-relaxed text-text-secondary">
                        <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-text-muted" />
                        {b}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Projects — where an early-career candidate's real evidence lives, and
          what the parser used to drop entirely for want of a field to put it in. */}
      {(p.projects?.length ?? 0) > 0 && (
        <Card className="p-6">
          <CardTitle><FolderGit2 size={18} className="text-wine-fg" /> Projects</CardTitle>
          <CardContent className="mt-5 space-y-6">
            {p.projects!.map((proj, i) => (
              <div key={i} className="border-l-2 border-divider pl-4">
                <p className="text-[16px] font-semibold text-text-primary">
                  {proj.url ? (
                    <a
                      href={proj.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
                    >
                      {proj.name || "Project"}
                    </a>
                  ) : (
                    proj.name || "Project"
                  )}
                </p>
                {(proj.start_date || proj.end_date) && (
                  <p className="mt-0.5 text-[13px] text-text-muted">
                    {proj.start_date || "?"} — {proj.end_date || "Present"}
                  </p>
                )}
                {proj.description && (
                  <p className="mt-2 text-[15px] leading-relaxed text-text-secondary">
                    {proj.description}
                  </p>
                )}
                {(proj.technologies?.length ?? 0) > 0 && (
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    {proj.technologies.map((t, j) => (
                      <Badge key={j} variant="neutral">{t}</Badge>
                    ))}
                  </div>
                )}
                {(proj.bullets?.length ?? 0) > 0 && (
                  <ul className="mt-2.5 space-y-1.5">
                    {proj.bullets.map((b, j) => (
                      <li key={j} className="flex gap-2 text-[15px] leading-relaxed text-text-secondary">
                        <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-text-muted" />
                        {b}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Education + certifications */}
      <div className="grid gap-6 lg:grid-cols-2">
        {p.education?.length > 0 && (
          <Card className="p-6">
            <CardTitle><GraduationCap size={18} className="text-wine-fg" /> Education</CardTitle>
            <CardContent className="mt-4 space-y-4">
              {p.education.map((e, i) => (
                <div key={i}>
                  <p className="text-[15px] font-semibold text-text-primary">{e.degree || "Degree"}</p>
                  <p className="text-[14px] text-text-secondary">
                    {e.institution}
                    {e.year ? ` · ${e.year}` : ""}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {p.certifications?.length > 0 && (
          <Card className="p-6">
            <CardTitle><Award size={18} className="text-wine-fg" /> Certifications</CardTitle>
            <CardContent className="mt-4 flex flex-wrap gap-2">
              {p.certifications.map((c, i) => (
                <Badge key={i} variant="neutral">{c}</Badge>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
      {/* Whatever else the resume contained. The point of the catch-all is that
          nothing gets silently discarded for not fitting a named field. */}
      {(p.additional_sections?.length ?? 0) > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          {p.additional_sections!.map((section, i) => (
            <Card key={i} className="p-6">
              <CardTitle><ListChecks size={18} className="text-wine-fg" /> {section.heading}</CardTitle>
              <CardContent className="mt-4 space-y-2">
                {section.items.map((item, j) => (
                  <p key={j} className="flex gap-2 text-[15px] leading-relaxed text-text-secondary">
                    <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-text-muted" />
                    {item}
                  </p>
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
