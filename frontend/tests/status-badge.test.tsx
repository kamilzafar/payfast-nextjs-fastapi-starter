import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/components/status-badge";

describe("StatusBadge", () => {
  it("renders trialing with the expected tone class", () => {
    render(<StatusBadge status="trialing" kind="subscription" />);
    const el = screen.getByText(/trialing/i);
    // trialing uses indigo/primary tone
    expect(el.className).toMatch(/bg-/);
    expect(el.className).toMatch(/indigo|primary|blue/);
  });

  it("renders active with green tone", () => {
    render(<StatusBadge status="active" kind="subscription" />);
    const el = screen.getByText(/active/i);
    expect(el.className).toMatch(/emerald|green/);
  });

  it("renders past_due with amber/orange tone", () => {
    render(<StatusBadge status="past_due" kind="subscription" />);
    const el = screen.getByText(/past due/i);
    expect(el.className).toMatch(/amber|orange|yellow/);
  });

  it("renders canceled with neutral tone", () => {
    render(<StatusBadge status="canceled" kind="subscription" />);
    const el = screen.getByText(/cancel/i);
    expect(el.className).toMatch(/muted|neutral|gray|slate|zinc/);
  });

  it("renders invoice open with amber tone", () => {
    render(<StatusBadge status="open" kind="invoice" />);
    const el = screen.getByText(/open/i);
    expect(el.className).toMatch(/amber|orange|yellow/);
  });

  it("renders invoice paid with green tone", () => {
    render(<StatusBadge status="paid" kind="invoice" />);
    const el = screen.getByText(/paid/i);
    expect(el.className).toMatch(/emerald|green/);
  });

  it("renders invoice void with neutral tone", () => {
    render(<StatusBadge status="void" kind="invoice" />);
    const el = screen.getByText(/void/i);
    expect(el.className).toMatch(/muted|neutral|gray|slate|zinc/);
  });
});
