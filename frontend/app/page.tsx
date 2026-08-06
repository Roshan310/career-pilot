"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { tokenStore } from "@/lib/api/client";
import { Logo } from "@/components/layout/logo";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(tokenStore.isAuthenticated ? "/dashboard" : "/login");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="animate-pulse">
        <Logo />
      </div>
    </div>
  );
}
