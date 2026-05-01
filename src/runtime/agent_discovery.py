"""
HYDRA Arm 3 — Agent Discovery & Distribution Engine

Autonomous registration and discovery maximization. Runs every 24 hours
via HydraAutomaton heartbeat. Zero human involvement.

55+ paid endpoints across 13 real-time data sources. Kalshi KXFED
market-calibrated Fed rate probabilities, FDIC bank failure monitoring,
alpha reports with Kelly sizing, atomic economic snapshots.

Distribution channels:
  x402 ecosystem:
    - x402.org registry — official Linux Foundation x402 registry
    - x402scan.com — open x402 crawler
    - x402list.fun — community x402 directory
    - x402-list.com — x402 service listing
    - x402.eco — x402 ecosystem directory
  MCP directories (auto-indexed from GitHub repo):
    - Glama (auto-indexes from README.md MCP metadata)
    - Smithery (auto-indexes from smithery.yaml in repo root)
    - mcp.so — community-submitted MCP servers
    - PulseMCP — MCP server directory
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
  Agent registries:
    - aiprox.dev — AI proxy registry
    - agentarena.site — agent marketplace
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
            "name": "HYDRA",
            "description": "x402 ecosystem hub + autonomous intelligence engine. 55+ paid endpoints across 13 real-time data sources (SEC EDGAR, CFTC, FinCEN, OCC, CFPB, Federal Reserve, Treasury, FDIC BankFind, Federal Register, BLS, FRED, Kalshi KXFED, Polymarket). Kalshi KXFED market-calibrated Fed rate probabilities, FDIC bank failure monitoring, alpha reports with Kelly sizing, composite risk scores, push alerts, x402 directory/routing, web extraction, search, conversion, dev tools, web checks, public data. $0.001-$50 USDC on Base.",
        },
    },
    {
        "name": "x402scan",
        "url": "https://x402scan.com/api/submit",
        "method": "POST",
        "payload": {
            "url": HYDRA_BASE_URL,
            "manifest": HYDRA_MANIFEST,
            "name": "HYDRA",
            "description": "x402 ecosystem hub + autonomous intelligence engine. 55+ paid endpoints across 13 real-time data sources (SEC EDGAR, CFTC, FinCEN, OCC, CFPB, Federal Reserve, Treasury, FDIC BankFind, Federal Register, BLS, FRED, Kalshi KXFED, Polymarket). Kalshi KXFED market-calibrated Fed rate probabilities, FDIC bank failure monitoring, alpha reports with Kelly sizing, composite risk scores, push alerts, x402 directory/routing, web extraction, search, conversion, dev tools, web checks, public data. $0.001-$50 USDC on Base.",
        },
    },
    {
        "name": "mcp_so",
        "url": "https://mcp.so/api/servers",
        "method": "POST",
        "payload": {
            "url": f"{HYDRA_BASE_URL}/mcp",
            "manifest": HYDRA_MANIFEST,
            "name": "HYDRA",
            "description": "x402 ecosystem hub + intelligence engine. 55+ MCP tools across 13 data sources: Kalshi KXFED-calibrated Fed rate probabilities, FDIC bank failure monitoring, alpha reports with Kelly sizing, composite risk scores, push alerts, x402 directory/routing, web extraction, search, HTML-to-Markdown, DNS/SSL, hash, diff, Wikipedia, arXiv, EDGAR, regulatory intelligence, prediction markets, oracle data.",
            "openapi_url": HYDRA_OPENAPI,
            "transport": "streamable-http",
        },
    },
    {
        "name": "x402list_fun",
        "url": "https://x402list.fun/api/submit",
        "method": "POST",
        "payload": {
            "url": HYDRA_BASE_URL,
            "manifest": HYDRA_MANIFEST,
            "name": "HYDRA",
            "description": "x402 ecosystem hub + autonomous intelligence engine. 55+ paid endpoints across 13 real-time data sources (SEC EDGAR, CFTC, FinCEN, OCC, CFPB, Federal Reserve, Treasury, FDIC BankFind, Federal Register, BLS, FRED, Kalshi KXFED, Polymarket). Kalshi KXFED market-calibrated Fed rate probabilities, FDIC bank failure monitoring, alpha reports with Kelly sizing, composite risk scores, push alerts, x402 directory/routing, web extraction, search, conversion, dev tools, web checks, public data. $0.001-$50 USDC on Base.",
        },
    },
    {
        "name": "x402_list_com",
        "url": "https://x402-list.com/api/submit",
        "method": "POST",
        "payload": {
            "url": HYDRA_BASE_URL,
            "manifest": HYDRA_MANIFEST,
            "name": "HYDRA",
            "description": "x402 ecosystem hub + autonomous intelligence engine. 55+ paid endpoints across 13 real-time data sources (SEC EDGAR, CFTC, FinCEN, OCC, CFPB, Federal Reserve, Treasury, FDIC BankFind, Federal Register, BLS, FRED, Kalshi KXFED, Polymarket). Kalshi KXFED market-calibrated Fed rate probabilities, FDIC bank failure monitoring, alpha reports with Kelly sizing, composite risk scores, push alerts, x402 directory/routing, web extraction, search, conversion, dev tools, web checks, public data. $0.001-$50 USDC on Base.",
        },
    },
    {
        "name": "the402_ai",
        "url": "https://the402.ai/v1/register",
        "method": "POST",
        "payload": {
            "url": HYDRA_BASE_URL,
            "manifest": HYDRA_MANIFEST,
            "name": "HYDRA",
            "category": "Intelligence",
        },
    },
    {
        "name": "x402_discovery_api",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA",
            "url": f"{HYDRA_BASE_URL}/v1/regulatory/scan",
            "price_usd": 2.00,
            "category": "data",
            "description": "Regulatory risk scoring for crypto/DeFi — SEC, CFTC, Fed, FinCEN frameworks",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_fed",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Fed Signal",
            "url": f"{HYDRA_BASE_URL}/v1/fed/signal",
            "price_usd": 5.00,
            "category": "data",
            "description": "Pre-FOMC signal with rate probabilities, speech analysis, economic indicators",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_price",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Crypto Price",
            "url": f"{HYDRA_BASE_URL}/v1/util/crypto/price",
            "price_usd": 0.001,
            "category": "data",
            "description": "Token price, 24h change, market cap — high-volume utility endpoint",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_scrape",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Web Scrape",
            "url": f"{HYDRA_BASE_URL}/v1/util/scrape",
            "price_usd": 0.005,
            "category": "data",
            "description": "URL to clean structured text — HTML parsed, scripts removed",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_oracle",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA UMA Oracle",
            "url": f"{HYDRA_BASE_URL}/v1/oracle/uma",
            "price_usd": 5.00,
            "category": "data",
            "description": "UMA Optimistic Oracle assertion data with evidence chain for market resolution",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_extract",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Web Extract",
            "url": f"{HYDRA_BASE_URL}/v1/extract/url",
            "price_usd": 0.01,
            "category": "data",
            "description": "Structured web extraction — title, headings, clean text, links, metadata from any URL",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_search",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Web Search",
            "url": f"{HYDRA_BASE_URL}/v1/extract/search",
            "price_usd": 0.02,
            "category": "data",
            "description": "Web search with structured result extraction — titles, snippets, URLs",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_html2md",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA HTML to Markdown",
            "url": f"{HYDRA_BASE_URL}/v1/convert/html2md",
            "price_usd": 0.005,
            "category": "data",
            "description": "Convert HTML to clean Markdown — preserves headings, lists, links, code, tables",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_dns",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA DNS Lookup",
            "url": f"{HYDRA_BASE_URL}/v1/check/dns",
            "price_usd": 0.005,
            "category": "data",
            "description": "DNS record lookup — A, AAAA, MX, TXT, NS, CNAME via DNS-over-HTTPS",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_wikipedia",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Wikipedia",
            "url": f"{HYDRA_BASE_URL}/v1/data/wikipedia",
            "price_usd": 0.01,
            "category": "data",
            "description": "Wikipedia article summary with thumbnail, extract, and page URL",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_edgar",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA SEC EDGAR",
            "url": f"{HYDRA_BASE_URL}/v1/data/edgar",
            "price_usd": 0.02,
            "category": "data",
            "description": "SEC EDGAR filing search — 10-K, 10-Q, 8-K by company, ticker, or keyword",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_alpha",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Alpha Signal",
            "url": f"{HYDRA_BASE_URL}/v1/intelligence/alpha",
            "price_usd": 5.00,
            "category": "data",
            "description": "Composite alpha: regulatory risk + Fed rate probability + prediction market sentiment + momentum",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_pulse",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Regulatory Pulse",
            "url": f"{HYDRA_BASE_URL}/v1/intelligence/pulse",
            "price_usd": 0.50,
            "category": "data",
            "description": "Hourly regulatory pulse from all US financial agencies with composite risk signal",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_risk",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Risk Score",
            "url": f"{HYDRA_BASE_URL}/v1/intelligence/risk-score",
            "price_usd": 2.00,
            "category": "data",
            "description": "Real-time 0-100 regulatory risk score for any crypto token or DeFi protocol",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_alerts",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Push Alerts",
            "url": f"{HYDRA_BASE_URL}/v1/alerts/subscribe",
            "price_usd": 0.10,
            "category": "data",
            "description": "Webhook push alerts for regulatory events — $0.10 per 100 alerts delivered",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_router",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA x402 Router",
            "url": f"{HYDRA_BASE_URL}/v1/x402/route",
            "price_usd": 0.001,
            "category": "infrastructure",
            "description": "Intelligent x402 service routing — find the best service for any capability",
            "network": "base-mainnet",
        },
    },
    {
        "name": "x402_discovery_api_digest",
        "url": "https://x402-discovery-api.onrender.com/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Daily Digest",
            "url": f"{HYDRA_BASE_URL}/v1/intelligence/digest",
            "price_usd": 1.00,
            "category": "data",
            "description": "Daily regulatory + market digest for compliance teams and trading agents",
            "network": "base-mainnet",
        },
    },
    # ── Additional discovery platforms ───────────────────────────
    {
        "name": "glama_connectors",
        "url": "https://glama.ai/api/mcp/connectors",
        "method": "POST",
        "payload": {
            "name": "HYDRA Regulatory Intelligence",
            "url": f"{HYDRA_BASE_URL}/mcp",
            "repository": "https://github.com/OGCryptoKitty/hydra-arm3",
            "description": "55+ MCP tools: Kalshi KXFED-calibrated Fed rate probabilities, FDIC bank failure monitoring, alpha reports with Kelly sizing, regulatory intelligence, prediction markets, web extraction, search, conversion, dev tools, web checks, public data. 13 real-time data sources. x402 payments on Base.",
        },
    },
    {
        "name": "aiprox_registry",
        "url": "https://aiprox.dev/api/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA",
            "url": HYDRA_BASE_URL,
            "manifest": HYDRA_MANIFEST,
            "category": "intelligence",
            "description": "Regulatory intelligence + prediction market signals via x402 on Base. 55+ paid endpoints from $0.001 USDC. 13 real-time data sources, Kalshi KXFED-calibrated Fed rate probabilities, FDIC bank failure monitoring, alpha reports with Kelly sizing.",
            "chain": "base",
            "token": "USDC",
        },
    },
    {
        "name": "agent_arena_registry",
        "url": "https://agentarena.site/api/register",
        "method": "POST",
        "payload": {
            "name": "HYDRA Regulatory Intelligence",
            "url": HYDRA_BASE_URL,
            "manifest": HYDRA_MANIFEST,
            "capabilities": ["regulatory-intelligence", "prediction-markets", "fed-signals", "kxfed-calibration", "fdic-bank-failures", "alpha-kelly-sizing", "web-extraction", "search", "oracle-data", "economic-data"],
            "chain_id": 8453,
            "payment_token": "USDC",
        },
    },
    {
        "name": "x402_eco",
        "url": "https://www.x402.eco/api/services",
        "method": "POST",
        "payload": {
            "name": "HYDRA",
            "url": HYDRA_BASE_URL,
            "manifest": HYDRA_MANIFEST,
            "description": "Regulatory intelligence engine — 55+ x402 endpoints on Base. 13 real-time data sources. Kalshi KXFED-calibrated Fed rate probabilities, FDIC bank failure monitoring, alpha reports with Kelly sizing, risk scores, push alerts, web extraction, search.",
            "category": "data-intelligence",
            "chain": "base",
        },
    },
    {
        "name": "pulsemcp_submission",
        "url": "https://www.pulsemcp.com/api/servers",
        "method": "POST",
        "payload": {
            "name": "OGCryptoKitty/hydra-arm3",
            "url": f"{HYDRA_BASE_URL}/mcp",
            "repository": "https://github.com/OGCryptoKitty/hydra-arm3",
            "description": "HYDRA Regulatory Intelligence — 55+ MCP tools for regulatory risk scoring, prediction markets, Kalshi KXFED-calibrated Fed signals, FDIC bank failure monitoring, alpha reports with Kelly sizing, web extraction, search, and more. 13 real-time data sources. Pay-per-call via x402 on Base L2.",
            "transport": "streamable-http",
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
