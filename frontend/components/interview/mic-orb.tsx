"use client";

import { motion } from "framer-motion";
import { Keyboard, Loader2, Mic, Volume2 } from "lucide-react";
import type { TurnPhase } from "@/hooks/use-voice-turn";
import { cn } from "@/lib/utils";

interface MicOrbProps {
  phase: TurnPhase;
  submitting: boolean;
  /** The recorded answer is being turned into text server-side. */
  transcribing?: boolean;
  /** 0..1 — how far through the auto-submit countdown we are. */
  countdownFraction: number;
  countdownSeconds: number | null;
  /** Typed mode shows a keyboard glyph instead of a live mic. */
  typed: boolean;
}

const SIZE = 132;
const THICKNESS = 4;

/**
 * The one thing on screen that says what the interview is doing right now.
 * The ring around it fills as the auto-submit countdown runs, so "it's about to
 * take my answer" is visible before it happens rather than after.
 */
export function MicOrb({
  phase,
  submitting,
  transcribing = false,
  countdownFraction,
  countdownSeconds,
  typed,
}: MicOrbProps) {
  const listening = phase === "listening" || phase === "armed";
  const radius = (SIZE - THICKNESS) / 2;
  const circumference = 2 * Math.PI * radius;

  const label = transcribing
    ? "Writing it down…"
    : submitting
    ? "Sending…"
    : phase === "speaking"
      ? "Listen"
      : phase === "waiting"
        ? "Get ready…"
        : phase === "armed"
          ? `Submitting in ${countdownSeconds ?? 0}…`
          : listening
            ? typed
              ? "Type your answer"
              : "Listening"
            : "Ready";

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        {/* Breathing halo while the mic is open. */}
        {listening && !typed && (
          <motion.span
            className="absolute inset-0 rounded-full bg-wine/10"
            animate={{ scale: [1, 1.12, 1], opacity: [0.5, 0.15, 0.5] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          />
        )}

        <svg width={SIZE} height={SIZE} className="absolute inset-0 -rotate-90">
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={radius}
            fill="none"
            stroke="var(--color-divider)"
            strokeWidth={THICKNESS}
          />
          {phase === "armed" && (
            <circle
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={radius}
              fill="none"
              stroke="#B4232D"
              strokeWidth={THICKNESS}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - Math.min(1, Math.max(0, countdownFraction)))}
            />
          )}
        </svg>

        <div
          className={cn(
            "absolute inset-[18px] flex items-center justify-center rounded-full transition-colors duration-300",
            submitting || phase === "speaking"
              ? "bg-hover text-text-secondary"
              : listening
                ? "bg-wine text-white shadow-card-hover"
                : "bg-hover text-text-muted",
          )}
        >
          {submitting ? (
            <Loader2 size={34} className="animate-spin" />
          ) : phase === "speaking" ? (
            <Volume2 size={34} />
          ) : typed ? (
            <Keyboard size={34} />
          ) : (
            <Mic size={34} />
          )}
        </div>
      </div>

      <p
        className={cn(
          "text-[14px] font-medium",
          phase === "armed" ? "text-wine-fg" : "text-text-secondary",
        )}
        aria-live="polite"
      >
        {label}
      </p>
    </div>
  );
}
