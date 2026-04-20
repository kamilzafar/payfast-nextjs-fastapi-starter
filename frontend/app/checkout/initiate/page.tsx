"use client";

/**
 * /checkout/initiate?plan={planId}
 *
 * Bridge page used when a user hits "Subscribe" unauthenticated. They're sent
 * to /signup with `returnTo=/checkout/initiate?plan={planId}`, and after
 * signup they land here. We immediately POST /subscriptions on their behalf
 * so they don't have to click Subscribe a second time, then replace the
 * history entry with /checkout/{invoiceId}.
 */

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api, ApiError, isNetworkError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  CreateSubscriptionResponseSchema,
  type CreateSubscriptionRequest,
} from "@/lib/types";
import { cn } from "@/lib/utils";

export default function CheckoutInitiatePage() {
  return (
    <Suspense fallback={<InitiateLoading />}>
      <Initiate />
    </Suspense>
  );
}

function Initiate() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading: authLoading } = useAuth();

  const planParam = searchParams.get("plan");
  const [error, setError] = useState<string | null>(null);

  // Validate the plan param up front so the async `run()` below never calls
  // setError before its first await (keeps react-hooks/set-state-in-effect happy).
  const planIdNumeric = planParam !== null ? Number(planParam) : Number.NaN;
  const planParamValid =
    planParam !== null &&
    Number.isFinite(planIdNumeric) &&
    Number.isInteger(planIdNumeric);

  const run = useCallback(
    async (planId: number) => {
      try {
        const raw = await api.post<unknown, CreateSubscriptionRequest>(
          "/subscriptions",
          { plan_id: planId },
        );
        const parsed = CreateSubscriptionResponseSchema.safeParse(raw);
        if (!parsed.success) {
          setError("Unexpected response from /subscriptions.");
          return;
        }
        router.replace(`/checkout/${parsed.data.invoice_id}`);
      } catch (err) {
        if (isNetworkError(err)) {
          setError("Can't reach the billing API. Please try again shortly.");
          return;
        }
        if (err instanceof ApiError) {
          const detail =
            typeof err.body === "object" && err.body && "detail" in err.body
              ? String((err.body as { detail: unknown }).detail)
              : undefined;
          setError(detail ?? `Something went wrong (${err.status}).`);
          return;
        }
        setError(err instanceof Error ? err.message : "Please try again.");
      }
    },
    [router],
  );

  // Guard: if the proxy didn't bounce us and we somehow landed here unauth,
  // send the user to /login with a returnTo pointing back here. Otherwise
  // fire off the subscription request. Validation errors are surfaced via
  // the JSX below so we don't call setState synchronously from the effect.
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      const self = `/checkout/initiate${planParam ? `?plan=${encodeURIComponent(planParam)}` : ""}`;
      router.replace(`/login?returnTo=${encodeURIComponent(self)}`);
      return;
    }
    if (!planParamValid) return;
    let cancelled = false;
    (async () => {
      if (cancelled) return;
      await run(planIdNumeric);
    })();
    return () => {
      cancelled = true;
    };
  }, [authLoading, user, router, planParam, planParamValid, planIdNumeric, run]);

  // Surface validation errors derived from the URL (not setState), plus any
  // errors captured by `run()` once the API call resolves.
  const derivedError = !planParam
    ? "Missing plan. Please pick a plan from the pricing page."
    : !planParamValid
      ? "That plan identifier isn't valid."
      : null;
  const displayError = error ?? derivedError;

  if (displayError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Couldn&apos;t start checkout</CardTitle>
          <CardDescription>{displayError}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 pb-4">
          <Link
            href="/pricing"
            className={cn(buttonVariants({ size: "lg" }), "w-full")}
          >
            Back to pricing
          </Link>
        </CardContent>
      </Card>
    );
  }

  return <InitiateLoading />;
}

function InitiateLoading() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
        <Loader2 className="size-6 animate-spin text-primary" aria-hidden />
        <p className="text-sm text-muted-foreground">Setting up your subscription...</p>
      </CardContent>
    </Card>
  );
}
