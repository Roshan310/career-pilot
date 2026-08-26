"use client";

import { useState } from "react";
import Link from "next/link";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useMotionValueEvent, useScroll } from "framer-motion";
import { ArrowRight, Menu, Moon, Sun, X } from "lucide-react";
import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";
import { useTheme } from "@/providers/theme-provider";
import { cn } from "@/lib/utils";

const LINKS = [
  { label: "How it works", href: "#how-it-works" },
  { label: "Features", href: "#features" },
  { label: "FAQ", href: "#faq" },
];

/**
 * A floating bar rather than a full-width one: the page reads as a stack of
 * cards on a tinted ground, and a bar bleeding to both edges would be the only
 * element cutting across it. It narrows slightly once you leave the hero, which
 * is the whole scroll affordance — no shrinking logo, no colour change.
 */
export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, loading } = useAuth();
  const { theme, toggle } = useTheme();
  const { scrollY } = useScroll();

  useMotionValueEvent(scrollY, "change", (y) => setScrolled(y > 32));

  const dark = theme === "dark";

  return (
    <header className="sticky top-0 z-40 px-4 pt-4 sm:px-6">
      <div
        className={cn(
          "mx-auto flex items-center gap-6 rounded-[20px] border border-border bg-card/85 px-4 backdrop-blur-xl transition-all duration-300 sm:px-6",
          scrolled
            ? "h-16 max-w-[980px] shadow-card-hover"
            : "h-[72px] max-w-content shadow-card",
        )}
      >
        <Link href="/" aria-label="CareerPilot home" className="shrink-0">
          <Logo />
        </Link>

        <nav className="hidden flex-1 items-center justify-center gap-1 lg:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-full px-4 py-2 text-[15px] font-medium text-text-secondary transition-colors hover:bg-hover hover:text-text-primary"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2 lg:ml-0">
          <button
            type="button"
            onClick={toggle}
            aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
            className="flex h-10 w-10 items-center justify-center rounded-full text-text-secondary transition-colors hover:bg-hover hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
          >
            {dark ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {/* Reserved width so the bar doesn't twitch when /auth/me resolves. */}
          <div className="hidden min-w-[196px] items-center justify-end gap-2 sm:flex">
            {loading ? null : user ? (
              <Button asChild>
                <Link href="/dashboard">
                  Go to dashboard
                  <ArrowRight size={16} />
                </Link>
              </Button>
            ) : (
              <>
                <Link
                  href="/login"
                  className="rounded-full px-3 py-2 text-[15px] font-medium text-text-secondary transition-colors hover:text-text-primary"
                >
                  Sign in
                </Link>
                <Button asChild>
                  <Link href="/register">
                    Start free
                    <ArrowRight size={16} />
                  </Link>
                </Button>
              </>
            )}
          </div>

          <DialogPrimitive.Root open={menuOpen} onOpenChange={setMenuOpen}>
            <DialogPrimitive.Trigger
              aria-label="Open menu"
              className="flex h-10 w-10 items-center justify-center rounded-full text-text-secondary transition-colors hover:bg-hover hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40 lg:hidden"
            >
              <Menu size={20} />
            </DialogPrimitive.Trigger>
            <DialogPrimitive.Portal>
              <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px]" />
              <DialogPrimitive.Content className="fixed inset-x-4 top-4 z-50 rounded-[20px] border border-border bg-card p-4 shadow-modal focus:outline-none">
                <DialogPrimitive.Title className="sr-only">Menu</DialogPrimitive.Title>
                <div className="flex h-12 items-center justify-between">
                  <Logo />
                  <DialogPrimitive.Close
                    aria-label="Close menu"
                    className="flex h-9 w-9 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-hover hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
                  >
                    <X size={20} />
                  </DialogPrimitive.Close>
                </div>
                <nav className="mt-2 space-y-1">
                  {LINKS.map((link) => (
                    <a
                      key={link.href}
                      href={link.href}
                      onClick={() => setMenuOpen(false)}
                      className="flex h-12 items-center rounded-xl px-4 text-[15px] font-medium text-text-secondary transition-colors hover:bg-hover hover:text-text-primary"
                    >
                      {link.label}
                    </a>
                  ))}
                </nav>
                <div className="mt-4 space-y-2 border-t border-divider pt-4">
                  {user ? (
                    <Button asChild size="lg" className="w-full">
                      <Link href="/dashboard">Go to dashboard</Link>
                    </Button>
                  ) : (
                    <>
                      <Button asChild size="lg" className="w-full">
                        <Link href="/register">Start free</Link>
                      </Button>
                      <Button asChild variant="secondary" size="lg" className="w-full">
                        <Link href="/login">Sign in</Link>
                      </Button>
                    </>
                  )}
                </div>
              </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
          </DialogPrimitive.Root>
        </div>
      </div>
    </header>
  );
}
