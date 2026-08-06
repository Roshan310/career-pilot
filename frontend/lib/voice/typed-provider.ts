// The keyboard fallback (SPECS.md §7.3: "a 'type your answer instead' toggle for
// unsupported browsers, so the feature degrades gracefully rather than breaking").
//
// It implements the same interface so the interview screen runs one code path
// whether the answer was spoken or typed — the difference shows up only as
// `source: "typed"` on the submitted envelope.
//
// Questions are still voiced here: not being able to hold a microphone is no
// reason to read the interview in silence.

import type { Speaker } from "./speaker";
import type { ListenHandlers, VoiceProvider } from "./types";

export class TypedProvider implements VoiceProvider {
  readonly source = "typed" as const;
  readonly canListen = false;

  constructor(private speaker: Speaker) {}

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

  // No microphone: the textarea is the transcript source, and it produces no
  // segments, so the backend reports `longest_pause_ms: null` rather than
  // fabricating a number.
  listen(_handlers: ListenHandlers): void {}
  stopListening(): void {}

  /** Nothing was recorded — the answer arrives as text, already transcribed. */
  async takeRecording(): Promise<Blob | null> {
    return null;
  }

  dispose(): void {
    this.speaker.dispose();
  }
}
