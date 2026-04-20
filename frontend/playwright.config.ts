import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for PayFast frontend E2E smoke tests.
 *
 * - `e2e/*.spec.ts` → active specs (run with `pnpm e2e`)
 * - `e2e/*.skip`    → disabled specs (gated on PayFast UAT credentials)
 *
 * Run locally:
 *   pnpm exec playwright install chromium   # one-off, downloads browser
 *   pnpm dev                                # start Next.js in one terminal
 *   pnpm e2e                                # run smoke in another
 *
 * The backend must also be running (make backend) because signup/login hit it.
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.spec\.ts$/,
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "line" : [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
