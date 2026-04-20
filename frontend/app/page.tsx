import Link from "next/link";
import { ArrowRight, ShieldCheck, Sparkles, Zap } from "lucide-react";

import { SiteNav } from "@/components/site-nav";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const valueProps = [
  {
    icon: Zap,
    title: "Local rails, global UX",
    body: "Recurring charges via PayFast with a checkout experience Pakistani customers trust.",
  },
  {
    icon: ShieldCheck,
    title: "Built for compliance",
    body: "Card data never touches your servers. Tokenisation, retries, and dunning are handled for you.",
  },
  {
    icon: Sparkles,
    title: "Launch in a weekend",
    body: "Drop in the hosted portal or wire up the API. No lock-in, no enterprise sales call.",
  },
];

export default function LandingPage() {
  return (
    <>
      <SiteNav />
      <main className="flex-1">
        <section className="relative overflow-hidden">
          <div className="mx-auto w-full max-w-6xl px-6 pb-24 pt-20 sm:pt-28">
            <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
              <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-border/70 bg-muted/40 px-3 py-1 text-xs text-muted-foreground">
                <span className="inline-block size-1.5 rounded-full bg-primary" />
                Now accepting early-access teams
              </span>
              <h1 className="text-balance text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
                Subscription billing for Pakistan.{" "}
                <span className="text-muted-foreground">
                  Powered by PayFast.
                </span>
              </h1>
              <p className="mt-6 max-w-2xl text-balance text-base leading-relaxed text-muted-foreground sm:text-lg">
                Ship recurring revenue in days, not quarters. One API for plans,
                subscriptions, invoices, and dunning — tuned for the local
                payments stack.
              </p>
              <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row">
                <Link
                  href="/pricing"
                  className={cn(buttonVariants({ size: "lg" }))}
                >
                  See pricing
                  <ArrowRight className="ml-1 size-4" />
                </Link>
                <Link
                  href="/signup"
                  className={cn(buttonVariants({ size: "lg", variant: "ghost" }))}
                >
                  Create an account
                </Link>
              </div>
            </div>
          </div>
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-72 bg-gradient-to-b from-primary/5 to-transparent"
          />
        </section>

        <section className="border-t border-border/60 bg-muted/20">
          <div className="mx-auto grid w-full max-w-6xl gap-8 px-6 py-20 sm:grid-cols-3">
            {valueProps.map(({ icon: Icon, title, body }) => (
              <div key={title} className="space-y-3">
                <div className="inline-flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </div>
                <h3 className="text-base font-semibold">{title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {body}
                </p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-border/60 py-8">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-2 px-6 text-xs text-muted-foreground sm:flex-row">
          <span>
            &copy; {new Date().getFullYear()} PayFast Billing. All rights reserved.
          </span>
          <span>Made in Pakistan.</span>
        </div>
      </footer>
    </>
  );
}
