// How a question gets voiced. Split out from VoiceProvider because speaking and
// listening fail for completely unrelated reasons, and both providers were
// carrying their own copy of the same broken `speak()`.
//
// The default is server-generated audio. `speechSynthesis` is a last resort, not
// a peer: Brave restricts it, Linux Chromium ships with no local voices unless
// speech-dispatcher is installed, and calling `cancel()` immediately before
// `speak()` silently drops the utterance in both Chrome and Firefox — a bug this
// project shipped for a while, which is why the fallback below is written the
// way it is.

import { getQuestionAudio } from "@/lib/api/interviews";

export interface Speaker {
  readonly canSpeak: boolean;
  /** Resolves when the question has finished being voiced, or immediately if it can't be. */
  speak(text: string, turnNumber: number): Promise<void>;
  cancel(): void;
  setMuted(muted: boolean): void;
  dispose(): void;
}

// ---- browser speech synthesis (fallback only) ----

/**
 * Utterances must outlive the call that created them. Chrome and Safari garbage
 * collect an unreferenced SpeechSynthesisUtterance mid-sentence, after which no
 * further events fire and the caller waits forever.
 */
let heldUtterance: SpeechSynthesisUtterance | null = null;

export function isSpeechSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export class BrowserSpeaker implements Speaker {
  private muted = false;
  private timeout: ReturnType<typeof setTimeout> | null = null;

  constructor(muted = false) {
    this.muted = muted;
  }

  get canSpeak(): boolean {
    return !this.muted && isSpeechSynthesisSupported();
  }

  speak(text: string): Promise<void> {
    if (!this.canSpeak || !text.trim()) return Promise.resolve();

    return new Promise<void>((resolve) => {
      let settled = false;
      const done = () => {
        if (settled) return;
        settled = true;
        this.clearTimeout();
        resolve();
      };

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      utterance.rate = 1;
      utterance.onend = done;
      utterance.onerror = done;
      heldUtterance = utterance;

      // A watchdog, because speechSynthesis events are not dependable: Chrome
      // intermittently never fires `onend`, and on a machine with no voices
      // installed neither event fires at all. Without this the interview would
      // sit in "speaking" and never open the microphone. ~2.5 words/sec.
      const words = text.trim().split(/\s+/).length;
      this.timeout = setTimeout(done, Math.max(4000, (words / 2.5) * 1000 + 3000));

      // Deliberately NOT cancel()-then-speak(): that pairing drops the utterance
      // outright in Chrome and Firefox. Anything still queued is cancelled by
      // whoever moves the turn on, not here.
      window.speechSynthesis.speak(utterance);
    });
  }

  cancel(): void {
    this.clearTimeout();
    if (isSpeechSynthesisSupported()) window.speechSynthesis.cancel();
    heldUtterance = null;
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    if (muted) this.cancel();
  }

  dispose(): void {
    this.cancel();
  }

  private clearTimeout() {
    if (this.timeout) {
      clearTimeout(this.timeout);
      this.timeout = null;
    }
  }
}

// ---- server-generated audio (the real one) ----

export class RemoteSpeaker implements Speaker {
  private muted = false;
  private audio: HTMLAudioElement | null = null;
  private objectUrl: string | null = null;
  private fallback: BrowserSpeaker;

  constructor(
    private sessionId: string,
    muted = false,
  ) {
    this.muted = muted;
    this.fallback = new BrowserSpeaker(muted);
  }

  /** Always true: if the fetch fails we fall back, and if that fails too the
   *  question is still on screen to read. Never a reason to block the interview. */
  get canSpeak(): boolean {
    return !this.muted;
  }

  async speak(text: string, turnNumber: number): Promise<void> {
    if (this.muted || !text.trim()) return;

    let blob: Blob;
    try {
      blob = await getQuestionAudio(this.sessionId, turnNumber);
    } catch {
      // 503 (no key / vendor down) or offline. A worse voice beats no voice.
      return this.fallback.speak(text);
    }
    if (this.muted) return; // muted while the audio was in flight

    try {
      await this.play(blob);
    } catch {
      return this.fallback.speak(text);
    }
  }

  private play(blob: Blob): Promise<void> {
    this.releaseUrl();
    this.objectUrl = URL.createObjectURL(blob);

    // One element reused for the whole session. A fresh element per question
    // leaks, and on some browsers loses the autoplay permission granted by the
    // user's initial gesture.
    if (!this.audio) this.audio = new Audio();
    const audio = this.audio;
    audio.src = this.objectUrl;

    return new Promise<void>((resolve, reject) => {
      let settled = false;
      const finish = (fn: () => void) => {
        if (settled) return;
        settled = true;
        audio.onended = null;
        audio.onerror = null;
        fn();
      };

      audio.onended = () => finish(resolve);
      // `error` here means decode or source failure. Reject so the caller can
      // fall back rather than skipping the question in silence.
      audio.onerror = () => finish(() => reject(new Error("audio playback failed")));

      // play() rejects when autoplay is blocked — which is exactly why the
      // session screen requires a Begin click before the first question.
      audio.play().catch((err) => finish(() => reject(err)));
    });
  }

  cancel(): void {
    if (this.audio) {
      this.audio.pause();
      this.audio.currentTime = 0;
    }
    this.fallback.cancel();
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    this.fallback.setMuted(muted);
    if (muted) this.cancel();
  }

  dispose(): void {
    this.cancel();
    this.releaseUrl();
    this.audio = null;
    this.fallback.dispose();
  }

  private releaseUrl() {
    if (this.objectUrl) {
      URL.revokeObjectURL(this.objectUrl);
      this.objectUrl = null;
    }
  }
}
