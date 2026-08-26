import { cn } from "@/lib/utils";

/**
 * CareerPilot wordmark. The mark is a paper plane — the previous glyph was a
 * letter "R", which matched neither the product name nor the repository name.
 * Keep in sync with app/icon.svg, which draws the same path as the favicon.
 */
export function Logo({ className, showWordmark = true }: { className?: string; showWordmark?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden>
        <rect width="32" height="32" rx="9" fill="#B4232D" />
        <path d="M25.5 6.5 L6.5 14.2 L14.2 17.8 Z" fill="#fff" />
        <path d="M25.5 6.5 L14.2 17.8 L18 25.5 Z" fill="#fff" fillOpacity="0.72" />
      </svg>
      {showWordmark && (
        <span className="text-[19px] font-bold tracking-tight text-text-primary">CareerPilot</span>
      )}
    </div>
  );
}
