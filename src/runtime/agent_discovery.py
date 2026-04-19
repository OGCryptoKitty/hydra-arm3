"""
HYDRA Arm 3 — Agent Discovery & Distribution Engine

Autonomous registration and discovery maximization. Runs every 24 hours
via HydraAutomaton heartbeat. Zero human involvement.

Distribution channels:
  x402 ecosystem:
    - x402.org registry — official Linux Foundation x402 registry
    - x402scan.com — open x402 crawler
    - x402list.fun — community x402 directory
    - x402-list.com — x402 service listing
  MCP directories (auto-indexed from GitHub repo):
    - Glama (auto-indexes from README.md MCP metadata)
    - Smithery (auto-indexes from smithery.yaml in repo root)
    - mcp.so — community-submitted MCP servers
  Agent discovery protocols:
    - Google A2A — /.well-known/agent.json
    - MCP — /.well-known/mcp.json
    - x402 — /.well-known/x402.json
    - llms.txt — /.well-known/llms.txt
    - AI Plugin — /.well-known/ai-plugin.json
  Search engine pinging:
    - Google sitemap ping
    - Bing IndexNow
    - Yandex sitemap ping
  x402 marketplaces:
    - the402.ai — agent marketplace with x402 payments
  Self-verification:
    - All discovery manifests verified on each cycle
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("hydra.discovery")

HYDRA_BASE_URL = "https://hydra-api-nlnj.onrender.com"
HYDRA_MANIFEST = f"{HYDRA_BASE_URL}/.well-known/x402.json"
HYDRA_OPENAPI = f"{HYDRA_BASE_URL}/openapi.json"

DISCOVERY_ENDPOINTS = [
    {
        "name": "x402_org_registry",
        "url": "https://x402.org/api/services",
        "method": "POST",
        "payload": {
            "url": HYDRA_BASE_URL,
            "manifest": HYDRA_MANIFEST,
            "name": "HYDRA Regulatory Intelligence",
            "description": "22 paid x402 endpoints — regulatory signals, FOMC data, oracle feeds. $0.001-$50 USDC on Base.",
        },
    },
    {
        "name": "x402scan",
        "url": "https://x402scan.com/api/submit",
        "method": "POST",
        "payload": {"url": HYDRA_BASE_URL, "manifest": HYDRA_MANIFEST},
    },
    {
        "name": "mcp_so",
        "url": "https://mcp.so/api/servers",
        "method": "POST",
        "payload": {
            "url": f"{HYDRA_BASE_URL}/mcp",
            "name": "HYDRA Regulatory Intelligence",
            "description": "x402-paid regulatory intelligence MCP server. SEC/CFTC/Fed monitoring, prediction market signals, oracle data.",
            "openapi_url": HYDRA_OPENAPI,
            "transport": "streamable-http",
        },
    },
    {
        "name": "x402list_fun",
        "url": "https://x402list.fun/api/submit",
        "method": "POST",
        "payload": {"url": HYDRA_BASE_URL, "manifest": HYDRA_MANIFEST},
    },
    {
        "name": "x402_list_com",
        "url": "https://x402-list.com/api/submit",
        "method": "POST",
        "payload": {"url": HYDRA_BASE_URL, "manifest": HYDRA_MANIFEST},
    },
    {
        "name": "the402_ai",
        "url": "https://the402.ai/v1/register",
        "method": "POST",
        "payload": {
            "url": HYDRA_BASE_URL,
            "manifest": HYDRA_MANIFEST,
            "name": "HYDRA Regulatory Intelligence",
            "category": "Intelligence",
        },
    },
]

SELF_VERIFICATION_ENDPOINTS = [
    f"{HYDRA_BASE_URL}/.well-known/x402.json",
    f"{HYDRA_BASE_URL}/.well-known/agent.json",
    f"{HYDRA_BASE_URL}/.well-known/agent-card.json",
    f"{HYDRA_BASE_URL}/.well-known/mcp.json",
    f"{HYDRA_BASE_URL}/.well-known/llms.txt",
    f"{HYDRA_BASE_URL}/.well-known/ai-plugin.json",
    f"{HYDRA_BASE_URL}/openapi.json",
    f"{HYDRA_BASE_URL}/health",
]


async def register_with_discovery_services() -> dict[str, Any]:
    """
    Register HYDRA with x402 discovery services and verify self-hosted manifests.

    Returns a dict of service_name → result. Failures are non-fatal.
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

        for url in SELF_VERIFICATION_ENDPOINTS:
            ep_name = url.split("onrender.com")[-1]
            try:
                resp = await client.get(url)
                results[f"self:{ep_name}"] = {"status": resp.status_code, "ok": resp.status_code == 200}
            except Exception as exc:
                results[f"self:{ep_name}"] = {"status": "error", "ok": False}

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


async def ping_search_engines() -> dict[str, Any]:
    """
    Notify search engines that HYDRA's sitemap and OpenAPI spec exist.
    Google and Bing will crawl and index these URLs.
    """
    results: dict[str, Any] = {}
    sitemap_url = f"{HYDRA_BASE_URL}/sitemap.xml"
    openapi_url = f"{HYDRA_BASE_URL}/openapi.json"

    ping_targets = [
        ("google_sitemap", f"https://www.google.com/ping?sitemap={sitemap_url}"),
        ("bing_sitemap", f"https://www.bing.com/ping?sitemap={sitemap_url}"),
        ("yandex_sitemap", f"https://webmaster.yandex.com/ping?sitemap={sitemap_url}"),
    ]

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for name, url in ping_targets:
            try:
                resp = await client.get(url)
                results[name] = {"status": resp.status_code, "ok": resp.status_code < 400}
                logger.info("Search engine ping %s: HTTP %d", name, resp.status_code)
            except Exception as exc:
                results[name] = {"status": "error", "ok": False}
                logger.debug("Search engine ping %s failed: %s", name, exc)

    return results


async def verify_deployment_health() -> dict[str, Any]:
    """
    Verify HYDRA is live and all discovery manifests are serving.
    """
    checks: dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for endpoint in SELF_VERIFICATION_ENDPOINTS + [
            f"{HYDRA_BASE_URL}/v1/markets",
            f"{HYDRA_BASE_URL}/pricing",
            f"{HYDRA_BASE_URL}/mcp",
        ]:
            ep_name = endpoint.split("onrender.com")[-1] if "onrender.com" in endpoint else endpoint
            try:
                resp = await client.get(endpoint)
                checks[ep_name] = {
                    "status": resp.status_code,
                    "ok": resp.status_code == 200,
                    "size_bytes": len(resp.content),
                }
            except Exception as exc:
                checks[ep_name] = {"status": "error", "ok": False, "error": str(exc)[:100]}

    return checks
