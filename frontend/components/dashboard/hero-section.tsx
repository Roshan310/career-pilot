"use client";

import { useRouter } from "next/navigation";
import { CheckCircle2, Circle, FileText, Mic, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProgressRing } from "@/components/common/progress-ring";
import { greeting, displayName } from "@/lib/utils";
import type { User } from "@/lib/types";

interface HeroSectionProps {
  user: User | null;
  progress: { done: number; total: number; items: { label: string; done: boolean }[] };
  onUpload: () => void;
}

/** Reflects where the user actually is. The old copy was one static line shown
 *  identically to a brand-new account and to someone 40 interviews in. */
function subtitle(done: number, total: number): string {
  if (done === 0) return "Upload a resume to get your first match score.";
  if (done >= total) return "You have worked through every step — keep your practice sharp.";
  if (done === 1) return "Good start. Analyze your resume against a real job next.";
  return "You're one interview away from your next opportunity.";
}

export function HeroSection({ user, progress, onUpload }: HeroSectionProps) {
  const router = useRouter();
  const name = displayName(user?.name, user?.email);

  return (
    <section className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <h1 className="text-h2 text-text-primary">
          {greeting()}, {name} <span className="inline-block">👋</span>
        </h1>
        <p className="mt-2 text-[17px] text-text-secondary">
          {subtitle(progress.done, progress.total)}
        </p>

        <div className="mt-7 flex flex-wrap gap-3">
          <Button onClick={() => router.push("/analysis")}>
            <FileText size={18} /> Analyze Resume
          </Button>
          <Button variant="secondary" onClick={() => router.push("/interview")}>
            <Mic size={18} /> Start Interview
          </Button>
          <Button variant="secondary" onClick={onUpload}>
            <Upload size={18} /> Upload Resume
          </Button>
        </div>
      </div>

      {/* Today's Progress */}
      <div className="rounded-card border border-border bg-card p-6 shadow-card">
        <p className="text-card-title text-text-primary">Your Progress</p>
        <div className="mt-4 flex items-center gap-5">
          <ProgressRing value={progress.total ? progress.done / progress.total : 0} size={92} thickness={7}>
            <span className="text-[20px] font-bold text-text-primary">
              {progress.done}/{progress.total}
            </span>
          </ProgressRing>
          <ul className="flex-1 space-y-2.5">
            {progress.items.map((item) => (
              <li key={item.label} className="flex items-center gap-2.5 text-[14px]">
                {item.done ? (
                  <CheckCircle2 size={17} className="text-success" />
                ) : (
                  <Circle size={17} className="text-text-disabled" />
                )}
                <span className={item.done ? "text-text-primary" : "text-text-muted"}>
                  {item.label}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
