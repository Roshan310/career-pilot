"use client";

// Everything that happens between "here is the question" and "here is the
// answer envelope" — for ONE turn. It talks to a VoiceProvider and to timers,
// never to the API and never to a browser media API directly (SPECS.md §7.6).
//
// The answer-end rule is a deliberate softening of §7.2's bare 2s auto-submit:
// silence arms a *visible, cancellable* countdown instead of ending the turn
// outright, because a 2s pause mid-sentence is normal speech, not a finished
// answer.

import { useCallback, useEffect, useRef, useState } from "react";
import type { AnswerSource, TranscriptSegment } from "@/lib/types";
import type { VoiceError, VoiceProvider } from "@/lib/voice";

/** A beat after the question is voiced, before the mic opens (§7.2). */
const GRACE_MS = 2000;
/** Silence this long arms the countdown. */
const SILENCE_MS = 3000;
/** How long the armed countdown runs before submitting. */
const COUNTDOWN_MS = 3000;
/** Nothing heard at all for this long → one gentle retry prompt (§7.2). */
const NO_SPEECH_PROMPT_MS = 8000;
/** Still nothing this long after the prompt → treat it as a skipped question. */
const NO_SPEECH_GIVE_UP_MS = 12000;

const RETRY_PROMPT = "Take your time — go ahead whenever you're ready.";

export type TurnPhase =
  | "idle"
  | "speaking" // the question is being read aloud
  | "waiting" // grace beat before the mic opens
  | "listening"
  | "armed" // countdown to auto-submit is running
  | "captured";

export interface CapturedAnswer {
  transcript: string;
  durationSeconds: number;
  segments: TranscriptSegment[] | null;
  source: AnswerSource;
  skipped: boolean;
}

interface UseVoiceTurnOptions {
  provider: VoiceProvider | null;
  /**
   * The turn wants to end: the countdown expired, or the no-speech window ran
   * out (`skipped`). Signals intent rather than handing over an answer, because
   * the caller has to collect the recording too, and capturing the envelope in
   * two places is how the two halves drift apart.
   */
  onAutoSubmit(skipped: boolean): void;
  onError?(error: VoiceError): void;
}

export function useVoiceTurn({ provider, onAutoSubmit, onError }: UseVoiceTurnOptions) {
  const [phase, setPhase] = useState<TurnPhase>("idle");
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [typedAnswer, setTypedAnswer] = useState("");
  const [countdownMs, setCountdownMs] = useState<number | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [level, setLevel] = useState(0);
  /**
   * Whether any speech has been heard this turn. A recording provider has no
   * transcript to check until the server returns one, so "is there an answer to
   * send" has to be answered acoustically.
   */
  const [heardSpeech, setHeardSpeech] = useState(false);

  // Everything the tick loop reads lives in refs so the interval can stay
  // mounted for the life of the turn without restarting on every transcript
  // update (which would reset the silence window on every syllable).
  const segmentsRef = useRef<TranscriptSegment[]>([]);
  const transcriptRef = useRef("");
  const typedRef = useRef("");
  const listenStartRef = useRef<number | null>(null);
  const lastSpeechAtRef = useRef(0);
  const heardAnythingRef = useRef(false);
  const armedAtRef = useRef<number | null>(null);
  const promptedAtRef = useRef<number | null>(null);
  const phaseRef = useRef<TurnPhase>("idle");
  const callbacksRef = useRef({ onAutoSubmit, onError });
  const graceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  callbacksRef.current = { onAutoSubmit, onError };
  typedRef.current = typedAnswer;

  const setPhaseBoth = useCallback((next: TurnPhase) => {
    phaseRef.current = next;
    setPhase(next);
  }, []);

  const buildAnswer = useCallback(
    (skipped: boolean): CapturedAnswer => {
      const spoken = transcriptRef.current.trim();
      const typed = typedRef.current.trim();
      const isTyped = provider?.source === "typed";
      const startedAt = listenStartRef.current;
      const durationSeconds = startedAt ? (performance.now() - startedAt) / 1000 : 0;

      return {
        // Empty for a recording provider: the words don't exist yet. The session
        // hook transcribes the audio and fills this in before submitting, which
        // is why transcription is its own step rather than part of submitTurn.
        // Falling back to `spoken` matters when the user switches to the
        // keyboard mid-answer: what was already transcribed is theirs to keep.
        transcript: skipped ? "" : isTyped ? typed || spoken : spoken,
        durationSeconds: Math.max(0, durationSeconds),
        // Typed answers have no timing data — send null rather than invent
        // segments, so the server reports longest_pause_ms as null.
        segments: isTyped || !segmentsRef.current.length ? null : segmentsRef.current,
        source: provider?.source ?? "typed",
        skipped,
      };
    },
    [provider],
  );

  const stopMic = useCallback(() => {
    provider?.stopListening();
    if (graceTimerRef.current) {
      clearTimeout(graceTimerRef.current);
      graceTimerRef.current = null;
    }
  }, [provider]);

  /** Ends the turn and hands the envelope back. Used by the timers and by the buttons. */
  const capture = useCallback(
    (skipped = false): CapturedAnswer => {
      const answer = buildAnswer(skipped);
      stopMic();
      setPhaseBoth("captured");
      setCountdownMs(null);
      armedAtRef.current = null;
      return answer;
    },
    [buildAnswer, setPhaseBoth, stopMic],
  );

  /** Reset for a new question, then voice it and open the mic. */
  const ask = useCallback(
    async (questionText: string, turnNumber: number) => {
      if (!provider) return;

      transcriptRef.current = "";
      segmentsRef.current = [];
      heardAnythingRef.current = false;
      armedAtRef.current = null;
      promptedAtRef.current = null;
      listenStartRef.current = null;
      setTranscript("");
      setInterim("");
      setTypedAnswer("");
      setCountdownMs(null);
      setHint(null);
      setLevel(0);
      setHeardSpeech(false);

      setPhaseBoth("speaking");
      await provider.speak(questionText, turnNumber);
      if (phaseRef.current !== "speaking") return; // aborted while speaking

      setPhaseBoth("waiting");
      graceTimerRef.current = setTimeout(() => {
        if (phaseRef.current !== "waiting") return;
        listenStartRef.current = performance.now();
        lastSpeechAtRef.current = performance.now();
        // The mic is attached by the effect below, not here — so that swapping
        // providers mid-answer (mic ⇄ keyboard) reattaches correctly.
        setPhaseBoth("listening");
      }, GRACE_MS);
    },
    [provider, setPhaseBoth],
  );

  // The mic is open exactly while the turn is taking an answer. Keyed on a
  // boolean rather than `phase` so arming the countdown doesn't restart it.
  const micShouldBeOpen = phase === "listening" || phase === "armed";
  useEffect(() => {
    if (!micShouldBeOpen || !provider?.canListen) return;

    provider.listen({
      onTranscript: (update) => {
        // `text` stays empty for a recording provider — the transcript arrives
        // from the server after the turn. Segments and voice activity are what
        // this hook actually runs on.
        const grew = update.text !== "" && update.text !== transcriptRef.current;
        transcriptRef.current = update.text || transcriptRef.current;
        segmentsRef.current = update.segments;
        if (update.text) setTranscript(update.text);
        setInterim(update.interim);
        setLevel(update.level);

        if (grew || update.interim || update.speaking) {
          lastSpeechAtRef.current = performance.now();
          heardAnythingRef.current = true;
          setHeardSpeech(true);
          // Speaking again cancels a pending auto-submit — the "Keep going"
          // behaviour, triggered by the voice itself.
          if (armedAtRef.current !== null) {
            armedAtRef.current = null;
            setCountdownMs(null);
            setPhaseBoth("listening");
          }
          setHint(null);
        }
      },
      onError: (error) => callbacksRef.current.onError?.(error),
    });

    return () => provider.stopListening();
  }, [micShouldBeOpen, provider, setPhaseBoth]);

  /** User spoke again / clicked "Keep going" — disarm and keep listening. */
  const keepGoing = useCallback(() => {
    armedAtRef.current = null;
    lastSpeechAtRef.current = performance.now();
    setCountdownMs(null);
    setHint(null);
    if (phaseRef.current === "armed") setPhaseBoth("listening");
  }, [setPhaseBoth]);

  const reset = useCallback(() => {
    stopMic();
    provider?.cancelSpeech();
    setPhaseBoth("idle");
    setCountdownMs(null);
    setHint(null);
  }, [provider, setPhaseBoth, stopMic]);

  // ---- the single tick loop ----
  useEffect(() => {
    if (phase !== "listening" && phase !== "armed") return;

    const id = setInterval(() => {
      const now = performance.now();
      const startedAt = listenStartRef.current;
      if (startedAt === null) return;

      // Typed answers are ended by the button, never by a timer.
      if (!provider?.canListen) return;

      if (!heardAnythingRef.current) {
        const silentFor = now - startedAt;
        if (promptedAtRef.current === null) {
          if (silentFor > NO_SPEECH_PROMPT_MS) {
            promptedAtRef.current = now;
            // Shown, not spoken. Question audio is generated per turn and cached
            // by turn number; this nudge belongs to no turn, and adding an
            // endpoint that voices arbitrary text would let anyone bill the
            // account for anything. On screen is enough for a one-line prompt.
            setHint(RETRY_PROMPT);
          }
        } else if (now - promptedAtRef.current > NO_SPEECH_GIVE_UP_MS) {
          // §7.2: nothing after the retry prompt → skipped question. The
          // backend takes this without spending an evaluation call.
          callbacksRef.current.onAutoSubmit(true);
        }
        return;
      }

      if (armedAtRef.current === null) {
        if (now - lastSpeechAtRef.current > SILENCE_MS) {
          armedAtRef.current = now;
          setPhaseBoth("armed");
          setCountdownMs(COUNTDOWN_MS);
        }
        return;
      }

      const left = COUNTDOWN_MS - (now - armedAtRef.current);
      if (left <= 0) {
        callbacksRef.current.onAutoSubmit(false);
      } else {
        setCountdownMs(left);
      }
    }, 100);

    return () => clearInterval(id);
  }, [phase, provider, capture, setPhaseBoth]);

  // Switching to the keyboard mid-answer carries the spoken text into the
  // textarea so it can be edited rather than retyped from scratch.
  const isTyped = provider?.source === "typed";
  useEffect(() => {
    if (isTyped && !typedRef.current && transcriptRef.current) {
      setTypedAnswer(transcriptRef.current);
    }
  }, [isTyped]);

  // Release the mic if the screen goes away mid-answer.
  useEffect(() => {
    return () => {
      if (graceTimerRef.current) clearTimeout(graceTimerRef.current);
    };
  }, []);

  return {
    phase,
    transcript,
    interim,
    typedAnswer,
    setTypedAnswer,
    countdownMs,
    countdownFraction: countdownMs === null ? 0 : 1 - countdownMs / COUNTDOWN_MS,
    hint,
    /** 0..1 mic input level, for the meter. */
    level,
    /** Anything to submit? Drives the enabled state of "Done answering". */
    hasAnswer: isTyped
      ? typedAnswer.trim().length > 0 || transcript.trim().length > 0
      : heardSpeech || transcript.trim().length > 0,
    ask,
    capture,
    keepGoing,
    reset,
  };
}
