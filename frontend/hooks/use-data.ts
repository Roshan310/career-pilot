"use client";

import { useEffect, useRef, useState } from "react";
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
const POLL_INTERVAL_MS = 1500;
/** A match that has not settled in two minutes is stuck, not slow. */
const MATCH_POLL_GIVE_UP_MS = 120_000;
/** Long enough that a normal run never sees the "taking longer" copy. */
const MATCH_POLL_SLOW_MS = 20_000;

/**
 * Polls a match until it reaches a terminal state, then stops.
 *
 * The give-up bound matters: an enqueue that never reached the worker (Redis
 * down, worker crashed) leaves the row `pending` forever with nothing
 * server-side to reap it, and the UI used to spin on it indefinitely with no way
 * out. Elapsed wall time rather than a refetch count, so a backgrounded tab
 * (where refetches pause) doesn't report a stall that isn't real.
 */
export const useMatchPolling = (id: string | null) => {
  const startedAt = useRef<number | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const query = useQuery({
    queryKey: ["match", id],
    queryFn: () => getMatch(id as string),
    enabled: !!id,
    refetchInterval: (q) => {
      const status = q.state.data?.status as MatchStatus | undefined;
      if (status === "done" || status === "failed") return false;
      const since = startedAt.current;
      if (since !== null && Date.now() - since >= MATCH_POLL_GIVE_UP_MS) return false;
      return POLL_INTERVAL_MS;
    },
  });

  const status = query.data?.status as MatchStatus | undefined;
  const settled = status === "done" || status === "failed";

  useEffect(() => {
    if (!id || settled) {
      startedAt.current = null;
      setElapsed(0);
      return;
    }
    startedAt.current ??= Date.now();
    const tick = setInterval(() => {
      if (startedAt.current !== null) setElapsed(Date.now() - startedAt.current);
    }, 1000);
    return () => clearInterval(tick);
  }, [id, settled]);

  return {
    ...query,
    /** Still waiting, and it has been long enough to say so. */
    isSlow: !settled && elapsed >= MATCH_POLL_SLOW_MS,
    /** Gave up. The match is almost certainly orphaned server-side. */
    isStalled: !settled && elapsed >= MATCH_POLL_GIVE_UP_MS,
  };
};

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
