import Link from "next/link";
import { Logo } from "@/components/layout/logo";

const COLUMNS = [
  {
    heading: "Product",
    links: [
      { label: "How it works", href: "#how-it-works" },
      { label: "Features", href: "#features" },
      { label: "FAQ", href: "#faq" },
    ],
  },
  {
    heading: "Account",
    links: [
      { label: "Sign in", href: "/login" },
      { label: "Create an account", href: "/register" },
    ],
  },
];

export function LandingFooter() {
  return (
    <footer className="border-t border-border bg-sidebar">
      <div className="mx-auto grid max-w-content gap-12 px-6 py-16 sm:grid-cols-2 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <Logo />
          <p className="mt-4 max-w-[320px] text-[15px] leading-relaxed text-text-secondary">
            Resume matching and AI mock interviews that share the same context, so the practice is
            always about the job you actually want.
          </p>
        </div>

        {COLUMNS.map((column) => (
          <div key={column.heading}>
            <h2 className="text-[13px] font-semibold uppercase tracking-wide text-text-muted">
              {column.heading}
            </h2>
            <ul className="mt-4 space-y-3">
              {column.links.map((link) => (
                <li key={link.label}>
                  {link.href.startsWith("#") ? (
                    <a
                      href={link.href}
                      className="text-[15px] text-text-secondary transition-colors hover:text-text-primary"
                    >
                      {link.label}
                    </a>
                  ) : (
                    <Link
                      href={link.href}
                      className="text-[15px] text-text-secondary transition-colors hover:text-text-primary"
                    >
                      {link.label}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="mx-auto max-w-content px-6">
        <div className="flex flex-col gap-3 border-t border-divider py-7 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-[13px] text-text-muted">
            © {new Date().getFullYear()} CareerPilot. All rights reserved.
          </p>
          <p className="text-[13px] text-text-muted">Built for people mid-job-hunt.</p>
        </div>
      </div>
    </footer>
  );
}
