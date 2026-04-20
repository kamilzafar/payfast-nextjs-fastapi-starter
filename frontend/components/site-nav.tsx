"use client";

/**
 * Top navigation used across marketing and authed surfaces.
 *
 * The authed layout owns the user dropdown; this component focuses on the
 * shared shell (logo, public links, theme toggle). An authed variant is
 * composed on top for the (app) routes.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, Settings, User as UserIcon } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

function Logo() {
  return (
    <Link
      href="/"
      className="flex items-center gap-2 text-base font-semibold tracking-tight"
    >
      <span className="inline-block size-6 rounded-md bg-primary" />
      PayFast Billing
    </Link>
  );
}

export function SiteNav({ variant = "public" }: { variant?: "public" | "app" }) {
  const router = useRouter();
  const { user, logout } = useAuth();

  const initial = user?.name?.[0]?.toUpperCase() ?? user?.email[0]?.toUpperCase() ?? "?";

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <Logo />
          {variant === "app" ? (
            <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
              <Link
                href="/dashboard"
                className="transition-colors hover:text-foreground"
              >
                Dashboard
              </Link>
              <Link
                href="/dashboard/invoices"
                className="transition-colors hover:text-foreground"
              >
                Invoices
              </Link>
              <Link
                href="/settings"
                className="transition-colors hover:text-foreground"
              >
                Settings
              </Link>
            </nav>
          ) : (
            <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
              <Link
                href="/pricing"
                className="transition-colors hover:text-foreground"
              >
                Pricing
              </Link>
            </nav>
          )}
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          {variant === "public" ? (
            user ? (
              <Link
                href="/dashboard"
                className={cn(buttonVariants({ size: "sm" }))}
              >
                Dashboard
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className={cn(
                    buttonVariants({ size: "sm", variant: "ghost" }),
                  )}
                >
                  Log in
                </Link>
                <Link
                  href="/signup"
                  className={cn(buttonVariants({ size: "sm" }))}
                >
                  Sign up
                </Link>
              </>
            )
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger
                aria-label="Open user menu"
                className="inline-flex size-9 items-center justify-center rounded-full outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Avatar className="size-8">
                  <AvatarFallback className="text-xs font-medium">
                    {initial}
                  </AvatarFallback>
                </Avatar>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="flex flex-col">
                  <span className="text-sm font-medium">
                    {user?.name ?? "Account"}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {user?.email}
                  </span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => router.push("/dashboard")}>
                  <UserIcon className="mr-2 size-4" /> Dashboard
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => router.push("/settings")}>
                  <Settings className="mr-2 size-4" /> Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={async () => {
                    await logout();
                    router.push("/login");
                  }}
                >
                  <LogOut className="mr-2 size-4" /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </header>
  );
}
