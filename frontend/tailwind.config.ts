import type { Config } from "tailwindcss";

/**
 * Design tokens from docs/FRONTEND.md.
 *
 * Every color resolves through a CSS variable defined for BOTH themes in
 * globals.css. The `rgb(var(--x) / <alpha-value>)` form is what lets an alpha
 * modifier work (`bg-wine/10`, `ring-wine/40`, `bg-background/80`); a bare
 * `var(--x)` makes Tailwind drop the modifier and emit nothing.
 */
const withAlpha = (v: string) => `rgb(var(${v}) / <alpha-value>)`;

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
        // Brand — Premium Wine Red.
        // `wine` = solid fill under white text. `wine.fg` = brand red as text or
        // icon on a surface. Identical in light, deliberately different in dark.
        wine: {
          DEFAULT: withAlpha("--color-wine"),
          500: withAlpha("--color-wine"),
          hover: withAlpha("--color-wine-hover"),
          pressed: withAlpha("--color-wine-pressed"),
          fg: withAlpha("--color-wine-fg"),
          tint: withAlpha("--color-wine-tint"),
        },
        // Semantic surfaces
        background: withAlpha("--color-background"),
        sidebar: withAlpha("--color-sidebar"),
        card: withAlpha("--color-card"),
        border: withAlpha("--color-border"),
        "border-hover": withAlpha("--color-border-hover"),
        divider: withAlpha("--color-divider"),
        hover: withAlpha("--color-hover"),
        // Text
        "text-primary": withAlpha("--color-text-primary"),
        "text-secondary": withAlpha("--color-text-secondary"),
        "text-muted": withAlpha("--color-text-muted"),
        "text-disabled": withAlpha("--color-text-disabled"),
        // State
        success: { DEFAULT: withAlpha("--color-success"), bg: withAlpha("--color-success-bg") },
        warning: { DEFAULT: withAlpha("--color-warning"), bg: withAlpha("--color-warning-bg") },
        error: { DEFAULT: withAlpha("--color-error"), bg: withAlpha("--color-error-bg") },
        info: { DEFAULT: withAlpha("--color-info"), bg: withAlpha("--color-info-bg") },
        // Progress-ring track
        "ring-track": withAlpha("--color-ring-track"),
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
