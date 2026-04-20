"""Rate-limiting wiring on top of slowapi.

Keys:
  - Authenticated endpoints: prefer the JWT-decoded user id (if we can cheaply
    read it off the Authorization header). Fall back to client IP.
  - Anonymous endpoints: always client IP (slowapi's default remote-addr key).

The webhook endpoint is explicitly skipped in handlers — see main.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
import structlog
from limits import parse
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.config import settings

log = structlog.get_logger(__name__)


def get_rate_limit_key(request: Request) -> str:
    """Return a stable rate-limit key for this request.

    Order of preference:
      1. user:<id> if we can decode a JWT from the Authorization header
      2. ip:<remote_addr> otherwise
    """
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            # fastapi-users signs tokens with HS256 + audience "fastapi-users:auth".
            # We don't verify expiry here — if the token is expired, the auth dep
            # will 401 anyway; we just want a stable per-user bucket either way.
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=["HS256"],
                audience="fastapi-users:auth",
                options={"verify_exp": False},
            )
            sub = payload.get("sub")
            if sub is not None:
                return f"user:{sub}"
        except Exception:
            # Malformed / mismatched / wrong-audience — fall through to IP.
            pass

    return f"ip:{get_remote_address(request)}"


# Primary limiter used by @limiter.limit(...) decorators on our own handlers.
# If RATE_LIMIT_ENABLED is False (e.g. in the test suite) slowapi no-ops.
limiter = Limiter(key_func=get_rate_limit_key, enabled=settings.RATE_LIMIT_ENABLED)


@dataclass(frozen=True)
class PathLimit:
    """A limit applied by exact (method, path) match at the middleware layer.

    Used for endpoints we can't decorate directly — i.e. fastapi-users' built-in
    register/login/refresh routes, which are mounted as sub-routers.
    """

    method: str
    path: str
    rate: str  # e.g. "5/minute"


# Auth endpoints can't be decorated (they're provided by fastapi-users),
# so enforce them via PathLimitMiddleware below.
AUTH_PATH_LIMITS: tuple[PathLimit, ...] = (
    PathLimit(method="POST", path="/auth/register", rate="5/minute"),
    PathLimit(method="POST", path="/auth/jwt/login", rate="10/minute"),
    # fastapi-users doesn't ship a refresh route out-of-the-box, but the brief
    # specifies one; applying the limit here is harmless (no match → skipped)
    # and auto-activates if a refresh endpoint is added later at this path.
    PathLimit(method="POST", path="/auth/jwt/refresh", rate="30/minute"),
)


class PathLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-(method, path) rate limits using the shared `limiter`.

    Skips `/webhooks/*` entirely — PayFast retries server-to-server; idempotency
    is handled at the webhook handler via `webhook_events.try_insert`.
    """

    def __init__(self, app: ASGIApp, limits: tuple[PathLimit, ...]) -> None:
        super().__init__(app)
        self._parsed = [(pl, parse(pl.rate)) for pl in limits]

    async def dispatch(self, request: Request, call_next) -> Response:
        if not limiter.enabled or request.url.path.startswith("/webhooks/"):
            return await call_next(request)

        for pl, rate_item in self._parsed:
            if request.method == pl.method and request.url.path == pl.path:
                key = get_rate_limit_key(request)
                if not limiter.limiter.hit(rate_item, pl.path, key):
                    log.warning(
                        "rate_limit.exceeded",
                        path=pl.path,
                        method=pl.method,
                        rate=pl.rate,
                        key=key,
                    )
                    return JSONResponse(
                        status_code=429,
                        content={"detail": f"rate limit exceeded: {pl.rate}"},
                        headers={"Retry-After": "60"},
                    )
                break  # only one match per path

        return await call_next(request)
