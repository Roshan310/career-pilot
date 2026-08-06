"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, FileText, FileSearch } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { ScoreBadge } from "@/components/common/status-badge";
import { EmptyState } from "@/components/common/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, scorePct } from "@/lib/utils";
import type { MatchListItem } from "@/lib/types";

interface Props {
  matches: MatchListItem[];
  loading: boolean;
}

export function RecentAnalyses({ matches, loading }: Props) {
  const router = useRouter();
  const rows = matches.filter((m) => m.status === "done").slice(0, 5);

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between">
        <span className="text-card-title text-text-primary">Recent Resume Analyses</span>
        <Button variant="secondary" size="sm" onClick={() => router.push("/analysis")}>
          View All
        </Button>
      </div>

      <div className="mt-4">
        {loading ? (
          <div className="space-y-3 py-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={FileSearch}
            title="No analyses yet"
            description="Match a resume against a job description to see your results here."
            action={<Button onClick={() => router.push("/analysis")}>Run an Analysis</Button>}
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Resume</TH>
                <TH>Company / Role</TH>
                <TH>Match Score</TH>
                <TH>Analyzed On</TH>
                <TH className="text-right">Action</TH>
              </TR>
            </THead>
            <TBody>
              {rows.map((m) => (
                <TR
                  key={m.id}
                  className="cursor-pointer hover:bg-background"
                  onClick={() => router.push(`/analysis/${m.id}`)}
                >
                  <TD>
                    <span className="flex items-center gap-2.5">
                      <FileText size={17} className="text-text-muted" />
                      <span className="max-w-[180px] truncate">{m.resume_file_name || "Resume"}</span>
                    </span>
                  </TD>
                  <TD>
                    <span className="text-text-secondary">
                      {m.job_company || "—"}
                      {m.job_title ? ` · ${m.job_title}` : ""}
                    </span>
                  </TD>
                  <TD>
                    <ScoreBadge pct={scorePct(m.overall_score)} />
                  </TD>
                  <TD className="text-text-secondary">{formatDate(m.created_at)}</TD>
                  <TD className="text-right">
                    <span className="inline-flex items-center gap-1 font-medium text-wine">
                      Open <ArrowRight size={15} />
                    </span>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </div>
    </Card>
  );
}
