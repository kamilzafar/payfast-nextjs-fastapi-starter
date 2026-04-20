"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";

// `useSyncExternalStore` gives us a hydration-safe "have we mounted?" bit
// without tripping the react-hooks/set-state-in-effect rule.
const subscribe = () => () => {};
const getSnapshot = () => true;
const getServerSnapshot = () => false;

/**
 * Compact dark-mode toggle. Renders a neutral icon during SSR to avoid a
 * hydration mismatch from the unknown theme, then swaps to the resolved
 * theme's icon on the client.
 */
export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const mounted = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );

  const current = theme === "system" ? resolvedTheme : theme;
  const nextTheme = current === "dark" ? "light" : "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Toggle theme"
      onClick={() => setTheme(nextTheme)}
      className="h-9 w-9"
    >
      {mounted && current === "dark" ? (
        <Sun className="size-4" />
      ) : (
        <Moon className="size-4" />
      )}
    </Button>
  );
}
