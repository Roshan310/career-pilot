import { ArrowRight, Check, Mic, Sparkles, X } from "lucide-react";

/**
 * The four feature illustrations, built out of the app's own tokens rather than
 * cropped screenshots. Cropping one dashboard PNG four ways would have shipped
 * four blurry rectangles that go stale the moment a card is redesigned; these
 * restyle themselves with the theme and read correctly at any zoom.
 *
 * They are decorative. Numbers here are illustrative and the whole set is
 * aria-hidden by the panel that frames them, so nothing lands in the a11y tree
 * as if it were the reader's own data.
 */

function MockCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={
        "rounded-card border border-border bg-card p-5 shadow-card-hover " + (className ?? "")
      }
    >
      {children}
    </div>
  );
}

const SIGNALS = [
  { label: "Semantic fit", value: 82 },
  { label: "Skill overlap", value: 71 },
  { label: "Experience level", value: 88 },
  { label: "Keyword density", value: 64 },
];

export function ScoreVisual() {
  const radius = 34;
  const circumference = 2 * Math.PI * radius;

  return (
    <MockCard>
      <div className="flex items-center gap-5">
        <div className="relative h-[86px] w-[86px] shrink-0">
          <svg viewBox="0 0 86 86" className="h-full w-full -rotate-90">
            <circle cx="43" cy="43" r={radius} fill="none" strokeWidth="8" className="stroke-ring-track" />
            <circle
              cx="43"
              cy="43"
              r={radius}
              fill="none"
              strokeWidth="8"
              strokeLinecap="round"
              className="stroke-wine"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - 0.78)}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-[22px] font-bold tracking-tight text-text-primary">78%</span>
          </div>
        </div>
        <div>
          <p className="text-card-title text-text-primary">Strong match</p>
          <p className="mt-1 text-[13px] leading-snug text-text-secondary">
            Senior Backend Engineer · Fintech
          </p>
        </div>
      </div>

      <div className="mt-5 space-y-3 border-t border-divider pt-4">
        {SIGNALS.map((signal) => (
          <div key={signal.label} className="flex items-center gap-3">
            <span className="w-[112px] shrink-0 text-[12px] text-text-secondary">{signal.label}</span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-ring-track">
              <span className="block h-full rounded-full bg-wine" style={{ width: `${signal.value}%` }} />
            </span>
            <span className="w-7 shrink-0 text-right text-[12px] font-semibold tabular-nums text-text-primary">
              {signal.value}
            </span>
          </div>
        ))}
      </div>
    </MockCard>
  );
}

const MISSING = ["Kubernetes", "Terraform", "gRPC"];
const MATCHED = ["Python", "PostgreSQL", "AWS"];

export function GapVisual() {
  return (
    <div className="space-y-4">
      <MockCard>
        <p className="text-[12px] font-semibold uppercase tracking-wide text-text-muted">
          Skills the posting asks for
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {MATCHED.map((skill) => (
            <span
              key={skill}
              className="inline-flex items-center gap-1.5 rounded-badge bg-success-bg px-2.5 py-1 text-[13px] font-medium text-success"
            >
              <Check size={13} />
              {skill}
            </span>
          ))}
          {MISSING.map((skill) => (
            <span
              key={skill}
              className="inline-flex items-center gap-1.5 rounded-badge bg-error-bg px-2.5 py-1 text-[13px] font-medium text-error"
            >
              <X size={13} />
              {skill}
            </span>
          ))}
        </div>
      </MockCard>

      <MockCard>
        <p className="text-[12px] font-semibold uppercase tracking-wide text-text-muted">
          Suggested rewrite
        </p>
        <p className="mt-3 text-[13px] leading-relaxed text-text-muted line-through decoration-text-disabled">
          Worked on the payments service and helped improve performance.
        </p>
        <div className="mt-3 flex items-start gap-2 rounded-xl bg-wine-tint p-3">
          <Sparkles size={14} className="mt-0.5 shrink-0 text-wine-fg" />
          <p className="text-[13px] leading-relaxed text-text-primary">
            Cut p99 latency on the payments service by 40% by moving settlement to an async
            worker queue, serving 12k requests a minute.
          </p>
        </div>
      </MockCard>
    </div>
  );
}

export function InterviewVisual() {
  return (
    <MockCard className="space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-wine text-[11px] font-semibold text-white">
            AI
          </span>
          <span className="text-[12px] font-medium text-text-secondary">Interviewer</span>
        </div>
        <p className="mt-2 rounded-2xl rounded-tl-md bg-hover p-3.5 text-[13px] leading-relaxed text-text-primary">
          You led a team of four at Acme. The posting is heavy on Kubernetes and your resume
          doesn&apos;t mention it — how did your team ship and roll back services?
        </p>
        <p className="mt-2 pl-1 text-[11px] text-text-muted">
          Based on · Acme Corp, 2022–2024 · Gap: Kubernetes
        </p>
      </div>

      <div className="pl-8">
        <p className="rounded-2xl rounded-tr-md bg-wine-tint p-3.5 text-[13px] leading-relaxed text-text-primary">
          We deployed with a managed pipeline, so I owned the rollback runbook rather than the
          orchestration layer itself…
        </p>
        <div className="mt-2 flex items-center justify-end gap-3 text-[11px] text-text-muted">
          <span className="flex items-center gap-1.5">
            <Mic size={11} className="text-wine-fg" />
            Spoken · 48s
          </span>
          <span>3 filler words</span>
          <span>142 wpm</span>
        </div>
      </div>
    </MockCard>
  );
}

const COLUMNS = [
  { label: "Applied", tone: "bg-info", rows: ["Stripe · Backend", "Monzo · Platform"] },
  { label: "Screening", tone: "bg-info", rows: ["Figma · Infra"] },
  { label: "Interviewing", tone: "bg-wine", rows: ["Linear · Product Eng"] },
];

export function PipelineVisual() {
  return (
    <MockCard>
      <div className="grid grid-cols-3 gap-3">
        {COLUMNS.map((column) => (
          <div key={column.label} className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${column.tone}`} />
              <span className="truncate text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                {column.label}
              </span>
            </div>
            <div className="mt-2.5 space-y-2">
              {column.rows.map((row) => (
                <div key={row} className="rounded-xl border border-border bg-background p-2.5">
                  <p className="truncate text-[12px] font-medium text-text-primary">
                    {row.split(" · ")[1]}
                  </p>
                  <p className="truncate text-[11px] text-text-muted">{row.split(" · ")[0]}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between gap-2 rounded-xl bg-warning-bg px-3 py-2.5">
        <p className="truncate text-[12px] font-medium text-warning">
          Linear · Product Eng closes in 2 days
        </p>
        <ArrowRight size={14} className="shrink-0 text-warning" />
      </div>
    </MockCard>
  );
}
