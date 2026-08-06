"use client";

// Same auth guard as the main app shell, without the sidebar and top nav.
// A live interview is a focused mode: while the mic is open there should be
// nothing to click that silently ends the session. Leaving is explicit.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Logo } from "@/components/layout/logo";
import { useAuth } from "@/providers/auth-provider";

export default function SessionLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="animate-pulse">
          <Logo />
        </div>
      </div>
    );
  }

  return <div className="min-h-screen bg-background">{children}</div>;
}
