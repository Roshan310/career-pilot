import { GapVisual, InterviewVisual, PipelineVisual, ScoreVisual } from "./feature-visuals";
import { Reveal } from "./reveal";

const ROWS = [
  {
    badge: "Match scoring",
    title: "A score you can actually act on",
    body: "Four signals are scored separately — semantic fit, skill overlap, experience level and keyword density, so you can tell whether you lost the match on substance or just on wording.",
    visual: <ScoreVisual />,
  },
  {
    badge: "Gap analysis",
    title: "See the gaps before the recruiter does",
    body: "Every requirement in the posting, checked against what your resume actually says. Then line-by-line rewrites for the bullets that undersell the work you did.",
    visual: <GapVisual />,
  },
  {
    badge: "Mock interviews",
    title: "An interviewer that has read your resume",
    body: "Questions come from your resume and that specific posting, never a generic bank, and each one shows what it was drawn from. Answer out loud; vague answers get a follow-up, and you get pace, filler-word and gap-coverage metrics at the end.",
    visual: <InterviewVisual />,
  },
  {
    badge: "Applications",
    title: "Every application in one pipeline",
    body: "Track each role from saved through to offer, with deadlines that surface before they pass and every analysis and practice session attached to the job it belongs to.",
    visual: <PipelineVisual />,
  },
];

export function Features() {
  return (
    <section id="features" className="scroll-mt-28 py-24 sm:py-32">
      <div className="mx-auto max-w-content px-6">
        <Reveal className="mx-auto max-w-[680px] text-center">
          <h2 className="text-[32px] font-bold leading-[1.15] tracking-[-0.02em] text-text-primary sm:text-[44px]">
            Four tools that share
            <br className="hidden sm:block" /> the same context
          </h2>
          <p className="mt-5 text-[17px] leading-relaxed text-text-secondary">
            The analysis feeds the interview, the interview feeds the report, and all of it hangs
            off the application it belongs to. Nothing asks you to explain yourself twice.
          </p>
        </Reveal>

        <div className="mt-20 space-y-24 sm:space-y-32">
          {ROWS.map((row, i) => {
            const flipped = i % 2 === 1;
            return (
              <div
                key={row.badge}
                className="grid items-center gap-10 lg:grid-cols-2 lg:gap-20"
              >
                <Reveal
                  from={flipped ? "right" : "left"}
                  className={flipped ? "lg:order-2" : undefined}
                >
                  <span className="inline-flex rounded-badge bg-wine-tint px-3.5 py-1.5 text-[13px] font-semibold text-wine-fg">
                    {row.badge}
                  </span>
                  <h3 className="mt-5 text-[28px] font-bold leading-[1.2] tracking-[-0.02em] text-text-primary sm:text-[34px]">
                    {row.title}
                  </h3>
                  <p className="mt-4 max-w-[520px] text-[16px] leading-[1.7] text-text-secondary sm:text-[17px]">
                    {row.body}
                  </p>
                </Reveal>

                <Reveal
                  delay={0.1}
                  from={flipped ? "left" : "right"}
                  className={flipped ? "lg:order-1" : undefined}
                >
                  <div
                    aria-hidden
                    className="rounded-[28px] border border-border bg-gradient-to-br from-wine/10 via-wine/5 to-transparent p-5 sm:p-9"
                  >
                    {row.visual}
                  </div>
                </Reveal>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
