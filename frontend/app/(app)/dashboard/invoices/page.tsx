"use client";

/**
 * Full invoice history. Paginated server-side at limit=20 so we only
 * ever render a bounded list, even for long-lived accounts. Prev is
 * disabled when offset===0; Next is disabled when we've reached `total`.
 */

import { useCallback, useEffect, useState } from "react";

import { InvoiceTable } from "@/components/invoice-table";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, isApiError } from "@/lib/api-client";
import { InvoiceListSchema, type InvoiceOut } from "@/lib/types";

const PAGE_SIZE = 20;

export default function InvoicesPage() {
  const [items, setItems] = useState<InvoiceOut[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (nextOffset: number) => {
    setLoading(true);
    setError(null);
    try {
      const raw = await api.get<unknown>(
        `/invoices?limit=${PAGE_SIZE}&offset=${nextOffset}`,
      );
      const parsed = InvoiceListSchema.parse(raw);
      setItems(parsed.items);
      setTotal(parsed.total);
      setOffset(nextOffset);
    } catch (err) {
      setError(
        isApiError(err)
          ? `Couldn't load invoices (HTTP ${err.status}).`
          : "Couldn't load invoices. Please retry.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      void load(0);
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const canPrev = offset > 0;
  const canNext = offset + items.length < total;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Invoices</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your complete billing history.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All invoices</CardTitle>
          <CardDescription>
            Showing {items.length === 0 ? 0 : offset + 1}
            &ndash;{offset + items.length} of {total}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : (
            <InvoiceTable items={items} />
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              disabled={!canPrev || loading}
              onClick={() => void load(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!canNext || loading}
              onClick={() => void load(offset + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
