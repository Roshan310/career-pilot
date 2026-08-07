import { api } from "./client";
import type {
  InterviewCreateRequest,
  InterviewListItem,
  InterviewSession,
  SessionReport,
  TurnSubmitRequest,
  TurnSubmitResponse,
} from "../types";

export function listInterviews(): Promise<InterviewListItem[]> {
  return api.get<InterviewListItem[]>("/api/interviews");
}

/**
 * Blocks 5-15s while the LLM drafts the question plan — deliberately synchronous
 * on the backend (see docs/decisions.md), so callers must show a preparing state
 * rather than expect this to return immediately.
 */
export function createInterview(body: InterviewCreateRequest): Promise<InterviewSession> {
  return api.post<InterviewSession>("/api/interviews", body);
}

/**
 * Practise a finished interview again over its stored questions.
 *
 * Returns immediately — unlike `createInterview`, nothing is generated, so
 * there is no 5-15s wait and no "preparing your interview" screen on this path.
 *
 * `allowFollowUps: false` runs the main questions only. That is the mode that
 * costs nothing in TTS: every question is already in the audio cache, and no
 * new text is ever synthesized. It does not make the run free of answer
 * scoring, which happens either way.
 */
export function replayInterview(
  sessionId: string,
  { allowFollowUps }: { allowFollowUps: boolean },
): Promise<InterviewSession> {
  return api.post<InterviewSession>(`/api/interviews/${sessionId}/replay`, {
    allow_follow_ups: allowFollowUps,
  });
}

/** Full session incl. turn history — this is what restores a session after a reload. */
export function getInterview(sessionId: string): Promise<InterviewSession> {
  return api.get<InterviewSession>(`/api/interviews/${sessionId}`);
}

export function submitTurn(
  sessionId: string,
  body: TurnSubmitRequest,
): Promise<TurnSubmitResponse> {
  return api.post<TurnSubmitResponse>(`/api/interviews/${sessionId}/turns`, body);
}

/**
 * The question, spoken. Server-generated because the browser's own speech
 * synthesis can't be relied on — Brave restricts it and Linux Chromium often has
 * no voices at all — and because a neural voice is the point.
 *
 * A 503 means the voice isn't configured or the vendor failed. That is expected
 * and recoverable: the caller falls back to browser speech rather than treating
 * it as a broken interview.
 */
export function getQuestionAudio(sessionId: string, turnNumber: number): Promise<Blob> {
  return api.getBlob(`/api/interviews/${sessionId}/turns/${turnNumber}/audio`);
}

/**
 * A recorded answer, transcribed server-side. Deliberately its own call rather
 * than part of `submitTurn`: the answer envelope has to exist in full before
 * anything can go wrong with sending it, or a transcription failure would
 * destroy an answer the candidate already gave.
 */
export async function transcribeAnswer(sessionId: string, audio: Blob): Promise<string> {
  const form = new FormData();
  // The extension matters to the server's content-type sniffing far less than
  // the blob's own type, which FormData carries through.
  form.append("audio", audio, "answer.webm");
  const { transcript } = await api.postForm<{ transcript: string }>(
    `/api/interviews/${sessionId}/transcribe`,
    form,
  );
  return transcript;
}

export function completeInterview(sessionId: string): Promise<SessionReport> {
  return api.post<SessionReport>(`/api/interviews/${sessionId}/complete`);
}

/** End without a report — the candidate quit early. */
export function abandonInterview(sessionId: string): Promise<InterviewSession> {
  return api.post<InterviewSession>(`/api/interviews/${sessionId}/abandon`);
}

export function getInterviewReport(sessionId: string): Promise<SessionReport> {
  return api.get<SessionReport>(`/api/interviews/${sessionId}/report`);
}
