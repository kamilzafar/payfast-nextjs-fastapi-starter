import { expect, test } from "@playwright/test";

/**
 * Smoke E2E — the minimum walk-through of the app that does NOT require
 * PayFast UAT credentials. Confirms:
 *   1. Landing page renders
 *   2. Pricing page is reachable from the nav
 *   3. A new user can sign up and land on /dashboard
 *   4. /settings is reachable while authenticated
 *
 * Requires:
 *   - Next.js dev server running on baseURL (default http://localhost:3000)
 *   - FastAPI backend running and able to register users (DB up, JWT_SECRET set)
 *
 * Payment/checkout flows are covered in `payment.spec.ts.skip` — enable that
 * once PayFast hands over merchant UAT credentials.
 */

function uniqueEmail(): string {
  // Randomised so repeated runs don't collide on unique-email constraints.
  const stamp = Date.now();
  const rand = Math.floor(Math.random() * 1e6);
  return `e2e-${stamp}-${rand}@example.com`;
}

test("landing → pricing → signup → dashboard → settings", async ({ page }) => {
  // 1. Landing
  await page.goto("/");
  await expect(page).toHaveTitle(/PayFast|Billing/i);
  await expect(
    page.getByRole("heading", { name: /Subscription billing/i }),
  ).toBeVisible();

  // 2. Pricing — follow the "See pricing" CTA
  await page.getByRole("link", { name: /see pricing/i }).first().click();
  await expect(page).toHaveURL(/\/pricing$/);

  // 3. Signup — navigate directly (pricing CTA behaviour depends on auth state)
  await page.goto("/signup");
  await expect(
    page.getByRole("heading", { name: /create your account/i }),
  ).toBeVisible();

  const email = uniqueEmail();
  await page.getByLabel(/full name/i).fill("E2E Smoke User");
  await page.getByLabel(/^email$/i).fill(email);
  await page.getByLabel(/phone/i).fill("+923001234567");
  await page.getByLabel(/password/i).fill("password-e2e-12345");

  await page.getByRole("button", { name: /create account/i }).click();

  // Land on /dashboard after successful registration + auto-login.
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 });
  await expect(page).toHaveURL(/\/dashboard/);

  // 4. Settings reachable while authenticated
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/settings$/);
});
