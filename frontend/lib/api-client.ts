/**
 * Typed fetch wrapper with automatic 401 -> refresh -> retry.
 *
 * Usage:
 *   await api.get<Plan[]>("/plans");
 *   await api.post<AuthToken, LoginPayload>("/auth/jwt/login", body, { form: true });
 *
 * Design notes:
 *  - No third-party HTTP lib. `fetch` is enough and keeps the bundle small.
 *  - The refresh flow is deliberately single-flight: a concurrent burst of 401s
 *    from a stale token will all await the same refresh promise.
 *  - `ApiError` carries the HTTP status and parsed body so callers can
 *    branch on e.g. 422 validation errors without re-parsing.
 *  - Credentials are `include`d so the httpOnly refresh cookie is sent
 *    cross-origin to the FastAPI backend.
 */

import { env } from "./env";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "./auth-storage";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message?: string,
  ) {
    super(message ?? `API error ${status}`);
    this.name = "ApiError";
  }
}

/** Thrown when the network request itself fails (backend down, DNS, CORS, etc). */
export class ApiNetworkError extends Error {
  constructor(public readonly cause: unknown) {
    super("Unable to reach the server. Please try again.");
    this.name = "ApiNetworkError";
  }
}

type RequestOptions = {
  /** If true, body is sent as application/x-www-form-urlencoded. */
  form?: boolean;
  /** Override the Authorization header. Use `null` to explicitly omit. */
  accessToken?: string | null;
  /** Additional fetch init (e.g. `cache: "no-store"`). */
  init?: Omit<RequestInit, "body" | "method" | "headers">;
  /** Extra headers to merge in. */
  headers?: Record<string, string>;
};

function toUrl(path: string): string {
  // Leading-slash tolerant so callers can write either "/plans" or "plans".
  const base = env.API_URL.replace(/\/+$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

async function parseBody(res: Response): Promise<unknown> {
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      return await res.json();
    } catch {
      return null;
    }
  }
  try {
    const text = await res.text();
    return text.length > 0 ? text : null;
  } catch {
    return null;
  }
}

// Single-flight refresh so we don't hammer /auth/jwt/refresh with N parallel 401s.
let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      // fastapi-users' refresh endpoint: reads the refresh cookie, returns a new
      // access token. If this route name diverges on the backend, change it
      // here only.
      const res = await fetch(toUrl("/auth/jwt/refresh"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) return null;
      const data = (await parseBody(res)) as
        | { access_token?: string }
        | null;
      if (!data || typeof data.access_token !== "string") return null;
      setAccessToken(data.access_token);
      return data.access_token;
    } catch {
      return null;
    } finally {
      // Let the next 401 cycle start a fresh attempt after this one resolves.
      setTimeout(() => {
        refreshInFlight = null;
      }, 0);
    }
  })();

  return refreshInFlight;
}

async function request<TResponse>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body: unknown,
  options: RequestOptions = {},
  isRetry = false,
): Promise<TResponse> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers ?? {}),
  };

  let serializedBody: BodyInit | undefined;
  if (body !== undefined && body !== null) {
    if (options.form) {
      headers["Content-Type"] = "application/x-www-form-urlencoded";
      const params = new URLSearchParams();
      for (const [k, v] of Object.entries(body as Record<string, unknown>)) {
        if (v === undefined || v === null) continue;
        params.append(k, String(v));
      }
      serializedBody = params.toString();
    } else {
      headers["Content-Type"] = "application/json";
      serializedBody = JSON.stringify(body);
    }
  }

  // Attach bearer. `options.accessToken === null` means "explicitly unauth".
  const token =
    options.accessToken === null
      ? null
      : (options.accessToken ?? getAccessToken());
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(toUrl(path), {
      method,
      headers,
      body: serializedBody,
      credentials: "include",
      ...(options.init ?? {}),
    });
  } catch (err) {
    throw new ApiNetworkError(err);
  }

  if (res.status === 401 && !isRetry && options.accessToken !== null) {
    const fresh = await refreshAccessToken();
    if (fresh) {
      return request<TResponse>(method, path, body, options, true);
    }
    // Refresh failed — clear and surface the 401.
    clearAccessToken();
  }

  if (!res.ok) {
    const errorBody = await parseBody(res);
    throw new ApiError(res.status, errorBody);
  }

  // 204 and friends — nothing to parse.
  if (res.status === 204) return undefined as TResponse;

  return (await parseBody(res)) as TResponse;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>("GET", path, undefined, options),
  post: <T, B = unknown>(path: string, body?: B, options?: RequestOptions) =>
    request<T>("POST", path, body, options),
  put: <T, B = unknown>(path: string, body?: B, options?: RequestOptions) =>
    request<T>("PUT", path, body, options),
  patch: <T, B = unknown>(path: string, body?: B, options?: RequestOptions) =>
    request<T>("PATCH", path, body, options),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>("DELETE", path, undefined, options),
};

/** True iff the error is a 4xx/5xx from the API (not a network/other error). */
export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}

export function isNetworkError(err: unknown): err is ApiNetworkError {
  return err instanceof ApiNetworkError;
}
