"use client";

/**
 * Settings — three sections:
 *   1. Account (read-only for phase 4)
 *   2. Subscription — shows status, lets the user schedule a cancel
 *   3. Danger zone — placeholder for phase 5+
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { CancelSubscriptionDialog } from "@/components/cancel-subscription-dialog";
import { StatusBadge } from "@/components/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, isApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import {
  SubscriptionOutSchema,
  formatAmount,
  type SubscriptionOut,
} from "@/lib/types";

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

export default function SettingsPage() {
  const { user } = useAuth();
  const [subscription, setSubscription] = useState<SubscriptionOut | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const raw = await api.get<unknown>("/me/subscription");
      setSubscription(raw === null ? null : SubscriptionOutSchema.parse(raw));
    } catch (err) {
      setError(
        isApiError(err)
          ? `Couldn't load subscription (HTTP ${err.status}).`
          : "Couldn't load subscription.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      void load();
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const handleConfirmCancel = useCallback(
    async (reason: string) => {
      if (!subscription) return;
      try {
        const raw = await api.post<unknown>(
          `/subscriptions/${subscription.id}/cancel`,
          { at_period_end: true },
          reason
            ? { headers: { "x-cancel-reason": reason } }
            : undefined,
        );
        const parsed = SubscriptionOutSchema.parse(raw);
        setSubscription(parsed);
        toast.success(
          `Cancellation scheduled for ${formatDate(
            parsed.current_period_end,
          )}`,
        );
      } catch (err) {
        toast.error(
          err instanceof ApiError
            ? `Cancellation failed (HTTP ${err.status}).`
            : "Cancellation failed.",
        );
      }
    },
    [subscription],
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Account, subscription, and danger-zone controls.
        </p>
      </div>

      {/* --- Account --- */}
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>
            Edit profile coming soon — read-only for now.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="grid grid-cols-[8rem_1fr] gap-y-1">
            <div className="text-muted-foreground">Email</div>
            <div>{user?.email ?? "—"}</div>
            <div className="text-muted-foreground">Name</div>
            <div>{user?.name ?? "—"}</div>
            <div className="text-muted-foreground">Phone</div>
            <div>{user?.phone ?? "—"}</div>
          </div>
        </CardContent>
      </Card>

      {/* --- Subscription --- */}
      <Card>
        <CardHeader>
          <CardTitle>Subscription</CardTitle>
          <CardDescription>
            Manage your current plan.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {loading ? (
            <Skeleton className="h-16 w-full" />
          ) : error ? (
            <p className="text-destructive">{error}</p>
          ) : !subscription ? (
            <p className="text-muted-foreground">No active subscription.</p>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">{subscription.plan.name}</div>
                  <div className="text-muted-foreground">
                    {formatAmount(
                      subscription.plan.amount_minor,
                      subscription.plan.currency,
                    )}{" "}
                    /{" "}
                    {subscription.plan.interval === "yearly"
                      ? "year"
                      : "month"}
                  </div>
                </div>
                <StatusBadge
                  status={subscription.status}
                  kind="subscription"
                />
              </div>
              <div className="grid grid-cols-[8rem_1fr] gap-y-1 pt-2">
                <div className="text-muted-foreground">
                  {subscription.cancel_at_period_end ||
                  subscription.status === "canceled"
                    ? "Ends on"
                    : "Renews on"}
                </div>
                <div>{formatDate(subscription.current_period_end)}</div>
              </div>
            </>
          )}
        </CardContent>
        {subscription && (
          <CardFooter className="flex flex-wrap gap-2">
            {subscription.status === "canceled" ? (
              <Link
                href="/pricing"
                className={cn(buttonVariants({ size: "sm" }))}
              >
                Re-subscribe
              </Link>
            ) : subscription.cancel_at_period_end ? (
              <Button
                size="sm"
                variant="outline"
                disabled
                title="Contact support to resume"
              >
                Resume subscription
              </Button>
            ) : (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => setDialogOpen(true)}
              >
                Cancel subscription
              </Button>
            )}
          </CardFooter>
        )}
      </Card>

      {/* --- Danger zone --- */}
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="text-destructive">Danger zone</CardTitle>
          <CardDescription>
            Irreversible account actions. Not available yet.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button size="sm" variant="destructive" disabled>
            Delete account
          </Button>
        </CardContent>
      </Card>

      <CancelSubscriptionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onConfirm={handleConfirmCancel}
        periodEnd={subscription?.current_period_end ?? null}
      />
    </div>
  );
}
