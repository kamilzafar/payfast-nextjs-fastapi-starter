"use client";

/**
 * Dashboard — the billing home page for a signed-in user.
 *
 * Two stacked cards:
 *   1. SubscriptionCard — current plan + status + next bill
 *   2. Recent invoices (last 5) + link to full list
 *
 * We fetch both in parallel inside a single effect. /me/subscription can
 * return null (no sub yet) — that's handled by SubscriptionCard's empty
 * state. /invoices is paginated but we only show the first 5 here; the
 * full list lives at /dashboard/invoices.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { InvoiceTable } from "@/components/invoice-table";
import { SubscriptionCard } from "@/components/subscription-card";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, isApiError } from "@/lib/api-client";
import {
  InvoiceListSchema,
  SubscriptionOutSchema,
  type InvoiceOut,
  type SubscriptionOut,
} from "@/lib/types";

export default function DashboardPage() {
  const router = useRouter();
  const [subscription, setSubscription] = useState<SubscriptionOut | null>(
    null,
  );
  const [invoices, setInvoices] = useState<InvoiceOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [subRaw, invRaw] = await Promise.all([
        api.get<unknown>("/me/subscription"),
        api.get<unknown>("/invoices?limit=5&offset=0"),
      ]);

      const subParsed =
        subRaw === null ? null : SubscriptionOutSchema.parse(subRaw);
      const invParsed = InvoiceListSchema.parse(invRaw);

      setSubscription(subParsed);
      setInvoices(invParsed.items);
    } catch (err) {
      setError(
        isApiError(err)
          ? `Couldn't load your billing info (HTTP ${err.status}).`
          : "Couldn't load your billing info. Please retry.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    // Defer the actual load() call so that setState inside it runs after
    // the effect body returns — keeps react-hooks/set-state-in-effect happy.
    queueMicrotask(() => {
      if (cancelled) return;
      void load();
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const handlePayNow = useCallback(async () => {
    // Find the first open invoice — that's the overdue one for past_due.
    const open = invoices.find((inv) => inv.status === "open");
    if (!open) {
      toast.error("No open invoice to pay.");
      return;
    }
    try {
      // Just route to /checkout/{id} — that page handles the PayFast handshake.
      router.push(`/checkout/${open.id}`);
    } catch (err) {
      toast.error(
        err instanceof ApiError
          ? `Failed to start checkout (HTTP ${err.status}).`
          : "Failed to start checkout.",
      );
    }
  }, [invoices, router]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Something went wrong</CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Billing</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your subscription and invoice history.
        </p>
      </div>

      <SubscriptionCard
        subscription={subscription}
        onPayNow={handlePayNow}
      />

      <Card>
        <CardHeader>
          <CardTitle>Recent invoices</CardTitle>
          <CardDescription>The last 5 charges on this account.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <InvoiceTable items={invoices} />
          {invoices.length > 0 && (
            <div className="pt-1">
              <Link
                href="/dashboard/invoices"
                className="text-sm text-primary underline-offset-4 hover:underline"
              >
                View all invoices
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
