import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import { QueryProvider } from "@/providers/query-provider";
import { AuthProvider } from "@/providers/auth-provider";
import { ThemeProvider, THEME_INIT_SCRIPT } from "@/providers/theme-provider";
import { AppToaster } from "@/components/common/app-toaster";

export const metadata: Metadata = {
  title: {
    default: "CareerPilot — AI Resume Matcher & Interview Practice",
    // Per-route layouts set only their own name; this frames it.
    template: "%s · CareerPilot",
  },
  description: "Analyze your resume against any job, close the gaps, and practice with AI.",
  applicationName: "CareerPilot",
};

export const viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fafafa" },
    { media: "(prefers-color-scheme: dark)", color: "#0d0d0f" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={GeistSans.variable} suppressHydrationWarning>
      <head>
        {/* Before first paint, or dark-mode users get a white flash on every load. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="font-sans antialiased">
        <ThemeProvider>
          <QueryProvider>
            <AuthProvider>{children}</AuthProvider>
          </QueryProvider>
          <AppToaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
