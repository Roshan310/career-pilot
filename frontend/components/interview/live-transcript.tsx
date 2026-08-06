"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

interface LiveTranscriptProps {
  /** Finalized text. Empty while recording — transcription happens after the turn. */
  text: string;
  /** The tail the recognizer hasn't committed yet, for providers that stream one. */
  interim: string;
  /** 0..1 input level, driving the meter. */
  level: number;
  /** True while the microphone is open. */
  recording: boolean;
  /** True while the recorded answer is being transcribed. */
  transcribing?: boolean;
  placeholder?: string;
}

/** Enough bars to read as a waveform, few enough to stay calm. */
const BAR_COUNT = 28;

/**
 * What the candidate looks at while answering.
 *
 * There is no word-by-word transcript any more: the answer is recorded and
 * transcribed server-side, because the browser API that produced live text
 * doesn't work in every browser (see lib/voice/recorded-provider.ts). A level
 * meter is the honest substitute — it answers the only question that actually
 * matters mid-answer, "is it hearing me", and answers it faster and more
 * truthfully than lagging text ever did.
 */
export function LiveTranscript({
  text,
  interim,
  level,
  recording,
  transcribing = false,
  placeholder,
}: LiveTranscriptProps) {
  const ref = useRef<HTMLDivElement>(null);

  // Keep the newest words in view without stealing focus.
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [text, interim]);

  if (recording || transcribing) {
    return (
      <div
        className="flex min-h-[92px] flex-col items-center justify-center gap-3 rounded-card border border-border bg-card px-5 py-4"
        aria-live="polite"
      >
        <Meter level={transcribing ? 0 : level} active={recording} />
        <p className="text-[13px] text-text-muted">
          {transcribing ? "Writing down your answer…" : "Recording — speak naturally."}
        </p>
      </div>
    );
  }

  const empty = !text && !interim;

  return (
    <div
      ref={ref}
      className="max-h-44 min-h-[92px] overflow-y-auto rounded-card border border-border bg-card px-5 py-4 text-[15px] leading-relaxed"
      aria-live="polite"
    >
      {empty ? (
        <p className="text-text-muted">{placeholder ?? "Your answer will appear here."}</p>
      ) : (
        <p className="text-text-primary">
          {text}
          {interim && <span className="text-text-muted">{text ? " " : ""}{interim}</span>}
        </p>
      )}
    </div>
  );
}

function Meter({ level, active }: { level: number; active: boolean }) {
  return (
    <div className="flex h-10 items-center gap-[3px]" aria-hidden>
      {Array.from({ length: BAR_COUNT }, (_, i) => {
        // Loudest in the middle, tapering out — reads as a voice rather than a
        // progress bar, and keeps the ends from twitching on room noise.
        const distance = Math.abs(i - (BAR_COUNT - 1) / 2) / ((BAR_COUNT - 1) / 2);
        const shape = 1 - distance * 0.75;
        const height = active ? Math.max(3, level * 40 * shape) : 3;
        return (
          <span
            key={i}
            className={cn(
              "w-[3px] rounded-full transition-[height] duration-75",
              active ? "bg-wine" : "bg-border",
            )}
            style={{ height }}
          />
        );
      })}
    </div>
  );
}
