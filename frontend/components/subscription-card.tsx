"use client";

/**
 * SubscriptionCard — renders the "Current Subscription" block on the
 * dashboard. Handles all five states:
 *   - null                         -> empty, with CTA to /pricing
 *   - trialing / active            -> normal "renews on ..."
 *   - past_due                     -> alert banner + "Pay now" button
 *   - cancel_at_period_end (true)  -> "ends on ..." instead of renews
 *   - canceled                     -> read-only "subscription is canceled"
 *
 * The `onPayNow` callback is optional so the component is easy to unit-test
 * without wiring the full api client; when undefined we still render the
 * button but no-op on click.
 */

import Link from "next/link";
import { AlertTriangle } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { formatAmount, type SubscriptionOut } from "@/lib/types";

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
}

export function SubscriptionCard({
  subscription,
  onPayNow,
}: {
  subscription: SubscriptionOut | null;
  onPayNow?: () => void;
}) {
  if (!subscription) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Current subscription</CardTitle>
          <CardDescription>
            You&apos;re not subscribed yet. Start with the plan that fits.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link
            href="/pricing"
            className={cn(buttonVariants({ size: "sm" }))}
          >
            See plans
          </Link>
        </CardContent>
      </Card>
    );
  }

  const { plan, status } = subscription;
  const price = formatAmount(plan.amount_minor, plan.currency);
  const endsOrRenews =
    status === "canceled" || subscription.cancel_at_period_end
      ? `Ends on ${formatDate(subscription.current_period_end)}`
      : `Renews on ${formatDate(subscription.current_period_end)}`;

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            {plan.name}
            <StatusBadge status={status} kind="subscription" />
          </CardTitle>
          <CardDescription>
            {price} / {plan.interval === "yearly" ? "year" : "month"}
          </CardDescription>
        </div>
        <Link
          href="/settings"
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          Manage
        </Link>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {status === "past_due" && (
          <div className="flex items-start gap-3 rounded-md border border-amber-600/30 bg-amber-50 p-3 text-amber-900 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-200">
            <AlertTriangle
              className="mt-0.5 size-5 shrink-0"
              aria-hidden
            />
            <div className="flex-1 space-y-2">
              <p className="font-medium">Your last payment failed.</p>
              <p className="text-sm text-amber-900/90 dark:text-amber-200/90">
                Pay your overdue invoice to reactivate your subscription.
              </p>
              <Button size="sm" onClick={onPayNow}>
                Pay now
              </Button>
            </div>
          </div>
        )}

        {status === "canceled" && (
          <p className="text-muted-foreground">
            Your subscription is canceled.
          </p>
        )}

        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
          <dt className="text-muted-foreground">
            {subscription.cancel_at_period_end || status === "canceled"
              ? "Ends"
              : "Renews"}
          </dt>
          <dd>{endsOrRenews.replace(/^(Renews on|Ends on) /, "")}</dd>

          {subscription.next_billing_at && status !== "canceled" && (
            <>
              <dt className="text-muted-foreground">Next billing</dt>
              <dd>{formatDate(subscription.next_billing_at)}</dd>
            </>
          )}
        </dl>
        <p className="sr-only">{endsOrRenews}</p>
      </CardContent>
    </Card>
  );
}
