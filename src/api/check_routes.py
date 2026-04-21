"""
HYDRA — Web infrastructure check endpoints.

URL health, DNS records, SSL certificates, HTTP headers.
Pay-per-call via x402 on Base L2.
"""

from __future__ import annotations

import socket
import ssl
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

check_router = APIRouter(tags=["Web Checks"])

_http_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            headers={"User-Agent": "HYDRA-Check/1.0 (x402; +https://hydra-api-nlnj.onrender.com)"},
        )
    return _http_client


@check_router.get("/v1/check/url", tags=["Web Checks"])
async def check_url(
    url: str = Query(..., description="URL to check"),
    follow_redirects: bool = Query(default=True),
):
    """
    URL health check — status code, response time, redirect chain,
    content type, server header. $0.005 USDC.
    """
    start = time.monotonic()
    client = await _get_client()

    redirects: list[dict] = []
    try:
        resp = await client.get(url, follow_redirects=False)
        final_url = url
        status = resp.status_code

        if follow_redirects:
            seen = {url}
            current = resp
            while current.is_redirect and len(redirects) < 10:
                location = str(current.headers.get("location", ""))
                if not location or location in seen:
                    break
                redirects.append({"from": str(current.url), "to": location, "status": current.status_code})
                seen.add(location)
                current = await client.get(location, follow_redirects=False)
            final_url = str(current.url)
            status = current.status_code
            resp = current

        content_type = resp.headers.get("content-type", "")
        server = resp.headers.get("server", "")
        content_length = resp.headers.get("content-length")

        return {
            "url": url,
            "final_url": final_url,
            "status_code": status,
            "ok": 200 <= status < 400,
            "content_type": content_type,
            "server": server,
            "content_length": int(content_length) if content_length else None,
            "redirects": redirects if redirects else None,
            "redirect_count": len(redirects),
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        }
    except httpx.RequestError as e:
        return JSONResponse(status_code=200, content={
            "url": url,
            "ok": False,
            "error": type(e).__name__,
            "detail": str(e)[:200],
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        })


@check_router.get("/v1/check/dns", tags=["Web Checks"])
async def check_dns(
    domain: str = Query(..., description="Domain to look up"),
    record_type: str = Query(default="A", description="Record type: A, AAAA, MX, TXT, NS, CNAME"),
):
    """
    DNS record lookup via Google DNS-over-HTTPS. Returns records
    for any domain and type. $0.005 USDC.
    """
    start = time.monotonic()
    client = await _get_client()

    rtype = record_type.upper()
    if rtype not in ("A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA", "PTR", "SRV", "CAA"):
        return JSONResponse(status_code=422, content={"error": f"Unsupported record type: {rtype}"})

    try:
        resp = await client.get(
            "https://dns.google/resolve",
            params={"name": domain, "type": rtype},
            headers={"Accept": "application/dns-json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.RequestError, httpx.HTTPStatusError):
        return JSONResponse(status_code=502, content={"error": "DNS resolver unavailable"})

    records = []
    for answer in data.get("Answer", []):
        records.append({
            "name": answer.get("name", "").rstrip("."),
            "type": rtype,
            "ttl": answer.get("TTL"),
            "data": answer.get("data", "").strip('"'),
        })

    return {
        "domain": domain,
        "record_type": rtype,
        "status": data.get("Status", -1),
        "records": records,
        "record_count": len(records),
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }


@check_router.get("/v1/check/ssl", tags=["Web Checks"])
async def check_ssl(
    domain: str = Query(..., description="Domain to inspect SSL certificate"),
    port: int = Query(default=443, ge=1, le=65535),
):
    """
    SSL certificate inspection — issuer, expiry, subject alternative names,
    protocol version, days until expiry. $0.005 USDC.
    """
    start = time.monotonic()

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                protocol = ssock.version()

        subject = dict(x[0] for x in cert.get("subject", ()))
        issuer = dict(x[0] for x in cert.get("issuer", ()))
        not_before = cert.get("notBefore", "")
        not_after = cert.get("notAfter", "")

        san = []
        for entry_type, value in cert.get("subjectAltName", ()):
            san.append(value)

        expiry_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days_remaining = (expiry_dt - datetime.now(timezone.utc)).days

        return {
            "domain": domain,
            "valid": True,
            "subject": subject,
            "issuer": issuer,
            "serial_number": cert.get("serialNumber"),
            "not_before": not_before,
            "not_after": not_after,
            "days_remaining": days_remaining,
            "expired": days_remaining < 0,
            "san": san,
            "protocol": protocol,
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        }
    except ssl.SSLCertVerificationError as e:
        return {
            "domain": domain,
            "valid": False,
            "error": "certificate_verification_failed",
            "detail": str(e)[:200],
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        }
    except (socket.timeout, socket.gaierror, OSError) as e:
        return JSONResponse(status_code=200, content={
            "domain": domain,
            "valid": False,
            "error": "connection_failed",
            "detail": str(e)[:200],
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        })


@check_router.get("/v1/check/headers", tags=["Web Checks"])
async def check_headers(
    url: str = Query(..., description="URL to inspect HTTP headers"),
):
    """
    HTTP response headers for a URL. Includes security headers analysis
    (HSTS, CSP, X-Frame-Options, etc.). $0.003 USDC.
    """
    start = time.monotonic()
    client = await _get_client()

    try:
        resp = await client.head(url, follow_redirects=True)
    except httpx.RequestError as e:
        return JSONResponse(status_code=200, content={
            "url": url,
            "error": type(e).__name__,
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        })

    headers = dict(resp.headers)

    security_headers = {
        "strict-transport-security": headers.get("strict-transport-security"),
        "content-security-policy": headers.get("content-security-policy"),
        "x-frame-options": headers.get("x-frame-options"),
        "x-content-type-options": headers.get("x-content-type-options"),
        "x-xss-protection": headers.get("x-xss-protection"),
        "referrer-policy": headers.get("referrer-policy"),
        "permissions-policy": headers.get("permissions-policy"),
    }
    security_score = sum(1 for v in security_headers.values() if v is not None)

    return {
        "url": url,
        "status_code": resp.status_code,
        "headers": headers,
        "security_headers": {k: v for k, v in security_headers.items() if v is not None},
        "security_score": f"{security_score}/7",
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }
