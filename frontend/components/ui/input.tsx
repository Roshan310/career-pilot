import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Inline validation message. Renders under the field and sets aria-invalid. */
  error?: string | null;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, id, "aria-describedby": describedBy, ...props }, ref) => {
    const generatedId = React.useId();
    const inputId = id ?? generatedId;
    const errorId = `${inputId}-error`;

    return (
      <>
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={[describedBy, error ? errorId : null].filter(Boolean).join(" ") || undefined}
          className={cn(
            "h-11 w-full rounded-input border bg-card px-3.5 text-[15px] text-text-primary placeholder:text-text-muted transition-colors duration-[180ms] focus:outline-none focus:ring-2 disabled:opacity-50",
            // A read-only field must not look like an editable one.
            "read-only:cursor-default read-only:bg-hover read-only:text-text-secondary",
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
Input.displayName = "Input";

export { Input };
