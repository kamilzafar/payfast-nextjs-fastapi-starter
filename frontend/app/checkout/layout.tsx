import type { ReactNode } from "react";

/**
 * Checkout layout — no site nav, no distractions. The user is mid-payment and
 * every extra link is a chance to abandon. Success and cancel live under this
 * same tree so the visual transition back from PayFast feels contiguous.
 */
export default function CheckoutLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen flex-1 items-center justify-center bg-muted/20 px-6 py-10">
      <div className="w-full max-w-lg">{children}</div>
    </main>
  );
}
