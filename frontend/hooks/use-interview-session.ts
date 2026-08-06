"use client";

// Session-level orchestration: restore, ask, submit, advance, wrap up, finish.
// It owns the API calls and the hard-cap clock; `useVoiceTurn` owns the mic.
// Neither knows the other's internals.

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";
import {
  abandonInterview,
  completeInterview,
  getInterview,
  submitTurn,
  transcribeAnswer,
} from "@/lib/api/interviews";
import type {
  CurrentQuestion,
  EvaluationResult,
  InterviewSession,
  SessionProgress,
  TurnDetail,
} from "@/lib/types";
import {
  createVoiceProvider,
  isRecordingSupported,
  type VoiceError,
  type VoiceMode,
  type VoiceProvider,
} from "@/lib/voice";
import { useVoiceTurn, type CapturedAnswer } from "./use-voice-turn";

export type SessionPhase =
  | "loading"
  | "error"
  | "ready" // loaded, waiting for the click that lets us play audio and open the mic
  | "active" // a question is being asked / answered
  | "transcribing"
  | "submitting"
  | "submit_failed"
  | "wrapping_up"
  | "completing"
  | "finished";

interface UseInterviewSessionOptions {
  sessionId: string;
  /** Called once the report exists and the screen should hand off. */
  onCompleted(sessionId: string): void;
  onAbandoned(): void;
}

export function useInterviewSession({ sessionId, onCompleted, onAbandoned }: UseInterviewSessionOptions) {
  const queryClient = useQueryClient();

  const [phase, setPhase] = useState<SessionPhase>("loading");
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [question, setQuestion] = useState<CurrentQuestion | null>(null);
  const [progress, setProgress] = useState<SessionProgress | null>(null);
  const [answered, setAnswered] = useState<TurnDetail[]>([]);
  const [lastEvaluation, setLastEvaluation] = useState<EvaluationResult | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  /** Set when a question is on screen but hasn't been voiced yet. */
  const [needsAsk, setNeedsAsk] = useState(false);
  /** The candidate has clicked Begin — the user gesture audio and mic both need. */
  const [started, setStarted] = useState(false);

  const [voiceMode, setVoiceMode] = useState<VoiceMode>("voice");
  const [muted, setMutedState] = useState(false);
  const [provider, setProvider] = useState<VoiceProvider | null>(null);

  const phaseRef = useRef<SessionPhase>("loading");
  const questionRef = useRef<CurrentQuestion | null>(null);
  const hydrateRef = useRef<((data: InterviewSession) => void) | null>(null);
  const captureRef = useRef<((skipped?: boolean) => CapturedAnswer) | null>(null);
  const askRef = useRef<((text: string, turnNumber: number) => Promise<void>) | null>(null);
  const resetTurnRef = useRef<(() => void) | null>(null);
  const failedAnswerRef = useRef<CapturedAnswer | null>(null);
  const failedRecordingRef = useRef<Blob | null>(null);
  const providerRef = useRef<VoiceProvider | null>(null);
  const hardCapFiredRef = useRef(false);

  phaseRef.current = phase;
  questionRef.current = question;
  providerRef.current = provider;

  const startedRef = useRef(false);
  startedRef.current = started;

  /** The Begin click. Everything audio-related hangs off this one gesture. */
  const start = useCallback(() => {
    setStarted(true);
    setPhase((current) => (current === "ready" ? "active" : current));
  }, []);

  // ---- provider lifecycle ----
  // Recreated only when the mode changes; muting goes through setMuted so
  // toggling it mid-answer doesn't drop the microphone.
  const mutedRef = useRef(false);
  mutedRef.current = muted;

  // Whether the *browser* can record at all — deliberately not `provider.canListen`,
  // which is false whenever the typed provider is active and would strip the way
  // back to the mic. Detected on the client only (there's no SSR-safe answer).
  const [speechSupported, setSpeechSupported] = useState(false);
  useEffect(() => setSpeechSupported(isRecordingSupported()), []);

  useEffect(() => {
    const p = createVoiceProvider({ mode: voiceMode, sessionId, muted: mutedRef.current });
    setProvider(p);
    return () => p.dispose();
  }, [voiceMode, sessionId]);

  const setMuted = useCallback(
    (next: boolean) => {
      setMutedState(next);
      provider?.setMuted(next);
    },
    [provider],
  );

  const applyProgress = useCallback((next: SessionProgress | null) => {
    setProgress(next);
    if (next) setSecondsRemaining(Math.max(0, Math.round(next.seconds_remaining)));
  }, []);

  // ---- submit ----
  const submitAnswer = useCallback(
    async (answer: CapturedAnswer, recording?: Blob | null) => {
      const current = questionRef.current;
      if (!current) return;

      setNotice(null);

      // A recorded answer has audio but no words yet. Transcribe first, then
      // submit — two calls, because a transcription failure must not destroy an
      // answer the candidate already gave. The envelope below is complete before
      // anything can go wrong with sending it, which is what makes the retry
      // path on `submit_failed` able to work at all.
      let transcript = answer.transcript;
      let segments = answer.segments;

      if (recording && !answer.skipped) {
        setPhase("transcribing");
        try {
          transcript = await transcribeAnswer(sessionId, recording);
        } catch (err) {
          // Hold on to the audio: retrying has to transcribe again, and the
          // recording can only be taken from the provider once.
          failedAnswerRef.current = answer;
          failedRecordingRef.current = recording;
          setError(
            err instanceof ApiError ? err.message : "Couldn't transcribe that answer.",
          );
          setPhase("submit_failed");
          return;
        }

        // Heard speaking, got no words back. Submitting now would send a blank
        // transcript, which the server correctly reads as a skipped question —
        // so the interview would move on and the answer would be gone without
        // anyone saying so. The segments are the evidence: VAD only produces
        // bursts when it actually detected voice.
        if (!transcript.trim() && segments?.length) {
          failedAnswerRef.current = answer;
          failedRecordingRef.current = recording;
          setError("We couldn't make out any words in that recording.");
          setPhase("submit_failed");
          return;
        }
        // The bursts carry timings but no text — the server transcribes the whole
        // answer at once, not per utterance. Attaching it to the first burst
        // keeps the segment list valid: speech_metrics reads word counts from
        // `answer_transcript` and pauses from the timings, never text per segment.
        if (segments?.length) {
          segments = segments.map((seg, i) => (i === 0 ? { ...seg, text: transcript } : seg));
        }
      }

      setPhase("submitting");
      try {
        const result = await submitTurn(sessionId, {
          question_number: current.turn_number,
          answer_transcript: transcript,
          duration: answer.durationSeconds,
          source: answer.source,
          segments,
          skipped: answer.skipped,
        });

        failedAnswerRef.current = null;
        setLastEvaluation(result.evaluation);
        applyProgress(result.progress);
        setAnswered((prev) => [
          ...prev,
          {
            turn_number: current.turn_number,
            question_text: current.question_text,
            question_type: current.question_type,
            targets_gap: current.targets_gap,
            answer_transcript: answer.skipped ? "" : transcript,
            answer_duration_seconds: answer.durationSeconds,
            score: result.evaluation,
            speech_metrics: result.speech_metrics,
            created_at: new Date().toISOString(),
          },
        ]);

        if (result.next_question) {
          setQuestion(result.next_question);
          questionRef.current = result.next_question;
          setPhase("active");
          setNeedsAsk(true);
        } else {
          setQuestion(null);
          setPhase("wrapping_up");
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          // The server no longer accepts an answer for this turn (double submit,
          // or it already moved on). Server state wins — re-read it.
          try {
            hydrateRef.current?.(await getInterview(sessionId));
            return;
          } catch {
            /* fall through to the retry path below */
          }
        }
        // Never silently lose an answer the user just gave. Stored with the
        // transcript already resolved: the recording has been handed over and
        // can't be taken twice, so a retry must not need to transcribe again
        // (and shouldn't pay for it twice either).
        failedAnswerRef.current = { ...answer, transcript, segments };
        failedRecordingRef.current = null; // already transcribed — don't pay twice
        setError(err instanceof ApiError ? err.message : "Couldn't send that answer.");
        setPhase("submit_failed");
      }
    },
    [sessionId, applyProgress],
  );

  const retrySubmit = useCallback(() => {
    const pending = failedAnswerRef.current;
    if (!pending) return;
    setError(null);
    void submitAnswer(pending, failedRecordingRef.current);
  }, [submitAnswer]);

  /**
   * Give up on the recording and type this answer instead. The turn is still
   * open on the server — nothing was submitted — so this returns to answering
   * rather than starting anything over. Needed because a retry can keep failing:
   * audio the model can't make out won't become clearer on a second attempt, and
   * without this the candidate is stuck on that question.
   */
  const switchToTyping = useCallback(() => {
    failedAnswerRef.current = null;
    failedRecordingRef.current = null;
    setError(null);
    setVoiceMode("typed");
    setPhase("active");
  }, []);

  /** Stop the mic, collect the recording, and send the turn. */
  const captureAndSubmit = useCallback(
    async (skipped: boolean) => {
      const answer = captureRef.current?.(skipped);
      if (!answer) return;
      // Must come after capture() — that's what stops the recorder, and the blob
      // isn't complete until it does.
      const recording = skipped ? null : await providerRef.current?.takeRecording();
      await submitAnswer(answer, recording);
    },
    [submitAnswer],
  );

  // ---- the mic ----
  const turn = useVoiceTurn({
    provider,
    onAutoSubmit: () => void captureAndSubmit(false),
    onError: (voiceError: VoiceError) => {
      if (voiceError.kind === "permission" || voiceError.kind === "unsupported") {
        // §7.3's graceful degradation: fall back to typing rather than dying.
        setVoiceMode("typed");
        setNotice(`${voiceError.message} Switched to typing.`);
      } else {
        setNotice(voiceError.message);
      }
    },
  });

  captureRef.current = turn.capture;
  askRef.current = turn.ask;
  resetTurnRef.current = turn.reset;

  // Voicing a question waits for the provider to exist, so a question set
  // before the provider mounts (first load) still gets asked.
  //
  // It also waits for `started`. Browsers refuse to play audio or open a
  // microphone without a user gesture, so the first question cannot be asked
  // straight out of hydrate() — it has to follow the Begin click, or the audio
  // is blocked and the mic never opens.
  useEffect(() => {
    if (!needsAsk || !started || !provider || !question) return;
    setNeedsAsk(false);
    void askRef.current?.(question.question_text, question.turn_number);
  }, [needsAsk, started, provider, question]);

  // ---- load / restore ----
  const hydrate = useCallback(
    (data: InterviewSession) => {
      setSession(data);
      applyProgress(data.progress);
      setAnswered(data.turns.filter((t) => t.answer_transcript !== null));

      if (data.status === "completed") {
        setPhase("finished");
        onCompleted(data.id);
        return;
      }
      if (data.status === "abandoned") {
        setPhase("finished");
        onAbandoned();
        return;
      }
      if (data.status === "wrapping_up" || !data.current_question) {
        setQuestion(null);
        setPhase("wrapping_up");
        return;
      }

      setQuestion(data.current_question);
      questionRef.current = data.current_question;
      // "ready" until Begin is clicked. On a mid-session reload this shows again
      // — deliberately: the reloaded page has no user gesture either, and the
      // alternative is a question that silently never plays.
      setPhase(startedRef.current ? "active" : "ready");
      setNeedsAsk(true);
    },
    [applyProgress, onCompleted, onAbandoned],
  );

  hydrateRef.current = hydrate;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getInterview(sessionId);
        if (!cancelled) hydrateRef.current?.(data);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Couldn't load this interview.");
        setPhase("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // ---- hard-cap clock ----
  // Ticks locally but is re-synced from `progress.seconds_remaining` after every
  // turn, so it can't drift from the cap the server actually enforces.
  useEffect(() => {
    if (phase !== "active" && phase !== "submitting") return;
    const id = setInterval(() => {
      setSecondsRemaining((s) => (s === null ? null : Math.max(0, s - 1)));
    }, 1000);
    return () => clearInterval(id);
  }, [phase]);

  useEffect(() => {
    if (secondsRemaining !== 0 || hardCapFiredRef.current) return;
    if (phaseRef.current !== "active") return;
    hardCapFiredRef.current = true;
    // Time's up: send whatever was captured rather than discarding it. The
    // server's own cap moves the session to wrapping_up on this same call.
    void captureAndSubmit(false);
  }, [secondsRemaining, captureAndSubmit]);

  // ---- explicit user actions ----
  const finishAnswer = useCallback(() => void captureAndSubmit(false), [captureAndSubmit]);
  const skipQuestion = useCallback(() => void captureAndSubmit(true), [captureAndSubmit]);

  const complete = useCallback(async () => {
    setPhase("completing");
    try {
      await completeInterview(sessionId);
      queryClient.invalidateQueries({ queryKey: ["interviews"] });
      queryClient.invalidateQueries({ queryKey: ["interview-report", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["interview", sessionId] });
      setPhase("finished");
      onCompleted(sessionId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't generate your report.");
      setPhase("wrapping_up");
    }
  }, [sessionId, queryClient, onCompleted]);

  const abandon = useCallback(async () => {
    resetTurnRef.current?.();
    try {
      await abandonInterview(sessionId);
    } catch {
      /* leaving anyway — the session is unusable to the user either way */
    }
    queryClient.invalidateQueries({ queryKey: ["interviews"] });
    setPhase("finished");
    onAbandoned();
  }, [sessionId, queryClient, onAbandoned]);

  return {
    phase,
    session,
    question,
    progress,
    answered,
    lastEvaluation,
    secondsRemaining,
    error,
    notice,
    dismissNotice: useCallback(() => setNotice(null), []),

    started,
    start,

    voiceMode,
    setVoiceMode,
    /**
     * What the user is *actually* answering with. Not the same as `voiceMode`:
     * an unsupported browser gets the typed provider while the requested mode is
     * still "voice", and the UI must follow the provider or it renders a mic
     * that can't hear and no textarea to type into.
     */
    typing: (provider?.source ?? "typed") === "typed",
    muted,
    setMuted,
    /** The browser supports speech recognition — so offering the mic is meaningful. */
    speechSupported,

    turn,
    finishAnswer,
    skipQuestion,
    retrySubmit,
    switchToTyping,
    complete,
    abandon,
  };
}
