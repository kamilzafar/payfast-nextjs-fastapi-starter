/**
 * Typed access to public env vars. Throws at import-time on the server if
 * NEXT_PUBLIC_API_URL is missing (we want to fail fast in build rather than
 * surfacing a confusing fetch error at runtime).
 *
 * Only NEXT_PUBLIC_* vars are available on the client; anything else defined
 * here would be a server-only leak footgun.
 */

function required(name: string, value: string | undefined): string {
  if (!value || value.length === 0) {
    throw new Error(
      `Missing required env var: ${name}. Add it to .env.local (see .env.example).`,
    );
  }
  return value;
}

export const env = {
  /** Base URL of the FastAPI backend, e.g. http://localhost:8000 */
  API_URL: required("NEXT_PUBLIC_API_URL", process.env.NEXT_PUBLIC_API_URL),
} as const;
