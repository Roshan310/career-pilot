// The single place the app chooses a voice implementation. Swapping in a
// streaming provider later means adding a file next to these two and one more
// branch here — nothing above `lib/voice/` changes.

export type { VoiceProvider, TranscriptUpdate, ListenHandlers, VoiceErrorKind } from "./types";
export { VoiceError } from "./types";
export type { Speaker } from "./speaker";
export { BrowserSpeaker, RemoteSpeaker, isSpeechSynthesisSupported } from "./speaker";
export { RecordedProvider, isRecordingSupported } from "./recorded-provider";
export { TypedProvider } from "./typed-provider";

import { RemoteSpeaker } from "./speaker";
import { RecordedProvider, isRecordingSupported } from "./recorded-provider";
import { TypedProvider } from "./typed-provider";
import type { VoiceProvider } from "./types";

export type VoiceMode = "voice" | "typed";

export interface CreateVoiceProviderOptions {
  mode: VoiceMode;
  /** Which session's question audio to fetch. */
  sessionId: string;
  /** Suppress spoken questions. Applies to both modes. */
  muted?: boolean;
}

/**
 * Returns the requested provider, downgrading to typed when the browser can't
 * record at all.
 *
 * Both modes speak through the same RemoteSpeaker, so questions are voiced
 * identically whether the candidate answers aloud or types. Note what is *not*
 * consulted here: `webkitSpeechRecognition`. Brave exposes that constructor
 * while refusing to return results, so its presence was never evidence of
 * anything — checking it is what produced a screen that claimed to be listening
 * and wasn't.
 */
export function createVoiceProvider({
  mode,
  sessionId,
  muted = false,
}: CreateVoiceProviderOptions): VoiceProvider {
  const speaker = new RemoteSpeaker(sessionId, muted);
  if (mode === "voice" && isRecordingSupported()) {
    return new RecordedProvider(speaker);
  }
  return new TypedProvider(speaker);
}
