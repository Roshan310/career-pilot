// Records the answer and lets the server transcribe it.
//
// This replaced the Web Speech API implementation, which could not be made to
// work: Brave ships `webkitSpeechRecognition` as a stub that returns a `network`
// error instead of results, and feature-detecting the constructor tells you
// nothing about whether it does anything. The old provider fed that error into
// an unconditional auto-restart, so the UI sat on "Listening" forever while
// recording precisely nothing.
//
// MediaRecorder and the Web Audio API are, by contrast, uniformly implemented.
// The cost is no live word-by-word transcript; the gain is that the interview
// behaves the same in every browser, and that pauses are now *measured* from the
// audio rather than inferred from how far transcription lagged behind speech.

import type { TranscriptSegment } from "@/lib/types";
import type { Speaker } from "./speaker";
import { VoiceError, type ListenHandlers, type VoiceProvider } from "./types";

/** How often the level is sampled. Fast enough for a responsive meter, cheap enough to ignore. */
const TICK_MS = 50;
/** Absolute floor — below this it's a quiet room, whatever the noise estimate says. */
const MIN_SPEECH_RMS = 0.012;
/** Speech has to clear the ambient noise estimate by this much to count. */
const NOISE_MULTIPLIER = 2.5;
/** Sustained sound before a burst opens. Rejects keyboard clicks and door thumps. */
const ATTACK_MS = 120;
/** Silence tolerated *inside* one burst — the gap between words, not between thoughts. */
const HANGOVER_MS = 400;

function isRecordingSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof MediaRecorder !== "undefined" &&
    Boolean(navigator?.mediaDevices?.getUserMedia)
  );
}

/** The best container this browser will actually give us. Safari differs from the rest. */
function pickMimeType(): string | undefined {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return candidates.find((type) => MediaRecorder.isTypeSupported?.(type));
}

export { isRecordingSupported };

export class RecordedProvider implements VoiceProvider {
  readonly source = "server_stt" as const;

  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private recording: Promise<Blob | null> | null = null;

  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  // Explicitly over an ArrayBuffer: getFloatTimeDomainData rejects a
  // Float32Array that might be backed by a SharedArrayBuffer.
  private buffer: Float32Array<ArrayBuffer> | null = null;
  private ticker: ReturnType<typeof setInterval> | null = null;

  private handlers: ListenHandlers | null = null;
  private startedAt = 0;
  private noiseFloor = MIN_SPEECH_RMS;

  private segments: TranscriptSegment[] = [];
  private burstStartedAt: number | null = null;
  private aboveSince: number | null = null;
  private lastLoudAt = 0;

  constructor(private speaker: Speaker) {}

  get canListen(): boolean {
    return isRecordingSupported();
  }

  get canSpeak(): boolean {
    return this.speaker.canSpeak;
  }

  speak(text: string, turnNumber: number): Promise<void> {
    return this.speaker.speak(text, turnNumber);
  }

  cancelSpeech(): void {
    this.speaker.cancel();
  }

  setMuted(muted: boolean): void {
    this.speaker.setMuted(muted);
  }

  listen(handlers: ListenHandlers): void {
    this.handlers = handlers;
    this.reset();
    void this.start(handlers);
  }

  private async start(handlers: ListenHandlers) {
    if (!isRecordingSupported()) {
      handlers.onError(new VoiceError("unsupported", "This browser can't record audio."));
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        // Browser-side cleanup before the audio ever reaches us. Cheaper and
        // better than anything we'd do to the samples ourselves.
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (err) {
      const name = (err as DOMException)?.name;
      if (name === "NotAllowedError" || name === "SecurityError") {
        handlers.onError(
          new VoiceError("permission", "Microphone access was blocked. Allow it, or type your answer."),
        );
      } else if (name === "NotFoundError") {
        handlers.onError(new VoiceError("other", "No microphone was found."));
      } else {
        handlers.onError(new VoiceError("other", "Couldn't open the microphone."));
      }
      return;
    }

    // listen() may have been torn down while the permission prompt was up.
    if (this.handlers !== handlers) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }

    this.stream = stream;
    this.startedAt = performance.now();
    this.lastLoudAt = this.startedAt;
    this.startRecorder(stream, handlers);
    this.startMeter(stream, handlers);
  }

  private startRecorder(stream: MediaStream, handlers: ListenHandlers) {
    const mimeType = pickMimeType();
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    } catch {
      handlers.onError(new VoiceError("unsupported", "This browser can't record audio."));
      return;
    }

    this.chunks = [];
    // Resolved by `onstop`, which is the only point at which the container is
    // complete — a Blob assembled from chunks before then can be undecodable.
    this.recording = new Promise<Blob | null>((resolve) => {
      recorder.onstop = () => {
        resolve(this.chunks.length ? new Blob(this.chunks, { type: recorder.mimeType }) : null);
      };
    });

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    };
    // Timeslice so a crash or an abrupt unmount still leaves usable audio behind
    // rather than one never-flushed buffer.
    recorder.start(1000);
    this.recorder = recorder;
  }

  private startMeter(stream: MediaStream, handlers: ListenHandlers) {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const context = new Ctor();
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.6;
    context.createMediaStreamSource(stream).connect(analyser);

    this.audioContext = context;
    this.analyser = analyser;
    this.buffer = new Float32Array(new ArrayBuffer(analyser.fftSize * 4));

    this.ticker = setInterval(() => this.tick(handlers), TICK_MS);
  }

  /** One VAD sample: measure, decide, and tell the caller where we are. */
  private tick(handlers: ListenHandlers) {
    const analyser = this.analyser;
    const buffer = this.buffer;
    if (!analyser || !buffer) return;

    analyser.getFloatTimeDomainData(buffer);
    let sum = 0;
    for (let i = 0; i < buffer.length; i += 1) sum += buffer[i] * buffer[i];
    const rms = Math.sqrt(sum / buffer.length);

    const now = performance.now();
    const elapsed = now - this.startedAt;

    // Track the quiet floor so a noisy room raises the bar instead of reading as
    // continuous speech. Rises slowly, falls fast — it should follow the room
    // down to quiet, not be dragged up by the candidate's own voice.
    this.noiseFloor =
      rms < this.noiseFloor ? this.noiseFloor * 0.9 + rms * 0.1 : this.noiseFloor * 0.999 + rms * 0.001;

    const threshold = Math.max(MIN_SPEECH_RMS, this.noiseFloor * NOISE_MULTIPLIER);
    const loud = rms > threshold;

    if (loud) {
      this.lastLoudAt = now;
      if (this.aboveSince === null) this.aboveSince = now;
      // Sustained, so it's speech rather than a click — open a burst.
      if (this.burstStartedAt === null && now - this.aboveSince >= ATTACK_MS) {
        this.burstStartedAt = elapsed - ATTACK_MS;
      }
    } else {
      this.aboveSince = null;
      // Quiet for longer than the gap between words — close the burst.
      if (this.burstStartedAt !== null && now - this.lastLoudAt >= HANGOVER_MS) {
        this.segments.push({
          text: "",
          start_ms: Math.max(0, this.burstStartedAt),
          end_ms: this.lastLoudAt - this.startedAt,
        });
        this.burstStartedAt = null;
      }
    }

    const speaking = this.burstStartedAt !== null;
    handlers.onTranscript({
      text: "",
      interim: "",
      isFinal: false,
      segments: this.currentSegments(elapsed),
      // Scaled for a meter rather than reported raw: speech RMS lives around
      // 0.02-0.2, which would barely move a 0-1 bar.
      level: Math.min(1, rms * 8),
      speaking,
    });
  }

  /** Closed bursts, plus the one in progress so the last utterance isn't lost. */
  private currentSegments(elapsed: number): TranscriptSegment[] {
    if (this.burstStartedAt === null) return [...this.segments];
    return [
      ...this.segments,
      { text: "", start_ms: Math.max(0, this.burstStartedAt), end_ms: elapsed },
    ];
  }

  stopListening(): void {
    if (this.ticker) {
      clearInterval(this.ticker);
      this.ticker = null;
    }
    // Close the burst that was open when they stopped, or its silence would be
    // dropped and the last pause would go unmeasured.
    if (this.burstStartedAt !== null) {
      this.segments.push({
        text: "",
        start_ms: Math.max(0, this.burstStartedAt),
        end_ms: Math.max(this.burstStartedAt, this.lastLoudAt - this.startedAt),
      });
      this.burstStartedAt = null;
    }
    // One last update so the caller's copy of the segments includes that closing
    // burst. Without it the final utterance would be missing from every answer.
    this.handlers?.onTranscript({
      text: "",
      interim: "",
      isFinal: true,
      segments: [...this.segments],
      level: 0,
      speaking: false,
    });

    if (this.recorder && this.recorder.state !== "inactive") {
      this.recorder.stop(); // resolves `this.recording` via onstop
    }
    this.recorder = null;

    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;

    void this.audioContext?.close().catch(() => {});
    this.audioContext = null;
    this.analyser = null;
    this.buffer = null;
    this.handlers = null;
  }

  async takeRecording(): Promise<Blob | null> {
    const pending = this.recording;
    this.recording = null;
    if (!pending) return null;
    return pending;
  }

  private reset() {
    this.segments = [];
    this.chunks = [];
    this.recording = null;
    this.burstStartedAt = null;
    this.aboveSince = null;
    this.noiseFloor = MIN_SPEECH_RMS;
  }

  dispose(): void {
    this.stopListening();
    this.speaker.dispose();
    this.reset();
  }
}
