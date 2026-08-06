import { cn } from "@/lib/utils";

/** CareerPilot wordmark with the wine-red "R"-style mark from the design. */
export function Logo({ className, showWordmark = true }: { className?: string; showWordmark?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden>
        <rect width="32" height="32" rx="9" fill="#B4232D" />
        <path
          d="M11 23V9h6.2c2.7 0 4.5 1.6 4.5 4.1 0 1.8-1 3.2-2.6 3.8L22 23h-3.3l-2.4-5.3h-2v5.3H11Zm3.3-7.9h2.6c1.2 0 2-.7 2-1.9 0-1.1-.8-1.8-2-1.8h-2.6v3.7Z"
          fill="#fff"
        />
      </svg>
      {showWordmark && (
        <span className="text-[19px] font-bold tracking-tight text-text-primary">CareerPilot</span>
      )}
    </div>
  );
}
