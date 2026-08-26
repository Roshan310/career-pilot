import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProductShot } from "./product-shot";

/**
 * One promise, one action. The badge names the two modules so the headline
 * doesn't have to carry the product category as well as the hook.
 *
 * Everything here is a server component staggered with `.landing-rise` rather
 * than the `Reveal` used further down the page — see the note on that keyframe
 * in globals.css for why the fold is the one place that can't wait for JS.
 */
export function Hero() {
  return (
    <section className="relative isolate overflow-hidden pb-24 pt-16 sm:pt-24">
      <div aria-hidden className="landing-grid pointer-events-none absolute inset-x-0 top-0 -z-20 h-[760px]" />
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[-320px] -z-10 h-[640px] w-[1100px] -translate-x-1/2 rounded-full bg-wine/10 blur-[130px]"
      />

      <div className="mx-auto max-w-[880px] px-6 text-center">
        <div className="landing-rise">
          <span className="inline-flex items-center gap-2 rounded-badge border border-border bg-card px-4 py-1.5 text-[13px] font-medium text-text-secondary shadow-card">
            <Sparkles size={14} className="text-wine-fg" />
            Resume matching and AI mock interviews, in one place
          </span>
        </div>

        <h1
          className="landing-rise mt-7 text-[42px] font-bold leading-[1.06] tracking-[-0.03em] text-text-primary sm:text-[60px] lg:text-[68px]"
          style={{ animationDelay: "80ms" }}
        >
          Find out why you&apos;re not
          <br className="hidden sm:block" /> getting <span className="text-wine-fg">callbacks</span>
        </h1>

        <p
          className="landing-rise mx-auto mt-6 max-w-[620px] text-[17px] leading-[1.65] text-text-secondary sm:text-[19px]"
          style={{ animationDelay: "160ms" }}
        >
          CareerPilot scores your resume against the exact job you&apos;re applying to, shows you
          which gaps cost you the match, then interviews you out loud on those same gaps.
        </p>

        <div
          className="landing-rise mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row"
          style={{ animationDelay: "240ms" }}
        >
          <Button asChild size="lg" className="w-full sm:w-auto">
            <Link href="/register">
              Start free
              <ArrowRight size={18} />
            </Link>
          </Button>
          <Button asChild variant="secondary" size="lg" className="w-full sm:w-auto">
            <a href="#how-it-works">See how it works</a>
          </Button>
        </div>

        <p className="landing-rise mt-6 text-[13px] text-text-muted" style={{ animationDelay: "300ms" }}>
          Free to start · No card required · Runs in any browser
        </p>
      </div>

      <ProductShot />
    </section>
  );
}
