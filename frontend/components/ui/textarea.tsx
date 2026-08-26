import * as React from "react";
import { cn } from "@/lib/utils";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  /** Inline validation message. Renders under the field and sets aria-invalid. */
  error?: string | null;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, id, "aria-describedby": describedBy, ...props }, ref) => {
    const generatedId = React.useId();
    const areaId = id ?? generatedId;
    const errorId = `${areaId}-error`;

    return (
      <>
        <textarea
          ref={ref}
          id={areaId}
          aria-invalid={error ? true : undefined}
          aria-describedby={[describedBy, error ? errorId : null].filter(Boolean).join(" ") || undefined}
          className={cn(
            "w-full rounded-input border bg-card px-3.5 py-3 text-[15px] leading-6 text-text-primary placeholder:text-text-muted transition-colors duration-[180ms] focus:outline-none focus:ring-2 disabled:opacity-50",
            error
              ? "border-error focus:border-error focus:ring-error/20"
              : "border-border focus:border-wine focus:ring-wine/15",
            className,
          )}
          {...props}
        />
        {error && (
          <p id={errorId} className="text-[13px] text-error">
            {error}
          </p>
        )}
      </>
    );
  },
);
Textarea.displayName = "Textarea";

export { Textarea };
