"use client";

/**
 * InvoiceTable — reusable list of invoices used on both the dashboard
 * card (last 5) and the full /dashboard/invoices page.
 *
 * Intentionally dumb: takes pre-fetched items. The parent owns pagination
 * state because it may live in different places on different pages (card
 * vs full page).
 */

import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatAmount, type InvoiceOut } from "@/lib/types";

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

export function InvoiceTable({ items }: { items: InvoiceOut[] }) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No invoices yet.
      </p>
    );
  }

  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th className="py-2 pr-4 font-medium">Date</th>
            <th className="py-2 pr-4 font-medium">Amount</th>
            <th className="py-2 pr-4 font-medium">Status</th>
            <th className="py-2 pr-4 font-medium text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((inv) => (
            <tr
              key={inv.id}
              className="border-b border-border/40 last:border-b-0"
            >
              <td className="py-2 pr-4 align-middle">
                {formatDate(inv.created_at)}
              </td>
              <td className="py-2 pr-4 align-middle tabular-nums">
                {formatAmount(inv.amount_minor, inv.currency)}
              </td>
              <td className="py-2 pr-4 align-middle">
                <StatusBadge status={inv.status} kind="invoice" />
              </td>
              <td className="py-2 pr-4 text-right align-middle">
                {inv.status === "open" ? (
                  <Link
                    href={`/checkout/${inv.id}`}
                    className={cn(
                      buttonVariants({ size: "sm", variant: "outline" }),
                    )}
                  >
                    Pay
                  </Link>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
