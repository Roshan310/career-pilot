"use client";

import { useState } from "react";
import Link from "next/link";
import { Briefcase, Plus } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/empty-state";
import { CreateJobDialog } from "@/components/job/create-job-dialog";
import { useJobs } from "@/hooks/use-data";
import { formatDate } from "@/lib/utils";

export default function JobsPage() {
  const { data: jobs = [], isLoading } = useJobs();
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <div>
      <PageHeader
        title="Job Descriptions"
        subtitle="Save the roles you're targeting to match and prep against them."
        action={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus size={18} /> Add Job
          </Button>
        }
      />

      {isLoading ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-card" />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <Card className="p-6">
          <EmptyState
            icon={Briefcase}
            title="No job descriptions yet"
            description="Paste a job posting to extract its required skills and start matching."
            action={<Button onClick={() => setCreateOpen(true)}>Add Job Description</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((j) => (
            <Link key={j.id} href={`/jobs/${j.id}`} className="block rounded-card focus:outline-none focus-visible:ring-2 focus-visible:ring-wine">
              <Card className="p-5 transition-shadow duration-[180ms] hover:shadow-card-hover">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-wine-tint">
                  <Briefcase size={20} className="text-wine-fg" />
                </div>
                <p className="mt-4 truncate text-[16px] font-semibold text-text-primary">
                  {j.title || "Untitled role"}
                </p>
                <p className="mt-0.5 truncate text-[14px] text-text-secondary">{j.company || "—"}</p>
                <div className="mt-3">
                  <Badge variant="neutral">Added {formatDate(j.created_at)}</Badge>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <CreateJobDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
