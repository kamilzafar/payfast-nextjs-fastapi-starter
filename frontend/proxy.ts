/**
 * Edge "proxy" (formerly `middleware.ts` in pre-16 Next.js).
 *
 * We do an *optimistic* auth check by looking for a sentinel cookie. The real
 * authz happens at the API layer — this is purely to bounce unauthenticated
 * users away from authed pages before we ship them the client bundle.
 *
 * The backend is expected to set a non-httpOnly `payfast.session` cookie
 * with any non-empty value whenever a refresh cookie is issued, so the edge
 * can see *that* a session exists without reading the actual token.
 *
 * If the backend doesn't set this sentinel, the (app) layout still runs a
 * client-side guard that bounces to /login — we just lose the optimistic
 * redirect. No correctness impact.
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SESSION_COOKIE = "payfast.session";

/**
 * `/checkout/success` and `/checkout/cancel` are the post-PayFast landing
 * pages — they must work even when the session cookie is missing (third-party
 * cookie policies, incognito, etc.). We allow-list them explicitly so the
 * matcher below can still cover `/checkout/:path*` for the gated pages like
 * `/checkout/initiate` and `/checkout/[invoiceId]`.
 */
const PUBLIC_CHECKOUT_PATHS = new Set<string>([
  "/checkout/success",
  "/checkout/cancel",
]);

export function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  if (PUBLIC_CHECKOUT_PATHS.has(pathname)) {
    return NextResponse.next();
  }

  const sentinel = request.cookies.get(SESSION_COOKIE)?.value;

  if (!sentinel || sentinel.length === 0) {
    const loginUrl = new URL("/login", request.url);
    // Preserve the full intended destination (including query) so deep-linked
    // checkout URLs survive the login bounce.
    const returnTo = `${pathname}${request.nextUrl.search ?? ""}`;
    loginUrl.searchParams.set("returnTo", returnTo);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/settings/:path*",
    "/checkout/:path*",
  ],
};
