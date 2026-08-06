"use client";

import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Briefcase, GraduationCap, Mail, MapPin, Phone, Sparkles, Award } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useResume } from "@/hooks/use-data";
import { formatDate } from "@/lib/utils";

export default function ResumeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: resume, isLoading, isError } = useResume(id);

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

  const p = resume.parsed_data;
  const contact = p.contact ?? {};

  return (
    <div className="space-y-6">
      <button
        onClick={() => router.push("/resumes")}
        className="flex items-center gap-1.5 text-sm font-medium text-text-secondary hover:text-text-primary"
      >
        <ArrowLeft size={16} /> Back to Library
      </button>

      <PageHeader
        title={resume.file_name || "Resume"}
        subtitle={`Version ${resume.version} · Uploaded ${formatDate(resume.created_at)}`}
        action={
          <Button onClick={() => router.push("/analysis")}>Analyze this resume</Button>
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
          <CardTitle><Sparkles size={18} className="text-wine" /> Skills</CardTitle>
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
          <CardTitle><Briefcase size={18} className="text-wine" /> Experience</CardTitle>
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

      {/* Education + certifications */}
      <div className="grid gap-6 lg:grid-cols-2">
        {p.education?.length > 0 && (
          <Card className="p-6">
            <CardTitle><GraduationCap size={18} className="text-wine" /> Education</CardTitle>
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
            <CardTitle><Award size={18} className="text-wine" /> Certifications</CardTitle>
            <CardContent className="mt-4 flex flex-wrap gap-2">
              {p.certifications.map((c, i) => (
                <Badge key={i} variant="neutral">{c}</Badge>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
