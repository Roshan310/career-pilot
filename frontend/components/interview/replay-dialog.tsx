"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, Loader2, MessageCircleQuestion, Repeat } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { replayInterview } from "@/lib/api/interviews";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The finished session whose questions are being re-run. */
  sessionId: string;
}

/**
 * Two options rather than a toggle, because the difference is what the practice
 * session *is* — a straight drill or the full adaptive interview — not a
 * setting on one thing.
 *
 * Framed by what the candidate gets. The cost asymmetry is real (main questions
 * come from the audio cache, follow-ups are new text and must be synthesized)
 * but that is our problem, not something to make someone weigh mid-practice.
 */
const OPTIONS = [
  {
    allowFollowUps: true,
    icon: MessageCircleQuestion,
    title: "Full interview",
    description:
      "Follow-up questions too, based on how you answer this time. Closest to the real thing.",
    recommended: true,
  },
  {
    allowFollowUps: false,
    icon: Repeat,
    title: "Main questions only",
    description: "The same questions, straight through. Fastest way to drill your answers.",
    recommended: false,
  },
] as const;

export function ReplayDialog({ open, onOpenChange, sessionId }: Props) {
  const router = useRouter();
  const qc = useQueryClient();
  const [allowFollowUps, setAllowFollowUps] = useState(true);
  const [starting, setStarting] = useState(false);

  async function start() {
    setStarting(true);
    try {
      const session = await replayInterview(sessionId, { allowFollowUps });
      // The history list gains a row and every sibling's attempt count changes.
      qc.invalidateQueries({ queryKey: ["interviews"] });
      router.push(`/interviews/${session.id}`);
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Could not start the practice session.",
      );
      setStarting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !starting && onOpenChange(next)}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Practise this again</DialogTitle>
          <DialogDescription>
            Same questions, fresh answers. Nothing is regenerated, so this starts straight away.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {OPTIONS.map((option) => {
            const selected = option.allowFollowUps === allowFollowUps;
            const Icon = option.icon;
            return (
              <button
                key={option.title}
                type="button"
                onClick={() => setAllowFollowUps(option.allowFollowUps)}
                aria-pressed={selected}
                className={cn(
                  "flex w-full items-start gap-3 rounded-2xl border p-4 text-left transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40",
                  selected
                    ? "border-wine bg-wine-tint"
                    : "border-border bg-background hover:bg-hover",
                )}
              >
                <div
                  className={cn(
                    "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
                    selected ? "bg-wine text-white" : "bg-hover text-text-muted",
                  )}
                >
                  {selected ? <Check size={18} /> : <Icon size={18} />}
                </div>
                <div className="min-w-0">
                  <p className="text-[15px] font-semibold text-text-primary">
                    {option.title}
                    {option.recommended && (
                      <span className="ml-2 text-[12px] font-medium text-text-muted">
                        Recommended
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 text-[13px] leading-relaxed text-text-secondary">
                    {option.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={starting}>
            Cancel
          </Button>
          <Button onClick={start} disabled={starting}>
            {starting ? <Loader2 size={18} className="animate-spin" /> : <Repeat size={18} />}
            {starting ? "Starting…" : "Start practice"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
