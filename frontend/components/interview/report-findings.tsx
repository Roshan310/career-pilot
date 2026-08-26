"use client";

import { CheckCircle2, TriangleAlert } from "lucide-react";
import type { FindingCode, ReportFinding, ReportItem } from "@/lib/types";

/**
 * The report's Strengths / Areas to Improve columns.
 *
 * The backend (`services/report_findings.py`) sends facts and a stable `code`;
 * every human-readable word lives here. That split is deliberate: wording gets
 * iterated on constantly, and re-running a data backfill for a copy tweak would
 * not be tolerable.
 *
 * Findings describe patterns across the whole session. Per-question detail is
 * the job of `TurnBreakdown` further down the same page, so nothing here repeats it.
 */

interface Copy {
  title: (f: ReportFinding) => string;
  body: (f: ReportFinding) => string;
  /** Shown instead of `body` when the finding is a ranking rather than a verdict. */
  relativeBody?: (f: ReportFinding) => string;
  exemplarLabel?: string;
}

const round = (n: number | null | undefined) => (n == null ? "—" : Math.round(n));
const answers = (n: number) => `${n} ${n === 1 ? "answer" : "answers"}`;

const FINDING_COPY: Record<FindingCode, Copy> = {
  // — Dimensions ————————————————————————————————————————————————
  structure_strong: {
    title: () => "Well-structured answers",
    body: () =>
      "Your answers followed a clear arc — the situation, what you did, how it turned out — so they were easy to follow.",
    relativeBody: () =>
      "This held up best of the three, though there's room to grow across the board. Your answers mostly followed a clear arc.",
  },
  specificity_strong: {
    title: () => "Concrete, specific answers",
    body: () =>
      "You backed up your claims with real projects, names and numbers rather than describing what you'd generally do.",
    relativeBody: () =>
      "This held up best of the three, though there's room to grow across the board. You did reach for real examples rather than generalities.",
  },
  relevance_strong: {
    title: () => "Answers stayed on target",
    body: () =>
      "You answered the question that was actually asked and tied it back to what the role needs.",
    relativeBody: () =>
      "This held up best of the three, though there's room to grow across the board. You mostly stayed on the question that was asked.",
  },
  structure_weak: {
    title: () => "Answer structure",
    body: () =>
      "Your answers tended to start mid-story or trail off without landing. Try STAR: set the Situation and Task in a sentence, spend most of the answer on your Action, and close with a concrete Result.",
    exemplarLabel: "Hardest to follow",
  },
  specificity_weak: {
    title: () => "Specific detail",
    body: () =>
      "Your answers described what you generally do rather than one particular time you did it. Name the project, your actual role in it, the numbers, and how it ended.",
    exemplarLabel: "Thinnest on detail",
  },
  relevance_weak: {
    title: () => "Answering what was asked",
    body: () =>
      "Your answers drifted from the question. Before you start talking, restate the question to yourself and pick the single example that answers it.",
    exemplarLabel: "Drifted furthest",
  },

  // — Participation —————————————————————————————————————————————
  all_questions_answered: {
    title: () => "Answered every question",
    body: (f) =>
      `You gave a real answer to all ${f.metric?.answered ?? 0} questions — nothing skipped, nothing left on the table.`,
  },
  questions_skipped: {
    title: (f) => {
      const n = f.metric?.skipped ?? 0;
      return `${n} skipped ${n === 1 ? "question" : "questions"}`;
    },
    body: (f) =>
      `You skipped ${f.metric?.skipped ?? 0} of ${f.metric?.answered ?? 0}. A short, honest answer scores better than silence — and in a real interview, so does saying what you'd do if you haven't done it.`,
    exemplarLabel: "First skipped",
  },
  no_scored_answers: {
    title: () => "Nothing to score yet",
    body: (f) => {
      const skipped = f.metric?.skipped ?? 0;
      const unscored = f.metric?.unscored ?? 0;
      if (unscored > 0 && skipped === 0)
        return `${unscored} ${unscored === 1 ? "answer" : "answers"} couldn't be evaluated, so there's no feedback to give for this session. Nothing you did wrong — try another run.`;
      return "Every question in this session was skipped, so there's nothing to give feedback on. Give the next one a go, even roughly.";
    },
  },

  // — Delivery ——————————————————————————————————————————————————
  pace_comfortable: {
    title: () => "Comfortable speaking pace",
    body: (f) =>
      `You averaged ${round(f.metric?.avg_wpm)} words per minute — right in the range that reads as calm and in control.`,
  },
  pace_fast: {
    title: () => "Speaking pace",
    body: (f) =>
      `You averaged ${round(f.metric?.avg_wpm)} words per minute, which is quick. Slowing down reads as more confident and gives your interviewer time to keep up.`,
  },
  pace_slow: {
    title: () => "Speaking pace",
    body: (f) =>
      `You averaged ${round(f.metric?.avg_wpm)} words per minute, on the slower side. A little more momentum sounds more assured.`,
  },
  fillers_low: {
    title: () => "Clean delivery",
    body: (f) => {
      const count = f.metric?.total_filler_count ?? 0;
      const words = f.metric?.total_words ?? 0;
      return count === 0
        ? `Not one filler word across ${words} words — that's rare, and it sounds composed.`
        : `Only ${count} filler ${count === 1 ? "word" : "words"} across ${words} words — barely noticeable.`;
    },
  },
  fillers_high: {
    title: () => "Filler words",
    body: (f) =>
      `${f.metric?.total_filler_count ?? 0} fillers — roughly ${f.metric?.fillers_per_100_words ?? 0} every 100 words. A silent pause while you think sounds far more considered than "um".`,
  },
  long_pause: {
    title: () => "A long pause mid-answer",
    body: (f) =>
      `Your longest silence inside an answer was ${((f.metric?.longest_pause_ms ?? 0) / 1000).toFixed(1)} seconds. Thinking time is fine — saying "let me think about that for a second" out loud is better than dead air.`,
  },
};

/** New-shape findings carry a `code`; legacy rows carry `question_text`. */
function isFinding(item: ReportItem): item is ReportFinding {
  return typeof (item as ReportFinding).code === "string";
}

function FindingRow({ finding, variant }: { finding: ReportFinding; variant: Variant }) {
  // Safe to assert: `renderable()` filtered unknown codes out before this ran.
  const copy = FINDING_COPY[finding.code];

  const strength = variant === "strength";
  const relative = finding.basis === "relative";
  const body = relative && copy.relativeBody ? copy.relativeBody(finding) : copy.body(finding);
  const exemplarLabel = copy.exemplarLabel ?? (strength ? "Best example" : "Weakest");

  return (
    <div className="flex gap-2.5">
      {strength ? (
        <CheckCircle2 size={17} className="mt-1 shrink-0 text-success" />
      ) : (
        <TriangleAlert size={17} className="mt-1 shrink-0 text-warning" />
      )}

      <div className="min-w-0 space-y-1">
        <p className="text-[15px] font-medium text-text-primary">
          {copy.title(finding)}
          {finding.average != null && (
            <span className="ml-2 text-[13px] font-normal text-text-muted">
              {finding.average.toFixed(1)} / 5 across {answers(finding.turns_counted)}
            </span>
          )}
        </p>

        <p className="text-[14px] leading-relaxed text-text-secondary">{body}</p>

        {finding.exemplar && (
          <p className="text-[13px] text-text-muted">
            {exemplarLabel}: Q{finding.exemplar.turn_number}{" "}
            <span className="text-text-secondary">
              &ldquo;{finding.exemplar.question_text}&rdquo;
            </span>
          </p>
        )}
      </div>
    </div>
  );
}

/** A report written before findings existed, rendered exactly as it always was. */
function LegacyRow({
  item,
  variant,
}: {
  item: Exclude<ReportItem, ReportFinding>;
  variant: Variant;
}) {
  return (
    <div className="flex gap-2.5 text-[15px] text-text-primary">
      {variant === "strength" ? (
        <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-success" />
      ) : (
        <TriangleAlert size={17} className="mt-0.5 shrink-0 text-warning" />
      )}
      <span>
        {item.question_text}
        {item.targets_gap && (
          <span className="ml-1.5 text-[13px] text-text-muted">({item.targets_gap})</span>
        )}
      </span>
    </div>
  );
}

type Variant = "strength" | "improvement";

/** How many findings to show. Rendering all of them would bury the top one. */
const MAX_SHOWN = 4;

/**
 * A finding whose code this build knows how to word. Backend codes are stable and
 * versioned separately from the frontend, so a newly added code can arrive before
 * a deploy — those are dropped here rather than in the row, because a row that
 * renders null after the length check leaves a titled card with an empty body.
 */
function renderable(item: ReportItem): boolean {
  return !isFinding(item) || item.code in FINDING_COPY;
}

export function FindingList({
  items,
  variant,
  empty,
}: {
  items: ReportItem[] | null;
  variant: Variant;
  empty: string;
}) {
  const shown = (items ?? []).filter(renderable).slice(0, MAX_SHOWN);

  if (!shown.length) {
    return <p className="text-[15px] text-text-secondary">{empty}</p>;
  }

  return (
    <>
      {shown.map((item, i) =>
        isFinding(item) ? (
          <FindingRow key={`${item.code}-${i}`} finding={item} variant={variant} />
        ) : (
          <LegacyRow key={`legacy-${item.turn_number ?? i}`} item={item} variant={variant} />
        )
      )}
    </>
  );
}
