"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { tokenStore } from "@/lib/api/client";
import { Skeleton } from "@/components/ui/skeleton";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(tokenStore.isAuthenticated ? "/dashboard" : "/login");
  }, [router]);

  // Pure redirect hop. A skeleton reads as "loading" without the brand flash of
  // a full-screen logo that is only on screen for a frame or two.
  return (
    <div className="min-h-screen bg-background" aria-busy="true" aria-label="Loading">
      <div className="mx-auto max-w-content space-y-6 px-6 py-10">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 rounded-card" />
      </div>
    </div>
  );
}
