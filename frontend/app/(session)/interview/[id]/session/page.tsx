"use client";

import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, Info, Keyboard, LogOut, Mic, RotateCcw, Volume2, VolumeX } from "lucide-react";
import { AnswerControls } from "@/components/interview/answer-controls";
import { LiveTranscript } from "@/components/interview/live-transcript";
import { MicOrb } from "@/components/interview/mic-orb";
import { QuestionCard } from "@/components/interview/question-card";
import { SessionHeader } from "@/components/interview/session-header";
import { SessionSummary } from "@/components/interview/session-summary";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useInterviews } from "@/hooks/use-data";
import { useInterviewSession } from "@/hooks/use-interview-session";

export default function InterviewSessionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [confirmExit, setConfirmExit] = useState(false);

  // The session endpoint doesn't carry job metadata; the history list does, and
  // it's already cached from the dashboard in most cases.
  const { data: interviews } = useInterviews();
  const meta = interviews?.find((i) => i.id === id);

  const onCompleted = useCallback(
    (sessionId: string) => router.replace(`/interviews/${sessionId}/report`),
    [router],
  );
  const onAbandoned = useCallback(() => router.replace("/interviews"), [router]);

  const s = useInterviewSession({ sessionId: id, onCompleted, onAbandoned });

  const typed = s.typing;
  const submitting = s.phase === "submitting" || s.phase === "transcribing";

  // A quiet marker so a replay is never mistaken for the original run, and so
  // "main questions only" is visible rather than inferred from follow-ups that
  // never arrive.
  const subtitle =
    [
      meta?.job_company,
      meta && meta.total_attempts > 1 ? `Attempt ${meta.attempt_number}` : null,
      meta && !meta.allow_follow_ups ? "main questions only" : null,
    ]
      .filter(Boolean)
      .join(" · ") || null;

  const header = (
    <SessionHeader
      title={meta?.job_title || "Mock interview"}
      subtitle={subtitle}
      progress={s.progress}
      secondsRemaining={s.secondsRemaining}
      right={
        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={() => s.setMuted(!s.muted)}
            title={s.muted ? "Unmute questions" : "Mute questions"}
            className="flex h-9 w-9 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-hover hover:text-text-primary"
          >
            {s.muted ? <VolumeX size={17} /> : <Volume2 size={17} />}
            <span className="sr-only">{s.muted ? "Unmute questions" : "Mute questions"}</span>
          </button>
          <button
            onClick={() => setConfirmExit(true)}
            title="End interview"
            className="flex h-9 w-9 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-error-bg hover:text-error"
          >
            <LogOut size={17} />
            <span className="sr-only">End interview</span>
          </button>
        </div>
      }
    />
  );

  if (s.phase === "loading") {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <Skeleton className="h-14 rounded-card" />
        <Skeleton className="mt-6 h-32 rounded-card" />
        <Skeleton className="mt-6 h-40 rounded-card" />
      </div>
    );
  }

  if (s.phase === "error") {
    return (
      <div className="mx-auto max-w-xl px-6 py-16">
        <Card className="p-10 text-center">
          <AlertTriangle size={28} className="mx-auto text-warning" />
          <h2 className="mt-4 text-h3 text-text-primary">Couldn&apos;t open this interview</h2>
          <p className="mt-2 text-[15px] text-text-secondary">{s.error}</p>
          <Button variant="secondary" className="mt-6" onClick={() => router.push("/interview")}>
            Back to Interview Practice
          </Button>
        </Card>
      </div>
    );
  }

  // Browsers refuse to play audio or open a microphone without a user gesture,
  // so the interview cannot start itself. This screen is that gesture — without
  // it the first question would be blocked from playing and the mic would never
  // open, which is indistinguishable from the app being broken.
  if (s.phase === "ready") {
    return (
      <div className="flex min-h-screen flex-col">
        {header}
        <main className="mx-auto flex w-full max-w-xl flex-1 flex-col justify-center px-6 py-10">
          <Card className="p-10 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-wine/10">
              <Mic size={24} className="text-wine-fg" />
            </div>
            <h2 className="mt-5 text-h3 text-text-primary">
              {s.answered.length > 0 ? "Ready to pick up where you left off" : "Ready when you are"}
            </h2>
            <p className="mt-2 text-[15px] leading-relaxed text-text-secondary">
              Your interviewer will read each question aloud. Answer out loud — when you stop
              speaking for a few seconds, your answer is submitted automatically, and you can
              always cancel that or type instead.
            </p>
            <p className="mt-3 text-[13px] text-text-muted">
              Your browser will ask for microphone access.
            </p>
            <Button className="mt-7" onClick={s.start}>
              <Mic size={18} /> Begin interview
            </Button>
          </Card>
        </main>
      </div>
    );
  }

  const wrappingUp = s.phase === "wrapping_up" || s.phase === "completing";

  return (
    <div className="flex min-h-screen flex-col">
      {header}

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 py-10">
        {s.notice && (
          <div className="mb-6 flex items-start gap-2.5 rounded-card border border-border bg-info-bg px-4 py-3 text-[14px] text-info">
            <Info size={17} className="mt-0.5 shrink-0" />
            <span className="flex-1">{s.notice}</span>
            <button onClick={s.dismissNotice} className="shrink-0 font-medium underline">
              Dismiss
            </button>
          </div>
        )}

        {wrappingUp ? (
          <SessionSummary
            answeredCount={s.answered.length}
            completing={s.phase === "completing"}
            error={s.error}
            onComplete={() => void s.complete()}
            onDiscard={() => setConfirmExit(true)}
          />
        ) : (
          <>
            {s.question && (
              <div className="pt-4">
                <QuestionCard question={s.question} speaking={s.turn.phase === "speaking"} />
              </div>
            )}

            <div className="mt-10 flex justify-center">
              <MicOrb
                phase={s.turn.phase}
                submitting={submitting}
                transcribing={s.phase === "transcribing"}
                countdownFraction={s.turn.countdownFraction}
                countdownSeconds={
                  s.turn.countdownMs === null ? null : Math.ceil(s.turn.countdownMs / 1000)
                }
                typed={typed}
              />
            </div>

            {s.turn.hint && (
              <p className="mt-4 text-center text-[14px] text-text-secondary">{s.turn.hint}</p>
            )}

            <div className="mt-8 space-y-5">
              {!typed && (
                <LiveTranscript
                  text={s.turn.transcript}
                  interim={s.turn.interim}
                  level={s.turn.level}
                  recording={s.turn.phase === "listening" || s.turn.phase === "armed"}
                  transcribing={s.phase === "transcribing"}
                />
              )}

              {s.phase === "submit_failed" ? (
                <Card className="p-5 text-center">
                  <p className="text-[15px] text-text-primary">{s.error}</p>
                  <p className="mt-1 text-[13px] text-text-secondary">
                    Your recording is still here — nothing was lost.
                  </p>
                  <div className="mt-4 flex flex-wrap justify-center gap-3">
                    <Button onClick={s.retrySubmit}>
                      <RotateCcw size={17} /> Try again
                    </Button>
                    {/* Retrying can keep failing — a mic that picked up nothing
                        intelligible will do it again. Typing is the way out that
                        doesn't cost the candidate the question. */}
                    <Button variant="secondary" onClick={s.switchToTyping}>
                      <Keyboard size={17} /> Type it instead
                    </Button>
                  </div>
                </Card>
              ) : (
                <AnswerControls
                  typed={typed}
                  canUseVoice={s.speechSupported}
                  armed={s.turn.phase === "armed"}
                  submitting={submitting}
                  hasAnswer={s.turn.hasAnswer}
                  typedAnswer={s.turn.typedAnswer}
                  onTypedAnswerChange={s.turn.setTypedAnswer}
                  onKeepGoing={s.turn.keepGoing}
                  onDone={s.finishAnswer}
                  onSkip={s.skipQuestion}
                  onToggleTyped={() => s.setVoiceMode(s.voiceMode === "typed" ? "voice" : "typed")}
                />
              )}
            </div>
          </>
        )}
      </main>

      <Dialog open={confirmExit} onOpenChange={setConfirmExit}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>End this interview?</DialogTitle>
            <DialogDescription>
              The session is closed without a feedback report. Answers you&apos;ve already given stay
              in your history, but you won&apos;t get scores for them.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setConfirmExit(false)}>
              Keep going
            </Button>
            <Button variant="danger" onClick={() => void s.abandon()}>
              End interview
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
