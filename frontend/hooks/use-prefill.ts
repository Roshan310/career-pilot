"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

/**
 * Picker selection carried in the URL.
 *
 * Every page that offered a next step used to `router.push("/analysis")` with
 * nothing attached, landing the user on an empty form they had just filled in
 * elsewhere. The worst case was the match report: the backend already accepts
 * `match_id` on interview creation, but reaching that flow meant re-selecting
 * the same resume and job by hand before the gap-analysis option appeared.
 *
 * Callers must render this inside a <Suspense> boundary — `useSearchParams`
 * opts a route out of static prerendering otherwise, and these pages are
 * statically rendered today.
 */
export function usePrefill(): { resume: string; job: string; match: string } {
  const params = useSearchParams();
  return {
    resume: params.get("resume") ?? "",
    job: params.get("job") ?? "",
    match: params.get("match") ?? "",
  };
}

/**
 * Drop a prefilled id that isn't in the list once the list has loaded.
 *
 * A link can carry something the user no longer owns — a deleted resume, a
 * stale bookmark. Without this the native select renders blank while the submit
 * button looks enabled, which reads as a broken form.
 */
export function useDropUnknownId<T extends { id: string }>(
  id: string,
  items: T[],
  clear: () => void,
): void {
  useEffect(() => {
    if (id && items.length > 0 && !items.some((item) => item.id === id)) clear();
    // `clear` is a setState updater — stable, and including it would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, items]);
}
