"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggle: () => void;
  /** True once the client has adopted the real theme. */
  ready: boolean;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export const THEME_STORAGE_KEY = "js.theme";

/**
 * Runs before first paint (injected into <head> by the root layout) so the page
 * never renders light and then flips. Keep in sync with `resolveTheme` below —
 * this string cannot import anything.
 */
export const THEME_INIT_SCRIPT = `
(function () {
  try {
    var s = localStorage.getItem("${THEME_STORAGE_KEY}");
    var t = s === "light" || s === "dark"
      ? s
      : (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", t);
    document.documentElement.style.colorScheme = t;
  } catch (e) {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
`;

function resolveTheme(): Theme {
  // The init script already decided; trust the DOM so the two can't disagree.
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "dark" || attr === "light") return attr;
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "dark" || stored === "light") return stored;
  } catch {
    /* storage unavailable (private mode, blocked cookies) — fall through */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function apply(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.style.colorScheme = theme;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Server-render as light to match the markup; the init script has already put
  // the correct attribute on <html>, so nothing visible depends on this value.
  const [theme, setTheme] = useState<Theme>("light");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setTheme(resolveTheme());
    setReady(true);
  }, []);

  // Follow the OS only while the user hasn't made an explicit choice.
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mq) return;
    const onChange = (e: MediaQueryListEvent) => {
      try {
        if (window.localStorage.getItem(THEME_STORAGE_KEY)) return;
      } catch {
        /* storage unavailable — follow the OS */
      }
      const next: Theme = e.matches ? "dark" : "light";
      apply(next);
      setTheme(next);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const toggle = () => {
    setTheme((prev) => {
      const next: Theme = prev === "light" ? "dark" : "light";
      apply(next);
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {
        /* preference just won't persist */
      }
      return next;
    });
  };

  return (
    <ThemeContext.Provider value={{ theme, toggle, ready }}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
