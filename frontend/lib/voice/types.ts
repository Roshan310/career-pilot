// The voice-provider seam (SPECS.md §7.6), widened to match the backend one.
//
// §7.6 sketches three methods — speak / listen / stopListening. That is not
// quite enough: the API's answer envelope carries `source` and `segments`, and
// if the interview screen derived those itself, swapping the provider would
// leak upward. So the provider owns both. A future streaming provider
// (Deepgram / Gemini Live) is one more file implementing this interface; the
// hooks and pages above it don't move.
//
// Nothing outside this directory may touch a browser media or speech API —
// `MediaRecorder`, `getUserMedia`, `AudioContext`, `speechSynthesis`. That
// boundary is what let the whole voice layer move from the browser to the server
// without a single hook or page changing.

import type { AnswerSource, TranscriptSegment } from "@/lib/types";

export interface TranscriptUpdate {
  /** Everything finalized so far. Empty for providers that transcribe after the fact. */
  text: string;
  /** The not-yet-finalized tail, if the provider streams one. */
  interim: string;
  /** True when this update finalized a chunk (i.e. `text` just grew). */
  isFinal: boolean;
  /** Timed chunks, ms relative to the `listen()` call — the API's shape exactly. */
  segments: TranscriptSegment[];
  /** 0..1 input level, for a meter. 0 from providers with no audio access. */
  level: number;
  /**
   * Whether the candidate is speaking right now. This is what drives the
   * silence countdown, deliberately in place of "did the transcript grow":
   * a provider that transcribes after the answer has no growing transcript to
   * watch, and acoustic silence is a truer signal anyway — transcript growth
   * lags speech by however long recognition takes.
   */
  speaking: boolean;
}

export interface ListenHandlers {
  onTranscript(update: TranscriptUpdate): void;
  onError(error: VoiceError): void;
}

export type VoiceErrorKind = "permission" | "unsupported" | "no-speech" | "other";

export class VoiceError extends Error {
  kind: VoiceErrorKind;
  constructor(kind: VoiceErrorKind, message: string) {
    super(message);
    this.name = "VoiceError";
    this.kind = kind;
  }
}

export interface VoiceProvider {
  /** Tagged onto every answer submitted while this provider is active. */
  readonly source: AnswerSource;
  readonly canListen: boolean;
  readonly canSpeak: boolean;

  /**
   * Voice the question. Resolves when it has finished being spoken (immediately
   * if muted or unavailable). `turnNumber` identifies which question this is, so
   * a provider that fetches server-generated audio knows what to ask for.
   */
  speak(text: string, turnNumber: number): Promise<void>;
  cancelSpeech(): void;
  /** Toggling output must not tear down the microphone, so it's a method, not a constructor option. */
  setMuted(muted: boolean): void;

  listen(handlers: ListenHandlers): void;
  stopListening(): void;

  /**
   * The audio captured since `listen()`, for providers that record and have it
   * transcribed elsewhere. Null when the provider produced text directly (or
   * produced nothing). Callable once per answer — it hands over the recording.
   */
  takeRecording(): Promise<Blob | null>;

  /** Release the mic and cancel any in-flight speech. Safe to call twice. */
  dispose(): void;
}
