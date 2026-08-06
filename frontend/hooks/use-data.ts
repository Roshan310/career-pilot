"use client";

import { useQuery } from "@tanstack/react-query";
import { listResumes, getResume } from "@/lib/api/resumes";
import { listJobs, getJob } from "@/lib/api/jobs";
import { listMatches, getMatch } from "@/lib/api/matches";
import { listInterviews, getInterview, getInterviewReport } from "@/lib/api/interviews";
import { getUsage } from "@/lib/api/usage";
import type { MatchStatus } from "@/lib/types";

export const useResumes = () =>
  useQuery({ queryKey: ["resumes"], queryFn: listResumes });

export const useResume = (id: string) =>
  useQuery({ queryKey: ["resume", id], queryFn: () => getResume(id), enabled: !!id });

export const useJobs = () => useQuery({ queryKey: ["jobs"], queryFn: listJobs });

export const useJob = (id: string) =>
  useQuery({ queryKey: ["job", id], queryFn: () => getJob(id), enabled: !!id });

export const useMatches = () =>
  useQuery({ queryKey: ["matches"], queryFn: listMatches });

export const useMatch = (id: string | null | undefined) =>
  useQuery({ queryKey: ["match", id], queryFn: () => getMatch(id as string), enabled: !!id });

/**
 * Poll a single match while it's still running. Stops polling once the match
 * reaches a terminal state (done|failed).
 */
export const useMatchPolling = (id: string | null) =>
  useQuery({
    queryKey: ["match", id],
    queryFn: () => getMatch(id as string),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status as MatchStatus | undefined;
      return status === "done" || status === "failed" ? false : 1500;
    },
  });

export const useInterviews = () =>
  useQuery({ queryKey: ["interviews"], queryFn: listInterviews });

/**
 * A single session with its full turn history. Not polled — the live session
 * screen owns its own state after the first load and only refetches on conflict.
 */
export const useInterview = (sessionId: string) =>
  useQuery({
    queryKey: ["interview", sessionId],
    queryFn: () => getInterview(sessionId),
    enabled: !!sessionId,
    retry: false,
    staleTime: Infinity,
  });

export const useInterviewReport = (sessionId: string) =>
  useQuery({
    queryKey: ["interview-report", sessionId],
    queryFn: () => getInterviewReport(sessionId),
    enabled: !!sessionId,
    retry: false,
  });

export const useUsage = () => useQuery({ queryKey: ["usage"], queryFn: getUsage });
