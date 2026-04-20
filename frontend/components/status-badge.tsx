/**
 * StatusBadge — coloured pill for subscription and invoice states.
 *
 * Keeping both "kinds" in a single component so the colour semantics stay
 * consistent across the dashboard. Colour choices:
 *  - trialing -> indigo  (provisional, getting started)
 *  - active   -> emerald (healthy, paying)
 *  - past_due -> amber   (needs attention, but not terminal)
 *  - canceled -> zinc    (neutral, terminal)
 *  - open     -> amber   (invoice owed)
 *  - paid     -> emerald (invoice done)
 *  - void     -> zinc    (invoice dismissed)
 *
 * We render a plain <span> (not the shadcn Badge component) because the
 * Badge's variant slots don't cover these semantic tones.
 */

import { cn } from "@/lib/utils";

export type SubscriptionStatus =
  | "trialing"
  | "active"
  | "past_due"
  | "canceled";
export type InvoiceStatus = "open" | "paid" | "void";
export type BadgeStatus = SubscriptionStatus | InvoiceStatus;

type Kind = "subscription" | "invoice";

const SUBSCRIPTION_LABELS: Record<SubscriptionStatus, string> = {
  trialing: "Trialing",
  active: "Active",
  past_due: "Past due",
  canceled: "Canceled",
};

const INVOICE_LABELS: Record<InvoiceStatus, string> = {
  open: "Open",
  paid: "Paid",
  void: "Void",
};

const TONE: Record<BadgeStatus, string> = {
  trialing:
    "bg-indigo-50 text-indigo-700 ring-indigo-600/20 dark:bg-indigo-500/10 dark:text-indigo-300 dark:ring-indigo-400/20",
  active:
    "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-400/20",
  past_due:
    "bg-amber-50 text-amber-800 ring-amber-600/30 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-400/20",
  canceled:
    "bg-zinc-100 text-zinc-700 ring-zinc-500/20 dark:bg-zinc-500/10 dark:text-zinc-300 dark:ring-zinc-400/20",
  open: "bg-amber-50 text-amber-800 ring-amber-600/30 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-400/20",
  paid: "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-400/20",
  void: "bg-zinc-100 text-zinc-700 ring-zinc-500/20 dark:bg-zinc-500/10 dark:text-zinc-300 dark:ring-zinc-400/20",
};

export function StatusBadge({
  status,
  kind,
  className,
}: {
  status: BadgeStatus;
  kind: Kind;
  className?: string;
}) {
  const label =
    kind === "subscription"
      ? SUBSCRIPTION_LABELS[status as SubscriptionStatus] ?? String(status)
      : INVOICE_LABELS[status as InvoiceStatus] ?? String(status);

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        TONE[status],
        className,
      )}
    >
      {label}
    </span>
  );
}
