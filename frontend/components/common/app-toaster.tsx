"use client";

import { Toaster } from "sonner";
import { useTheme } from "@/providers/theme-provider";

/**
 * Sonner needs to be told the theme explicitly — it reads next-themes context,
 * which this app doesn't use. Without this every toast is a white card in dark
 * mode. Must render inside ThemeProvider.
 */
export function AppToaster() {
  const { theme } = useTheme();
  return <Toaster position="top-right" theme={theme} richColors closeButton />;
}
