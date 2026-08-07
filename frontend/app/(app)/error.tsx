"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ErrorPanel } from "@/components/common/error-panel";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const router = useRouter();

  useEffect(() => {
    // No error-reporting service is wired up yet; the console is all there is.
    console.error("Route error:", error);
  }, [error]);

  return (
    <Card className="p-6">
      <ErrorPanel
        description="This page failed to load. Your data is safe — try again, or head back to the dashboard."
        detail={error.digest ? `Reference: ${error.digest}` : undefined}
        onRetry={reset}
        action={
          <Button variant="secondary" onClick={() => router.push("/dashboard")}>
            Back to Dashboard
          </Button>
        }
      />
    </Card>
  );
}
