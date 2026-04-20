import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// next/navigation's hooks are only defined at runtime inside a Next server —
// stub the bits our components touch so the landing page can be mounted in
// jsdom.
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

// next/link just renders an anchor in tests — we don't need its prefetch
// behaviour here.
vi.mock("next/link", () => ({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  default: ({ href, children, ...rest }: any) => (
    <a href={typeof href === "string" ? href : "#"} {...rest}>
      {children}
    </a>
  ),
}));

import LandingPage from "@/app/page";
import { AuthProvider } from "@/lib/auth-context";

describe("Landing page", () => {
  it("renders the hero and pricing CTA", () => {
    render(
      <AuthProvider>
        <LandingPage />
      </AuthProvider>,
    );

    expect(
      screen.getByRole("heading", { level: 1, name: /subscription billing/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /see pricing/i })).toHaveAttribute(
      "href",
      "/pricing",
    );
  });
});
