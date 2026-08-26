"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Minus, Plus } from "lucide-react";
import { Reveal } from "./reveal";

const ITEMS = [
  {
    q: "How is this different from a resume keyword checker?",
    a: "Keyword tools count string matches. CareerPilot scores four signals separately — semantic fit, skill overlap, experience level and keyword density — so a resume that says the right things in different words isn't marked down as though it said nothing at all.",
  },
  {
    q: "Where do the interview questions come from?",
    a: "Your resume, the specific posting you paired it with, and the gap analysis between the two. Every question records what it was drawn from, and follow-ups fire automatically when an answer stays vague.",
  },
  {
    q: "Do I need a microphone?",
    a: "It helps, but it isn't required. Speech is handled server-side rather than by the browser, so practice works even where there's no built-in speech support — and every question has a typed fallback if you'd rather not talk.",
  },
  {
    q: "What can I upload?",
    a: "PDF, DOCX and plain text. The text is extracted and then parsed into structured roles, skills and dates, which is what the scoring and the interviewer both read.",
  },
  {
    q: "What does it cost?",
    a: "Nothing today. Billing isn't switched on — accounts run against free usage limits, and those limits are visible from your plan card in the app.",
  },
  {
    q: "What happens to my resume?",
    a: "It stays on your account so analyses and practice sessions can reference it, and every version lives in your resume library. You can delete any of them from there whenever you want.",
  },
];

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  const reduce = useReducedMotion();

  return (
    <section id="faq" className="scroll-mt-28 py-24 sm:py-32">
      <div className="mx-auto grid max-w-content gap-12 px-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-20">
        {/* Pinned on desktop: the accordion is roughly twice the height of this
            column, so a static heading left a screen and a half of empty gutter
            beside the answers. */}
        <Reveal from="left" className="lg:sticky lg:top-32 lg:self-start">
          <h2 className="text-[32px] font-bold leading-[1.15] tracking-[-0.02em] text-text-primary sm:text-[44px]">
            Questions,
            <br className="hidden sm:block" /> answered
          </h2>
          <p className="mt-5 max-w-[420px] text-[17px] leading-relaxed text-text-secondary">
            The things people ask before they upload anything.
          </p>
        </Reveal>

        <Reveal from="right" className="space-y-3">
          {ITEMS.map((item, i) => {
            const isOpen = open === i;
            return (
              <div
                key={item.q}
                className="overflow-hidden rounded-card border border-border bg-card shadow-card"
              >
                <h3>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={`faq-panel-${i}`}
                    onClick={() => setOpen(isOpen ? null : i)}
                    className="flex w-full items-center justify-between gap-4 px-5 py-5 text-left transition-colors hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-wine/40"
                  >
                    <span className="text-[16px] font-semibold text-text-primary sm:text-[17px]">
                      {item.q}
                    </span>
                    <span
                      className={
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors " +
                        (isOpen ? "bg-wine text-white" : "bg-hover text-text-secondary")
                      }
                    >
                      {isOpen ? <Minus size={16} /> : <Plus size={16} />}
                    </span>
                  </button>
                </h3>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      id={`faq-panel-${i}`}
                      initial={reduce ? false : { height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={reduce ? { height: 0, opacity: 0 } : { height: 0, opacity: 0 }}
                      transition={{ duration: reduce ? 0 : 0.32, ease: [0.22, 1, 0.36, 1] }}
                      className="overflow-hidden"
                    >
                      <p className="px-5 pb-5 text-[15px] leading-[1.7] text-text-secondary">
                        {item.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </Reveal>
      </div>
    </section>
  );
}
