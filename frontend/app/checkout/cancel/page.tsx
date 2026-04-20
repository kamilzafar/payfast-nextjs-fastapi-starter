import { XCircle } from "lucide-react";
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

export const metadata = { title: "Payment cancelled" };

/**
 * Landing page after a user cancels on PayFast. No state changes here —
 * reconciliation happens via IPN. This page is deliberately public and
 * static so it works even if the session cookie didn't survive the
 * round-trip.
 */
export default function CheckoutCancelPage() {
  return (
    <Card>
      <CardHeader className="items-center text-center">
        <div className="mx-auto mb-2 flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <XCircle className="size-8" aria-hidden />
        </div>
        <CardTitle className="text-xl">Payment cancelled</CardTitle>
        <CardDescription>
          No charge was made. You can try again whenever you&apos;re ready.
        </CardDescription>
      </CardHeader>
      <CardContent className="text-center text-sm text-muted-foreground">
        If you ran into an issue on the payment page, your card provider may
        have more context in a recent transaction alert.
      </CardContent>
      <CardFooter className="flex flex-col gap-2">
        <Link
          href="/pricing"
          className={cn(buttonVariants({ size: "lg" }), "w-full")}
        >
          Try again
        </Link>
        <Link
          href="/dashboard"
          className={cn(
            buttonVariants({ size: "lg", variant: "ghost" }),
            "w-full",
          )}
        >
          Back to dashboard
        </Link>
      </CardFooter>
    </Card>
  );
}
