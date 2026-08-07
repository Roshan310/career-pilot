"use client";

import { useState } from "react";
import { ChevronDown, ListChecks } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { StarRating } from "@/components/common/star-rating";
import type { QuestionPlanItem, TurnDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

function turnAverage(turn: TurnDetail): number | null {
  const s = turn.score;
  if (!s || s.structure == null || s.specificity == null || s.relevance == null) return null;
  return (s.structure + s.specificity + s.relevance) / 3;
}

function TurnRow({
  turn,
  defaultOpen,
  plan,
}: {
  turn: TurnDetail;
  defaultOpen: boolean;
  plan?: QuestionPlanItem;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const avg = turnAverage(turn);
  // "" means skipped; null means never reached (shouldn't appear on a report).
  const skipped = turn.answer_transcript === "";

  return (
    <div className="border-b border-divider last:border-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 py-4 text-left"
        aria-expanded={open}
      >
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-hover text-[13px] font-semibold text-text-secondary">
          {turn.turn_number}
        </span>

        <span className="min-w-0 flex-1">
          <span className="block truncate text-[15px] font-medium text-text-primary">
            {turn.question_text}
          </span>
          {turn.question_type === "follow_up" && (
            <span className="text-[12px] text-text-muted">Follow-up</span>
          )}
        </span>

        {skipped ? (
          <Badge variant="neutral">Skipped</Badge>
        ) : avg !== null ? (
          <StarRating value={avg} className="shrink-0" />
        ) : (
          <Badge variant="neutral">Not scored</Badge>
        )}

        <ChevronDown
          size={17}
          className={cn("shrink-0 text-text-muted transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div className="space-y-4 pb-5 pl-10 pr-2">
          {/* Why this question exists. The product's pitch is that every
              question is traceable to your resume and this job; based_on has
              been stored on the plan all along and shown nowhere. */}
          {(plan?.based_on || turn.targets_gap) && (
            <div className="rounded-card border border-divider bg-hover px-4 py-3">
              {plan?.category && (
                <p className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-text-muted">
                  {plan.category}
                </p>
              )}
              {plan?.based_on ? (
                <p className="text-[13px] leading-relaxed text-text-secondary">
                  Asked because your resume says{" "}
                  <span className="text-text-primary">{plan.based_on}</span>
                  {turn.targets_gap && (
                    <>
                      {" "}— probing your gap in{" "}
                      <span className="text-text-primary">{turn.targets_gap}</span>
                    </>
                  )}
                </p>
              ) : (
                <p className="text-[13px] text-text-secondary">
                  Probing your gap in{" "}
                  <span className="text-text-primary">{turn.targets_gap}</span>
                </p>
              )}
            </div>
          )}

          <div>
            <p className="mb-1.5 text-[13px] font-medium text-text-secondary">Your answer</p>
            <p className="whitespace-pre-wrap rounded-card bg-hover px-4 py-3 text-[14px] leading-relaxed text-text-primary">
              {skipped ? "You skipped this question." : turn.answer_transcript}
            </p>
          </div>

          {turn.score && !skipped && (
            <div className="grid gap-3 sm:grid-cols-3">
              {(["structure", "specificity", "relevance"] as const).map((key) => (
                <div key={key}>
                  <p className="text-[13px] capitalize text-text-secondary">{key}</p>
                  <StarRating value={turn.score?.[key] ?? 0} className="mt-1" />
                </div>
              ))}
            </div>
          )}

          {turn.speech_metrics?.wpm != null && (
            <p className="text-[13px] text-text-muted">
              {Math.round(turn.speech_metrics.wpm)} wpm
              {turn.speech_metrics.filler_count != null &&
                ` · ${turn.speech_metrics.filler_count} filler ${turn.speech_metrics.filler_count === 1 ? "word" : "words"}`}
              {turn.answer_duration_seconds != null &&
                ` · ${Math.round(turn.answer_duration_seconds)}s`}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** Per-question detail: what was asked, what you said, and how it scored. */
export function TurnBreakdown({
  turns,
  questionPlan,
}: {
  turns: TurnDetail[];
  questionPlan?: QuestionPlanItem[] | null;
}) {
  const answered = turns.filter((t) => t.answer_transcript !== null);
  if (!answered.length) return null;

  // Matched on question text rather than index: follow-ups are inserted into the
  // turn sequence and are not in the plan, so positions drift apart.
  const planByQuestion = new Map(
    (questionPlan ?? []).map((q) => [q.question_text, q] as const),
  );

  return (
    <Card className="p-6">
      <CardTitle>
        <ListChecks size={18} className="text-wine-fg" /> Question by Question
      </CardTitle>
      <CardContent className="mt-2">
        {answered.map((turn, i) => (
          <TurnRow
            key={turn.turn_number}
            turn={turn}
            defaultOpen={i === 0}
            plan={planByQuestion.get(turn.question_text)}
          />
        ))}
      </CardContent>
    </Card>
  );
}
