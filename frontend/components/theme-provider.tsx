"use client";

/**
 * Thin re-export of next-themes' ThemeProvider. Centralized here so the
 * root layout doesn't need to know about the upstream package, and so we
 * can swap implementations later without touching every call site.
 */

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

export function ThemeProvider({
  children,
  ...props
}: ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
