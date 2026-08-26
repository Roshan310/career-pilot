"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "js.reviewed_reports";

/**
 * Which interview reports this browser has actually opened.
 *
 * The dashboard checklist used to tick "Feedback reviewed" the moment an
 * interview completed, which claimed the user had read a report they may never
 * have opened. There is no server-side read receipt, so this is client-local by
 * design — it under-reports on a new device rather than inventing progress.
 */
function read(): string[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return []; // storage blocked or value corrupted — treat as "nothing reviewed"
  }
}

export function markReportReviewed(sessionId: string): void {
  if (typeof window === "undefined" || !sessionId) return;
  try {
    const current = read();
    if (current.includes(sessionId)) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...current, sessionId]));
    // Same-tab listeners: the native `storage` event only fires cross-tab.
    window.dispatchEvent(new Event("js:reviewed-reports"));
  } catch {
    /* preference just won't persist */
  }
}

export function useReviewedReports(): { reviewed: string[]; hasAny: boolean } {
  // Starts empty so server and first client render agree; filled after mount.
  const [reviewed, setReviewed] = useState<string[]>([]);

  const sync = useCallback(() => setReviewed(read()), []);

  useEffect(() => {
    sync();
    window.addEventListener("js:reviewed-reports", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("js:reviewed-reports", sync);
      window.removeEventListener("storage", sync);
    };
  }, [sync]);

  return { reviewed, hasAny: reviewed.length > 0 };
}
