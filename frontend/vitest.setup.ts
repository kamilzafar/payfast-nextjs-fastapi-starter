import "@testing-library/jest-dom/vitest";

// NEXT_PUBLIC_API_URL is read at module import time by lib/env.ts — set a
// safe default for tests so the import doesn't throw.
process.env.NEXT_PUBLIC_API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
