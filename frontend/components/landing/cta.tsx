import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Reveal } from "./reveal";

/**
 * The panel keeps the wine fill in both themes — it is the one place on the page
 * that is unambiguously brand, and letting it flip to a dark surface would make
 * the end of the page trail off exactly where it should land.
 */
export function LandingCta() {
  return (
    <section className="px-6 pb-24 sm:pb-32">
      <Reveal className="mx-auto max-w-content">
        <div className="relative overflow-hidden rounded-[32px] bg-gradient-to-br from-wine via-wine to-wine-pressed px-8 py-16 sm:px-16 sm:py-20">
          <div
            aria-hidden
            className="pointer-events-none absolute -right-24 -top-24 h-[420px] w-[420px] rounded-full bg-white/10 blur-3xl"
          />
          <div className="relative flex flex-col items-start gap-10 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-[560px]">
              <h2 className="text-[32px] font-bold leading-[1.15] tracking-[-0.02em] text-white sm:text-[42px]">
                The next interview is the one that counts
              </h2>
              <p className="mt-4 text-[17px] leading-relaxed text-white/80">
                Score a resume against a real posting, close the gaps it finds, and practise the
                questions before someone else asks them.
              </p>
            </div>
            <Link
              href="/register"
              className="inline-flex h-12 shrink-0 items-center gap-2 rounded-btn bg-white px-7 text-[15px] font-semibold text-wine-pressed transition-transform duration-[180ms] hover:scale-[1.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-wine active:scale-[0.99]"
            >
              Start free
              <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
