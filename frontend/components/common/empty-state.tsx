import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

/** Educational empty state with a clear next action (UX rules §22). */
export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-14 text-center", className)}>
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-wine-tint">
        <Icon size={24} className="text-wine" strokeWidth={2} />
      </div>
      <h4 className="text-[17px] font-semibold text-text-primary">{title}</h4>
      <p className="mt-1.5 max-w-sm text-[15px] text-text-secondary">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
