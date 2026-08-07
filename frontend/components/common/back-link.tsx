import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * The four detail pages each hand-rolled this as a `<button onClick={router.push}>`.
 * A real link is keyboard- and middle-click-friendly, and one component keeps the
 * four spellings of the same control from drifting apart.
 */
export function BackLink({
  href,
  children,
  className,
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center gap-1.5 rounded text-sm font-medium text-text-secondary transition-colors hover:text-text-primary",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40",
        className,
      )}
    >
      <ArrowLeft size={16} /> {children}
    </Link>
  );
}
