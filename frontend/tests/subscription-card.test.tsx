import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SubscriptionOut } from "@/lib/types";

vi.mock("next/link", () => ({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  default: ({ href, children, ...rest }: any) => (
    <a href={typeof href === "string" ? href : "#"} {...rest}>
      {children}
    </a>
  ),
}));

import { SubscriptionCard } from "@/components/subscription-card";

const basePlan = {
  id: 1,
  name: "Basic",
  amount_minor: 150000,
  currency: "PKR",
  interval: "monthly",
  trial_days: 7,
};

function makeSub(overrides: Partial<SubscriptionOut> = {}): SubscriptionOut {
  return {
    id: 42,
    status: "active",
    current_period_start: "2026-04-01T00:00:00+00:00",
    current_period_end: "2026-06-12T00:00:00+00:00",
    next_billing_at: "2026-06-12T00:00:00+00:00",
    canceled_at: null,
    cancel_at_period_end: false,
    plan: basePlan,
    ...overrides,
  };
}

describe("SubscriptionCard", () => {
  it("renders empty state when subscription is null", () => {
    render(<SubscriptionCard subscription={null} />);
    expect(screen.getByText(/not subscribed/i)).toBeInTheDocument();
    const cta = screen.getByRole("link", { name: /see plans/i });
    expect(cta).toHaveAttribute("href", "/pricing");
  });

  it("renders trialing subscription", () => {
    render(<SubscriptionCard subscription={makeSub({ status: "trialing" })} />);
    expect(screen.getByText(/basic/i)).toBeInTheDocument();
    expect(screen.getByText(/trialing/i)).toBeInTheDocument();
  });

  it("renders active subscription with renews wording", () => {
    render(<SubscriptionCard subscription={makeSub({ status: "active" })} />);
    expect(screen.getByText(/basic/i)).toBeInTheDocument();
    expect(screen.getByText(/renews on/i)).toBeInTheDocument();
  });

  it("renders past_due with a pay-now alert", () => {
    render(<SubscriptionCard subscription={makeSub({ status: "past_due" })} />);
    expect(screen.getByText(/last payment failed/i)).toBeInTheDocument();
    // Pay now button should be present
    expect(screen.getByRole("button", { name: /pay now/i })).toBeInTheDocument();
  });

  it("renders canceled subscription with informational text", () => {
    render(
      <SubscriptionCard
        subscription={makeSub({
          status: "canceled",
          canceled_at: "2026-04-15T00:00:00+00:00",
          cancel_at_period_end: true,
        })}
      />,
    );
    expect(
      screen.getByText(/your subscription is canceled/i),
    ).toBeInTheDocument();
  });

  it("renders cancel-at-period-end scheduled with ends on wording", () => {
    render(
      <SubscriptionCard
        subscription={makeSub({
          status: "active",
          cancel_at_period_end: true,
        })}
      />,
    );
    expect(screen.getByText(/ends on/i)).toBeInTheDocument();
  });
});
