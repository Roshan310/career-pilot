import type { Config } from "tailwindcss";

/**
 * Design tokens from docs/FRONTEND.md.
 * Colors reference CSS variables (see globals.css) so a dark theme can be
 * layered on later without touching component code.
 */
const config: Config = {
  darkMode: ["class", '[data-theme="dark"]'],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand — Premium Wine Red
        wine: {
          DEFAULT: "#B4232D",
          500: "#B4232D",
          hover: "#9E1E27",
          pressed: "#851821",
          tint: "#FCEEEF",
        },
        // Semantic surfaces (var-backed for theming)
        background: "var(--color-background)",
        sidebar: "var(--color-sidebar)",
        card: "var(--color-card)",
        border: "var(--color-border)",
        "border-hover": "var(--color-border-hover)",
        divider: "var(--color-divider)",
        hover: "var(--color-hover)",
        // Text
        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "text-muted": "var(--color-text-muted)",
        "text-disabled": "var(--color-text-disabled)",
        // State
        success: { DEFAULT: "#16A34A", bg: "#F0FDF4" },
        warning: { DEFAULT: "#EA580C", bg: "#FFF7ED" },
        error: { DEFAULT: "#DC2626", bg: "#FEF2F2" },
        info: { DEFAULT: "#2563EB", bg: "#EFF6FF" },
      },
      borderRadius: {
        card: "16px",
        btn: "12px",
        input: "12px",
        badge: "999px",
      },
      boxShadow: {
        card: "0 2px 8px rgba(16,24,40,0.04)",
        "card-hover": "0 8px 24px rgba(16,24,40,0.08)",
        modal: "0 24px 48px rgba(16,24,40,0.12)",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Inter", "system-ui", "sans-serif"],
      },
      fontSize: {
        h1: ["40px", { lineHeight: "48px", fontWeight: "700" }],
        h2: ["32px", { lineHeight: "40px", fontWeight: "700" }],
        h3: ["24px", { lineHeight: "32px", fontWeight: "600" }],
        "card-title": ["18px", { lineHeight: "24px", fontWeight: "600" }],
      },
      maxWidth: {
        content: "1280px",
      },
      transitionDuration: {
        DEFAULT: "180ms",
      },
    },
  },
  plugins: [],
};

export default config;
