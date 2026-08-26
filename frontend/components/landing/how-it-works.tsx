import { FileUp, Mic, Target } from "lucide-react";
import { Reveal } from "./reveal";

const STEPS = [
  {
    icon: FileUp,
    title: "Upload your resume",
    body: "PDF, DOCX or plain text. It gets parsed into structured roles, skills and dates rather than dumped into a prompt as one long string.",
  },
  {
    icon: Target,
    title: "Paste the job posting",
    body: "The whole thing, straight off the careers page. Requirements, seniority and the must-haves come back out as something the scorer can compare against.",
  },
  {
    icon: Mic,
    title: "Analyse, then practise",
    body: "Read the score and the gaps, take the rewrites that help, then sit an interview built from those exact gaps — out loud, with a report at the end.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-28 border-y border-border bg-sidebar py-24 sm:py-32">
      <div className="mx-auto max-w-content px-6">
        <Reveal className="mx-auto max-w-[620px] text-center">
          <span className="inline-flex rounded-badge bg-wine-tint px-3.5 py-1.5 text-[13px] font-semibold text-wine-fg">
            How it works
          </span>
          <h2 className="mt-5 text-[32px] font-bold leading-[1.15] tracking-[-0.02em] text-text-primary sm:text-[44px]">
            Three steps, one sitting
          </h2>
        </Reveal>

        <div className="relative mt-16 grid gap-6 lg:grid-cols-3 lg:gap-8">
          {/* The thread between the steps. Hairline, behind the cards, and gone
              below `lg` where the steps stack and the line would point sideways
              into nothing. */}
          <div
            aria-hidden
            className="absolute left-0 right-0 top-[52px] hidden h-px bg-gradient-to-r from-transparent via-border to-transparent lg:block"
          />

          {STEPS.map((step, i) => {
            const Icon = step.icon;
            return (
              <Reveal key={step.title} delay={i * 0.1} className="relative">
                <div className="h-full rounded-card border border-border bg-card p-7 shadow-card">
                  <div className="flex items-center gap-3">
                    <span className="flex h-11 w-11 items-center justify-center rounded-[14px] bg-wine-tint text-wine-fg">
                      <Icon size={20} />
                    </span>
                    <span className="text-[13px] font-semibold tabular-nums text-text-muted">
                      Step {i + 1}
                    </span>
                  </div>
                  <h3 className="mt-5 text-card-title text-text-primary">{step.title}</h3>
                  <p className="mt-2.5 text-[15px] leading-[1.65] text-text-secondary">{step.body}</p>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
