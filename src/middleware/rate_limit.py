"""
HYDRA Rate Limiting Middleware
==============================
Per-IP rate limiting for API endpoints.

Limits:
  - Free endpoints:  60 requests/minute per IP
  - Paid endpoints:  30 requests/minute per IP (also payment-gated)
  - System endpoints: 10 requests/minute per IP

Uses a sliding window counter stored in TTLCache (in-memory).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Callable

from cachetools import TTLCache
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Rate limit windows (requests per 60 seconds)
RATE_LIMITS = {
    "free": 60,
    "paid": 30,
    "system": 10,
}

# Sliding window: IP → list of timestamps (TTL = 60 seconds)
_rate_windows: dict[str, list[float]] = defaultdict(list)

# Cleanup old entries periodically
_WINDOW_SECONDS = 60.0


def _classify_path(path: str) -> str:
    """Classify request path into rate limit tier."""
    if path.startswith("/system/"):
        return "system"
    if path.startswith("/v1/"):
        return "paid"
    return "free"


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _is_rate_limited(ip: str, tier: str) -> bool:
    """Check if the IP has exceeded the rate limit for the given tier."""
    now = time.monotonic()
    key = f"{ip}:{tier}"
    window = _rate_windows[key]

    # Prune expired entries
    cutoff = now - _WINDOW_SECONDS
    _rate_windows[key] = [ts for ts in window if ts > cutoff]
    window = _rate_windows[key]

    limit = RATE_LIMITS.get(tier, 60)
    if len(window) >= limit:
        return True

    window.append(now)
    return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting middleware."""

    # Paths exempt from rate limiting
    _EXEMPT_PATHS: frozenset[str] = frozenset({
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/favicon.ico",
    })

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if path in self._EXEMPT_PATHS:
            return await call_next(request)

        ip = _get_client_ip(request)
        tier = _classify_path(path)

        if _is_rate_limited(ip, tier):
            logger.warning("Rate limit exceeded: ip=%s tier=%s path=%s", ip, tier, path)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded ({RATE_LIMITS[tier]} requests/minute). Please retry later.",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        return response
