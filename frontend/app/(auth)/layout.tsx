import { Logo } from "@/components/layout/logo";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left: form */}
      <div className="flex flex-col justify-center px-6 py-12 sm:px-12 lg:px-20">
        <div className="mx-auto w-full max-w-sm">
          <Logo className="mb-10" />
          {children}
        </div>
      </div>

      {/* Right: brand panel */}
      <div className="relative hidden overflow-hidden bg-wine lg:block">
        <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)", backgroundSize: "28px 28px" }} />
        <div className="relative flex h-full flex-col justify-center px-16 text-white">
          <h2 className="text-[34px] font-bold leading-tight tracking-tight">
            Land your next role with confidence.
          </h2>
          <p className="mt-4 max-w-md text-[17px] leading-relaxed text-white/80">
            Analyze your resume against any job, close the skill gaps, and walk into every
            interview prepared. CareerPilot turns your job search into a system.
          </p>
          <ul className="mt-10 space-y-4 text-[15px] text-white/90">
            <li className="flex items-center gap-3">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/15">✓</span>
              Multi-signal resume match scoring
            </li>
            <li className="flex items-center gap-3">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/15">✓</span>
              AI-generated gap analysis & rewrites
            </li>
            <li className="flex items-center gap-3">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/15">✓</span>
              Tailored mock-interview practice
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
