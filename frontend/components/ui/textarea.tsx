import * as React from "react";
import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "w-full rounded-input border border-border bg-card px-3.5 py-3 text-[15px] leading-6 text-text-primary placeholder:text-text-muted transition-colors duration-[180ms] focus:border-wine focus:outline-none focus:ring-2 focus:ring-wine/15 disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export { Textarea };
