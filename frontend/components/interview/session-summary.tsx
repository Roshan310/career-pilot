"use client";

import { CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface SessionSummaryProps {
  answeredCount: number;
  completing: boolean;
  error: string | null;
  onComplete(): void;
  onDiscard(): void;
}

/**
 * The `wrapping_up` screen. The session is already at that status server-side,
 * so this is the only remaining action — generating the report is a separate
 * call the user opts into.
 */
export function SessionSummary({ answeredCount, completing, error, onComplete, onDiscard }: SessionSummaryProps) {
  return (
    <Card className="p-10 text-center">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-success-bg">
        <CheckCircle2 size={30} className="text-success" />
      </div>

      <h2 className="mt-6 text-h3 text-text-primary">That&apos;s a wrap</h2>
      <p className="mx-auto mt-2 max-w-md text-[15px] leading-relaxed text-text-secondary">
        You answered {answeredCount} {answeredCount === 1 ? "question" : "questions"}. Generating your
        feedback scores each answer and checks which of your resume gaps you actually closed.
      </p>

      {error && <p className="mt-4 text-[14px] text-error">{error}</p>}

      <div className="mt-7 flex justify-center gap-3">
        <Button onClick={onComplete} disabled={completing}>
          {completing ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
          {completing ? "Building your report…" : "Get my feedback"}
        </Button>
        <Button variant="secondary" onClick={onDiscard} disabled={completing}>
          Discard this session
        </Button>
      </div>
    </Card>
  );
}
