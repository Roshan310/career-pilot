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
          You&apos;re one interview away from your next opportunity.
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
        <p className="text-card-title text-text-primary">Today&apos;s Progress</p>
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
