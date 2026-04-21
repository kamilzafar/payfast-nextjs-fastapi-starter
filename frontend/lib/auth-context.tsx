"use client";

/**
 * Auth context — thin wrapper around the API client that exposes the current
 * user, token, and login/signup/logout helpers.
 *
 * This is intentionally not a full auth solution:
 *  - No optimistic updates.
 *  - No TanStack Query (that arrives in phase 4). On mount we just try
 *    GET /me once; if it fails we treat the user as unauthenticated.
 *  - Token refresh is delegated to `api-client`; this context only reacts
 *    to terminal "refresh failed" states (i.e. the /me call still 401s).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, ApiError, isNetworkError } from "./api-client";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "./auth-storage";
import {
  AuthTokenSchema,
  type LoginPayload,
  type SignupPayload,
  type User,
  UserSchema,
} from "./types";

type AuthContextValue = {
  user: User | null;
  accessToken: string | null;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => Promise<void>;
  /** Re-fetch /me. Useful after external mutations that touch the user. */
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessTokenState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const applyToken = useCallback((token: string | null) => {
    if (token) {
      setAccessToken(token);
      setAccessTokenState(token);
    } else {
      clearAccessToken();
      setAccessTokenState(null);
    }
  }, []);

  const fetchMe = useCallback(async (): Promise<User | null> => {
    try {
      const raw = await api.get<unknown>("/me");
      const parsed = UserSchema.safeParse(raw);
      if (!parsed.success) {
        // Don't spam console in production, but this *is* a backend contract
        // drift we want to know about during dev.
        if (process.env.NODE_ENV !== "production") {
          console.warn("User response failed schema validation:", parsed.error);
        }
        return null;
      }
      return parsed.data;
    } catch (err) {
      if (isNetworkError(err)) {
        // Backend is unreachable — don't nuke the token, user may be offline.
        return null;
      }
      if (err instanceof ApiError && err.status === 401) {
        // Refresh already tried and failed inside api-client; we're unauth.
        return null;
      }
      throw err;
    }
  }, []);

  // Boot: try to resurrect session from stored access token.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const stored = getAccessToken();
      setAccessTokenState(stored);
      if (!stored) {
        setIsLoading(false);
        return;
      }
      const me = await fetchMe();
      if (cancelled) return;
      if (me) {
        setUser(me);
      } else {
        applyToken(null);
        setUser(null);
      }
      setIsLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [applyToken, fetchMe]);

  const login = useCallback<AuthContextValue["login"]>(
    async (payload) => {
      // fastapi-users /auth/jwt/login uses OAuth2 password form flow.
      const raw = await api.post<unknown>(
        "/auth/jwt/login",
        { username: payload.email, password: payload.password },
        { form: true, accessToken: null },
      );
      const token = AuthTokenSchema.parse(raw);
      applyToken(token.access_token);
      const me = await fetchMe();
      setUser(me);
    },
    [applyToken, fetchMe],
  );

  const signup = useCallback<AuthContextValue["signup"]>(
    async (payload) => {
      // fastapi-users /register creates the user; we then log them in to
      // obtain a token. Some deployments combine these — we assume the
      // separate-call flow which is the fastapi-users default.
      await api.post<unknown>(
        "/auth/register",
        {
          email: payload.email,
          password: payload.password,
          name: payload.name,
          phone: payload.phone,
        },
        { accessToken: null },
      );
      await login({ email: payload.email, password: payload.password });
    },
    [login],
  );

  const logout = useCallback<AuthContextValue["logout"]>(async () => {
    try {
      await api.post<unknown>("/auth/jwt/logout", undefined);
    } catch {
      // Logout is best-effort — even if the server call fails we still
      // want the local session cleared.
    }
    applyToken(null);
    setUser(null);
  }, [applyToken]);

  const refresh = useCallback<AuthContextValue["refresh"]>(async () => {
    const me = await fetchMe();
    setUser(me);
  }, [fetchMe]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, accessToken, isLoading, login, signup, logout, refresh }),
    [user, accessToken, isLoading, login, signup, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
