import * as React from "react";
import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-11 w-full rounded-input border border-border bg-card px-3.5 text-[15px] text-text-primary placeholder:text-text-muted transition-colors duration-[180ms] focus:border-wine focus:outline-none focus:ring-2 focus:ring-wine/15 disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
