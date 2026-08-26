import { LandingNav } from "@/components/landing/landing-nav";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { Features } from "@/components/landing/features";
import { Faq } from "@/components/landing/faq";
import { LandingCta } from "@/components/landing/cta";
import { LandingFooter } from "@/components/landing/landing-footer";

/**
 * The marketing page, and the only public route besides /login and /register.
 *
 * This used to be a redirect hop to /dashboard or /login, which meant the
 * product had no front door at all — every link to the app landed a stranger on
 * a sign-in form. Signed-in visitors are not bounced away either: the nav
 * notices the session and offers the dashboard instead of a sign-up button.
 */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only left-4 top-4 z-50 rounded-btn bg-card px-4 py-2 text-[15px] font-medium text-text-primary shadow-modal focus:not-sr-only focus:absolute"
      >
        Skip to content
      </a>
      <LandingNav />
      <main id="main-content">
        <Hero />
        <HowItWorks />
        <Features />
        <Faq />
        <LandingCta />
      </main>
      <LandingFooter />
    </div>
  );
}
