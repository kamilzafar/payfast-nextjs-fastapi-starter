"use client";

/**
 * /checkout/[invoiceId]
 *
 * This page is the hop between "user clicked Subscribe" and "user is on
 * PayFast's payment page". We deliberately don't try to render anything
 * billing-specific here — the user should see a one-beat loading state and
 * then have their browser POSTed away to PayFast. Everything is designed so
 * that if JS dies, they can still click their way through manually.
 *
 * Flow:
 *   1. Wait for auth context to settle; if unauth, bounce to /login with
 *      returnTo so they come back here.
 *   2. POST /invoices/{id}/checkout to get { action_url, fields }.
 *   3. Render a hidden form with the signed fields and submit it via a ref.
 *   4. If auto-submit hasn't fired within 5s, show a manual "Continue to
 *      PayFast" button as a fallback.
 */

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
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
  InvoiceCheckoutResponseSchema,
  type InvoiceCheckoutResponse,
} from "@/lib/types";

type ViewState =
  | { kind: "loading" }
  | { kind: "ready"; spec: InvoiceCheckoutResponse }
  | { kind: "error"; title: string; message: string };

export default function CheckoutRedirectPage() {
  const rawParams = useParams();
  const rawInvoiceId = rawParams?.invoiceId;
  const invoiceId = Array.isArray(rawInvoiceId)
    ? (rawInvoiceId[0] ?? "")
    : (rawInvoiceId ?? "");
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();

  const [view, setView] = useState<ViewState>({ kind: "loading" });
  const [showManualFallback, setShowManualFallback] = useState(false);
  const submittedRef = useRef(false);
  const formRef = useRef<HTMLFormElement | null>(null);

  // Pure fetch — no synchronous setState before the first await, so it's
  // safe to call from an effect without tripping react-hooks/set-state-in-effect.
  // Callers that want to reset to a loading state should call resetToLoading()
  // first.
  const fetchCheckout = useCallback(async () => {
    try {
      const raw = await api.post<unknown>(
        `/invoices/${encodeURIComponent(invoiceId)}/checkout`,
      );
      const parsed = InvoiceCheckoutResponseSchema.safeParse(raw);
      if (!parsed.success) {
        setView({
          kind: "error",
          title: "Unexpected response",
          message:
            "The billing API returned something we didn't recognise. Please try again or contact support.",
        });
        return;
      }
      setView({ kind: "ready", spec: parsed.data });
    } catch (err) {
      if (isNetworkError(err)) {
        setView({
          kind: "error",
          title: "Can't reach the server",
          message:
            "We couldn't reach the billing API. Check your connection and try again.",
        });
        return;
      }
      if (err instanceof ApiError) {
        const detail =
          typeof err.body === "object" && err.body && "detail" in err.body
            ? String((err.body as { detail: unknown }).detail)
            : undefined;
        // Human-friendly wording for the common cases; fall back to server detail.
        const message =
          err.status === 404
            ? "We couldn't find that invoice. It may have been cancelled."
            : err.status === 409
              ? "This invoice has already been paid."
              : (detail ?? `Something went wrong (${err.status}).`);
        setView({
          kind: "error",
          title: "Checkout unavailable",
          message,
        });
        return;
      }
      setView({
        kind: "error",
        title: "Unexpected error",
        message: err instanceof Error ? err.message : "Please try again.",
      });
    }
  }, [invoiceId]);

  // Auth gate: bounce to /login if we know the user isn't signed in.
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      const returnTo = `/checkout/${invoiceId}`;
      router.replace(`/login?returnTo=${encodeURIComponent(returnTo)}`);
    }
  }, [authLoading, user, router, invoiceId]);

  // Kick the API call once auth is settled and we have a user.
  useEffect(() => {
    if (authLoading || !user || !invoiceId) return;
    let cancelled = false;
    (async () => {
      if (cancelled) return;
      await fetchCheckout();
    })();
    return () => {
      cancelled = true;
    };
  }, [authLoading, user, invoiceId, fetchCheckout]);

  // Auto-submit the hidden form once it renders with the PayFast fields.
  useEffect(() => {
    if (view.kind !== "ready") return;
    if (submittedRef.current) return;
    const form = formRef.current;
    if (!form) return;
    submittedRef.current = true;
    // requestSubmit runs validation; PayFast fields are all hidden so this is
    // equivalent to .submit() but plays nicer with any future interceptors.
    try {
      form.requestSubmit();
    } catch {
      form.submit();
    }
  }, [view]);

  // Manual fallback: if auto-submit hasn't completed after 5s (e.g. popup
  // blocker, JS error), expose a visible button so the user can finish the
  // handoff themselves.
  useEffect(() => {
    if (view.kind !== "ready") return;
    const t = setTimeout(() => setShowManualFallback(true), 5000);
    return () => clearTimeout(t);
  }, [view]);

  if (authLoading || !user) {
    return <CheckoutLoading label="Checking your session..." />;
  }

  if (view.kind === "loading") {
    return <CheckoutLoading label="Preparing secure checkout..." />;
  }

  if (view.kind === "error") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{view.title}</CardTitle>
          <CardDescription>{view.message}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 pb-4">
          <Button
            onClick={() => {
              setView({ kind: "loading" });
              void fetchCheckout();
            }}
          >
            Try again
          </Button>
          <Link
            href="/dashboard"
            className="text-center text-sm text-muted-foreground underline-offset-4 hover:underline"
          >
            Back to billing
          </Link>
        </CardContent>
      </Card>
    );
  }

  // view.kind === "ready"
  const { action_url, fields } = view.spec;
  return (
    <div className="space-y-6">
      <CheckoutLoading label="Redirecting to PayFast..." />

      {showManualFallback ? (
        <div className="rounded-lg border border-border/60 bg-card p-4 text-center text-sm">
          <p className="mb-3 text-muted-foreground">
            Still here? Tap the button below to finish your payment.
          </p>
          <Button
            onClick={() => formRef.current?.submit()}
            className="w-full"
          >
            Continue to PayFast
          </Button>
        </div>
      ) : null}

      {/*
        Hidden auto-post form. Must live in the DOM so requestSubmit() can fire
        it — aria-hidden keeps it out of the AT tree.
      */}
      <form
        ref={formRef}
        action={action_url}
        method="POST"
        className="hidden"
        aria-hidden="true"
      >
        {Object.entries(fields).map(([name, value]) => (
          <input key={name} type="hidden" name={name} value={value} />
        ))}
      </form>
    </div>
  );
}

function CheckoutLoading({ label }: { label: string }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
        <Loader2 className="size-6 animate-spin text-primary" aria-hidden />
        <p className="text-sm text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}
