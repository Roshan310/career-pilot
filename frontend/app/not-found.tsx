import Link from "next/link";
import { Logo } from "@/components/layout/logo";

export const metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-6 text-center">
      <Logo />
      <p className="mt-8 text-[52px] font-bold leading-none text-text-primary">404</p>
      <h1 className="mt-3 text-[20px] font-semibold text-text-primary">
        We couldn&apos;t find that page
      </h1>
      <p className="mt-2 max-w-md text-[15px] leading-relaxed text-text-secondary">
        The link may be out of date, or the page may have moved.
      </p>
      <Link
        href="/dashboard"
        className="mt-7 inline-flex h-11 items-center justify-center rounded-btn bg-wine px-5 text-[15px] font-medium text-white shadow-sm transition-colors hover:bg-wine-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wine/40"
      >
        Back to Dashboard
      </Link>
    </div>
  );
}
