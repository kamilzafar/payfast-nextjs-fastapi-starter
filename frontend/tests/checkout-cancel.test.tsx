import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// next/link renders as a plain anchor in jsdom — avoids router internals.
vi.mock("next/link", () => ({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  default: ({ href, children, ...rest }: any) => (
    <a href={typeof href === "string" ? href : "#"} {...rest}>
      {children}
    </a>
  ),
}));

import CheckoutCancelPage from "@/app/checkout/cancel/page";

describe("Checkout cancel page", () => {
  it("renders the cancellation copy and both navigation actions", () => {
    render(<CheckoutCancelPage />);

    // CardTitle renders as a styled <div>, not a heading element, so we
    // assert on the visible text.
    expect(screen.getByText(/payment cancelled/i)).toBeInTheDocument();
    expect(screen.getByText(/no charge was made/i)).toBeInTheDocument();

    const tryAgain = screen.getByRole("link", { name: /try again/i });
    expect(tryAgain).toHaveAttribute("href", "/pricing");

    const dashboard = screen.getByRole("link", { name: /back to dashboard/i });
    expect(dashboard).toHaveAttribute("href", "/dashboard");
  });
});
