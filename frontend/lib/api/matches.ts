import { api } from "./client";
import type { Match, MatchListItem, MatchStatusResponse } from "../types";

export function listMatches(): Promise<MatchListItem[]> {
  return api.get<MatchListItem[]>("/api/matches");
}

export function getMatch(id: string): Promise<Match> {
  return api.get<Match>(`/api/matches/${id}`);
}

export function createMatch(resume_id: string, job_id: string): Promise<MatchStatusResponse> {
  return api.post<MatchStatusResponse>("/api/matches", { resume_id, job_id });
}
