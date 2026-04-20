"use client";

/**
 * CancelSubscriptionDialog — confirmation modal for scheduling cancel.
 *
 * We default to `at_period_end=true` (soft-cancel) per the product spec —
 * users keep what they paid for until the current period ends. The
 * optional feedback textarea is forwarded to the API as an
 * `x-cancel-reason` header; the backend ignores it for now but can
 * persist it once we add a cancellations table.
 */

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

export function CancelSubscriptionDialog({
  open,
  onOpenChange,
  onConfirm,
  periodEnd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (reason: string) => Promise<void>;
  periodEnd?: string | null;
}) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm(reason);
      onOpenChange(false);
      setReason("");
    } finally {
      setSubmitting(false);
    }
  };

  const prettyEnd = periodEnd
    ? new Date(periodEnd).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "the end of your billing period";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Cancel subscription?</DialogTitle>
          <DialogDescription>
            You&apos;ll keep access until {prettyEnd}. After that, your plan
            won&apos;t renew.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="cancel-reason">
            Mind telling us why?{" "}
            <span className="text-muted-foreground">(optional)</span>
          </Label>
          <textarea
            id="cancel-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Too expensive, not using it, found an alternative..."
            className="w-full min-h-20 rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            disabled={submitting}
            onClick={() => onOpenChange(false)}
          >
            Keep subscription
          </Button>
          <Button
            variant="destructive"
            disabled={submitting}
            onClick={handleConfirm}
          >
            {submitting ? (
              <>
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
                Cancelling...
              </>
            ) : (
              "Confirm cancel"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
