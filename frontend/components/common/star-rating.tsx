import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

interface StarRatingProps {
  /** 0..5, halves allowed. */
  value: number;
  max?: number;
  className?: string;
}

export function StarRating({ value, max = 5, className }: StarRatingProps) {
  return (
    <div className={cn("flex items-center gap-1", className)} aria-label={`${value} out of ${max}`}>
      {Array.from({ length: max }).map((_, i) => {
        const filled = value >= i + 1;
        const half = !filled && value >= i + 0.5;
        return (
          <span key={i} className="relative inline-flex">
            <Star size={16} className="text-text-disabled" strokeWidth={2} />
            {(filled || half) && (
              <span className="absolute inset-0 overflow-hidden" style={{ width: half ? "50%" : "100%" }}>
                <Star size={16} className="fill-wine text-wine" strokeWidth={2} />
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}
