/**
 * Tiny localStorage wrapper for the access token only.
 *
 * Why localStorage and not a cookie for the access token?
 *  - The refresh token lives in an httpOnly cookie (set server-side by
 *    FastAPI), so XSS can't exfiltrate long-lived credentials.
 *  - The short-lived access token needs to be attached to the `Authorization`
 *    header on every API call. Reading it from a JS-accessible store is the
 *    simplest path there; the blast radius of leaking a 15-min access token
 *    is acceptable.
 *
 * All functions are SSR-safe (they no-op on the server).
 */

const ACCESS_TOKEN_KEY = "payfast.accessToken";
const SESSION_COOKIE = "payfast.session";

const isBrowser = (): boolean =>
  typeof window !== "undefined" && typeof window.localStorage !== "undefined";

function setSessionCookie(value: string): void {
  if (typeof document === "undefined") return;
  // Non-httpOnly sentinel; the edge proxy reads this to avoid bouncing
  // authed users back to /login. The actual access token stays in localStorage.
  // 7-day max-age roughly matches the refresh-token lifetime.
  const maxAge = 60 * 60 * 24 * 7;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${SESSION_COOKIE}=${value}; Path=/; Max-Age=${maxAge}; SameSite=Lax${secure}`;
}

function clearSessionCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
}

export function getAccessToken(): string | null {
  if (!isBrowser()) return null;
  try {
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    // localStorage can throw in private-mode Safari and some embedded browsers.
    return null;
  }
}

export function setAccessToken(token: string): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
    setSessionCookie("1");
  } catch {
    // Ignore — auth will fall back to a fresh login on next refresh.
  }
}

export function clearAccessToken(): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    clearSessionCookie();
  } catch {
    // Ignore.
  }
}
