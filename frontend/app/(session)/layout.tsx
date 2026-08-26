"use client";

// Same auth guard as the main app shell, without the sidebar and top nav.
// A live interview is a focused mode: while the mic is open there should be
// nothing to click that silently ends the session. Leaving is explicit.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { Skeleton } from "@/components/ui/skeleton";

export default function SessionLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    // Mirrors the session page's own skeleton so the transition is invisible
    // rather than a centred logo that snaps into a full layout.
    return (
      <div className="min-h-screen bg-background">
        <div className="mx-auto max-w-3xl space-y-6 px-6 py-10" aria-busy="true" aria-label="Loading">
          <Skeleton className="h-14 rounded-card" />
          <Skeleton className="h-40 rounded-card" />
          <Skeleton className="h-56 rounded-card" />
        </div>
      </div>
    );
  }

  return <div className="min-h-screen bg-background">{children}</div>;
}
