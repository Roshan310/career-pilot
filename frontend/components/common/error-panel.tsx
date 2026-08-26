"use client";

import { RotateCw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorPanelProps {
  title?: string;
  description?: string;
  /** Digest or message, shown small so a user can quote it in a bug report. */
  detail?: string;
  onRetry?: () => void;
  action?: React.ReactNode;
}

/** Shared body for every error boundary and 404 so failures stay on-brand. */
export function ErrorPanel({
  title = "Something went wrong",
  description = "This section failed to load. It is usually temporary.",
  detail,
  onRetry,
  action,
}: ErrorPanelProps) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-error-bg">
        <TriangleAlert size={24} className="text-error" strokeWidth={2} />
      </div>
      <h1 className="text-[20px] font-semibold text-text-primary">{title}</h1>
      <p className="mt-2 max-w-md text-[15px] leading-relaxed text-text-secondary">{description}</p>
      {detail && (
        <p className="mt-3 max-w-md break-words font-mono text-[12px] text-text-muted">{detail}</p>
      )}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        {onRetry && (
          <Button onClick={onRetry}>
            <RotateCw size={16} /> Try again
          </Button>
        )}
        {action}
      </div>
    </div>
  );
}
