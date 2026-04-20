"""HTTP middlewares: request ID + structlog request-scoped context."""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request ID, bind structlog context, time the request.

    - Reads `X-Request-ID` from the incoming request or mints a fresh UUID4.
    - Binds `request_id`, `path`, `method` into structlog's contextvars so
      every log line inside the request handler gets them for free.
    - On response, logs a single `http.request` line with status + duration_ms
      and echoes `X-Request-ID` back to the client.
    - Never logs bodies — only metadata.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._log = structlog.get_logger("http")

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming else str(uuid.uuid4())

        # Bind context for this request
        structlog.contextvars.clear_contextvars()
        bind_ctx = {
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        }

        # Best-effort: if FastAPI/fastapi-users has populated request.state.user,
        # capture user_id. Most routes haven't run auth dep yet at middleware time,
        # so this usually binds after the fact via explicit logger.bind in handlers.
        structlog.contextvars.bind_contextvars(**bind_ctx)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self._log.exception(
                "http.request.error",
                duration_ms=duration_ms,
                error=str(exc),
            )
            structlog.contextvars.clear_contextvars()
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id

        self._log.info(
            "http.request",
            status=response.status_code,
            duration_ms=duration_ms,
        )
        structlog.contextvars.clear_contextvars()
        return response
