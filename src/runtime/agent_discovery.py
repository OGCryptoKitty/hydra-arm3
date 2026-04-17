"""
HYDRA Arm 3 — Agent Discovery & Registration

Autonomous registration with x402 ecosystem discovery services.
Runs on startup and periodically to ensure HYDRA is discoverable
by AI agents across all major directories.

Zero-API-key channels (HTTP-only, no auth):
  - x402scan.com ping (x402 crawler trigger)
  - /.well-known/x402.json self-verification
  - OpenAPI spec advertisement via /docs endpoint

This module is called by the automaton heartbeat every 24 hours
alongside the marketing loop.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("hydra.discovery")

HYDRA_BASE_URL = "https://hydra-api-nlnj.onrender.com"

DISCOVERY_ENDPOINTS = [
    {
        "name": "x402scan",
        "url": "https://x402scan.com/api/submit",
        "method": "POST",
        "payload": {"url": HYDRA_BASE_URL},
    },
    {
        "name": "x402_index",
        "url": "https://x402-index.com/api/register",
        "method": "POST",
        "payload": {"url": HYDRA_BASE_URL, "manifest": f"{HYDRA_BASE_URL}/.well-known/x402.json"},
    },
]


async def register_with_discovery_services() -> dict[str, Any]:
    """
    Attempt to register HYDRA with all known x402 discovery services.

    Returns a dict of service_name → result. Failures are non-fatal
    (services may not exist yet or may have different APIs).
    """
    results: dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for service in DISCOVERY_ENDPOINTS:
            name = service["name"]
            try:
                if service["method"] == "POST":
                    resp = await client.post(service["url"], json=service["payload"])
                else:
                    resp = await client.get(service["url"])

                results[name] = {
                    "status": resp.status_code,
                    "success": resp.status_code < 400,
                    "response": resp.text[:200] if resp.status_code < 400 else None,
                }
                logger.info("Discovery registration %s: HTTP %d", name, resp.status_code)
            except httpx.RequestError as exc:
                results[name] = {"status": "unreachable", "success": False, "error": str(type(exc).__name__)}
                logger.debug("Discovery service %s unreachable: %s", name, exc)

        try:
            manifest_resp = await client.get(f"{HYDRA_BASE_URL}/.well-known/x402.json")
            results["self_manifest"] = {
                "status": manifest_resp.status_code,
                "valid": manifest_resp.status_code == 200,
                "endpoints": len(manifest_resp.json().get("endpoints", [])) if manifest_resp.status_code == 200 else 0,
            }
        except Exception as exc:
            results["self_manifest"] = {"status": "error", "valid": False, "error": str(exc)[:100]}

    return results


async def verify_deployment_health() -> dict[str, Any]:
    """
    Verify HYDRA is live and responding correctly on Render.
    Checks health, pricing, and free discovery endpoints.
    """
    checks: dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for endpoint in ["/health", "/pricing", "/v1/markets", "/v1/util", "/.well-known/x402.json"]:
            try:
                resp = await client.get(f"{HYDRA_BASE_URL}{endpoint}")
                checks[endpoint] = {
                    "status": resp.status_code,
                    "ok": resp.status_code == 200,
                    "size_bytes": len(resp.content),
                }
            except Exception as exc:
                checks[endpoint] = {"status": "error", "ok": False, "error": str(exc)[:100]}

    return checks
