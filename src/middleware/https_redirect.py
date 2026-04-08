"""
HYDRA HTTPS Redirect Middleware
================================
Redirects HTTP requests to HTTPS in production environments.
Respects reverse proxy headers (X-Forwarded-Proto).
Disabled when ENFORCE_HTTPS env var is not "true".
"""

from __future__ import annotations

import os
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

ENFORCE_HTTPS: bool = os.getenv("ENFORCE_HTTPS", "false").lower() == "true"


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect HTTP to HTTPS when ENFORCE_HTTPS=true."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not ENFORCE_HTTPS:
            return await call_next(request)

        # Check the protocol — honour X-Forwarded-Proto from reverse proxies
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "http":
            url = request.url.replace(scheme="https")
            return RedirectResponse(str(url), status_code=301)

        return await call_next(request)
