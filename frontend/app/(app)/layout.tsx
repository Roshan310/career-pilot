"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { MobileBar } from "@/components/layout/mobile-bar";
import { useAuth } from "@/providers/auth-provider";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ErrorPanel } from "@/components/common/error-panel";

/**
 * The shell renders immediately and only the content area waits on /auth/me.
 * Previously the whole viewport was a centred pulsing logo until the request
 * resolved, then the sidebar, nav and page all appeared at once — a full-page
 * layout shift on every hard refresh. Sidebar and MobileBar both tolerate a null
 * user, so there is nothing to gate them on.
 */
function ContentSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-10 w-64" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-64 rounded-card" />
        <Skeleton className="h-64 rounded-card" />
      </div>
      <Skeleton className="h-48 rounded-card" />
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, error, refreshUser } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Only redirect on a clean "not signed in". A network failure leaves `error`
    // set, and bouncing to /login there would look like a surprise logout.
    if (!loading && !user && !error) {
      router.replace("/login");
    }
  }, [loading, user, error, router]);

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only left-4 top-4 z-50 rounded-btn bg-card px-4 py-2 text-[15px] font-medium text-text-primary shadow-modal focus:not-sr-only focus:absolute"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="lg:pl-[280px]">
        <MobileBar />
        <main id="main-content" className="mx-auto max-w-content px-6 py-8 lg:px-8">
          {error && !user ? (
            <ErrorPanel
              title="Couldn't load your account"
              description={error}
              onRetry={() => refreshUser()}
              action={
                <Button variant="secondary" onClick={() => router.replace("/login")}>
                  Sign in again
                </Button>
              }
            />
          ) : loading || !user ? (
            <ContentSkeleton />
          ) : (
            children
          )}
        </main>
      </div>
    </div>
  );
}
