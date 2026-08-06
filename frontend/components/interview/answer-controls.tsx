"use client";

import { Check, Keyboard, Mic, RotateCcw, SkipForward } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface AnswerControlsProps {
  typed: boolean;
  /** Only offered when the browser can record audio at all. */
  canUseVoice: boolean;
  armed: boolean;
  submitting: boolean;
  hasAnswer: boolean;
  typedAnswer: string;
  onTypedAnswerChange(value: string): void;
  onKeepGoing(): void;
  onDone(): void;
  onSkip(): void;
  onToggleTyped(): void;
}

export function AnswerControls({
  typed,
  canUseVoice,
  armed,
  submitting,
  hasAnswer,
  typedAnswer,
  onTypedAnswerChange,
  onKeepGoing,
  onDone,
  onSkip,
  onToggleTyped,
}: AnswerControlsProps) {
  return (
    <div className="space-y-4">
      {typed && (
        <Textarea
          rows={5}
          autoFocus
          value={typedAnswer}
          disabled={submitting}
          onChange={(e) => onTypedAnswerChange(e.target.value)}
          placeholder="Type your answer…"
        />
      )}

      <div className="flex flex-wrap items-center justify-center gap-3">
        {armed && (
          <Button variant="secondary" onClick={onKeepGoing} disabled={submitting}>
            <RotateCcw size={17} /> Keep going
          </Button>
        )}

        <Button onClick={onDone} disabled={submitting || !hasAnswer}>
          <Check size={17} /> Done answering
        </Button>

        <Button variant="secondary" onClick={onSkip} disabled={submitting}>
          <SkipForward size={17} /> Skip
        </Button>

        {canUseVoice && (
          <Button variant="ghost" onClick={onToggleTyped} disabled={submitting}>
            {typed ? (
              <>
                <Mic size={17} /> Use the mic
              </>
            ) : (
              <>
                <Keyboard size={17} /> Type instead
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
