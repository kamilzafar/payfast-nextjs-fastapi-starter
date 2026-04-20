import { CheckCircle2 } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export const metadata = { title: "Payment successful" };

/**
 * Landing page after PayFast sends the browser back via the success URL.
 * Query params (`basket_id`, `txn_id`, `status`) are populated by the backend's
 * 302 after it reconciles the IPN. We don't call any API here — this page is
 * deliberately public so the redirect works even if PayFast strips the session
 * cookie (no SameSite=None Lax drama).
 */
export default async function CheckoutSuccessPage({
  searchParams,
}: {
  searchParams: Promise<{
    basket_id?: string;
    txn_id?: string;
    status?: string;
  }>;
}) {
  const { basket_id, txn_id } = await searchParams;

  return (
    <Card>
      <CardHeader className="items-center text-center">
        <div className="mx-auto mb-2 flex size-14 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500">
          <CheckCircle2 className="size-8" aria-hidden />
        </div>
        <CardTitle className="text-xl">Payment received</CardTitle>
        <CardDescription>
          Your subscription is active. A receipt is on its way to your inbox.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {txn_id || basket_id ? (
          <dl className="rounded-md border border-border/60 bg-muted/40 p-3 text-xs text-muted-foreground">
            {txn_id ? (
              <div className="flex justify-between gap-4">
                <dt>Transaction</dt>
                <dd className="font-mono text-foreground/80">{txn_id}</dd>
              </div>
            ) : null}
            {basket_id ? (
              <div className="mt-1 flex justify-between gap-4">
                <dt>Basket</dt>
                <dd className="font-mono text-foreground/80">{basket_id}</dd>
              </div>
            ) : null}
          </dl>
        ) : null}
        <p className="text-xs text-muted-foreground">
          If you don&apos;t see your subscription as active within 2 minutes,
          check your email or contact support.
        </p>
      </CardContent>
      <CardFooter>
        <Link
          href="/dashboard"
          className={cn(buttonVariants({ size: "lg" }), "w-full")}
        >
          Go to dashboard
        </Link>
      </CardFooter>
    </Card>
  );
}
