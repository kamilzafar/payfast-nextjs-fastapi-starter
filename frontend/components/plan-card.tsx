"use client";

import { Check } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api, ApiError, isNetworkError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  CreateSubscriptionResponseSchema,
  formatAmount,
  type CreateSubscriptionRequest,
  type Plan,
} from "@/lib/types";

export function PlanCard({
  plan,
  featured = false,
}: {
  plan: Plan;
  featured?: boolean;
}) {
  const router = useRouter();
  const { user } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const handleSubscribe = async () => {
    if (!user) {
      // Bounce through signup, then deep-link back into /checkout/initiate so
      // the user doesn't have to re-click Subscribe after creating an account.
      const returnTo = `/checkout/initiate?plan=${encodeURIComponent(plan.id)}`;
      router.push(
        `/signup?plan=${encodeURIComponent(plan.id)}&returnTo=${encodeURIComponent(returnTo)}`,
      );
      return;
    }

    // Plan.id is modelled as a string in the public catalogue schema, but the
    // subscriptions endpoint takes an integer primary key. Coerce here; the
    // backend plans table uses sequential int ids.
    const planIdNumeric = Number(plan.id);
    if (!Number.isFinite(planIdNumeric) || !Number.isInteger(planIdNumeric)) {
      toast.error("Couldn't start checkout", {
        description: "This plan has an invalid identifier. Please contact support.",
      });
      return;
    }

    setSubmitting(true);
    try {
      const raw = await api.post<unknown, CreateSubscriptionRequest>(
        "/subscriptions",
        { plan_id: planIdNumeric },
      );
      const parsed = CreateSubscriptionResponseSchema.safeParse(raw);
      if (!parsed.success) {
        throw new Error("Unexpected response from /subscriptions");
      }
      router.push(`/checkout/${parsed.data.invoice_id}`);
    } catch (err) {
      if (isNetworkError(err)) {
        toast.error("Can't reach the server", {
          description:
            "The billing API isn't responding. Check your connection or try again shortly.",
        });
      } else if (err instanceof ApiError) {
        const detail =
          typeof err.body === "object" && err.body && "detail" in err.body
            ? String((err.body as { detail: unknown }).detail)
            : undefined;
        toast.error("Couldn't start checkout", {
          description: detail ?? `Something went wrong (${err.status}).`,
        });
      } else {
        toast.error("Couldn't start checkout", {
          description:
            err instanceof Error ? err.message : "Please try again.",
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const cadence = plan.interval_count === 1
    ? `/${plan.interval}`
    : `/ ${plan.interval_count} ${plan.interval}s`;

  return (
    <Card
      className={
        featured
          ? "relative border-primary/50 shadow-lg ring-1 ring-primary/20"
          : "relative"
      }
    >
      {featured ? (
        <Badge className="absolute -top-3 right-6">Most popular</Badge>
      ) : null}
      <CardHeader>
        <CardTitle className="text-xl">{plan.name}</CardTitle>
        {plan.description ? (
          <CardDescription>{plan.description}</CardDescription>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-semibold tracking-tight">
            {formatAmount(plan.amount_minor, plan.currency)}
          </span>
          <span className="text-sm text-muted-foreground">{cadence}</span>
        </div>
        {plan.features.length > 0 ? (
          <ul className="space-y-2 text-sm">
            {plan.features.map((feature) => (
              <li key={feature} className="flex items-start gap-2">
                <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                <span className="text-foreground/90">{feature}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
      <CardFooter>
        <Button
          className="w-full"
          onClick={handleSubscribe}
          disabled={submitting}
        >
          {submitting ? "Starting checkout..." : "Subscribe"}
        </Button>
      </CardFooter>
    </Card>
  );
}
