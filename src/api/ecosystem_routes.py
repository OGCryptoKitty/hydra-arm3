"""
ecosystem_routes.py — x402 Ecosystem Hub
==========================================
Makes HYDRA the infrastructure layer of the x402 economy.
Instead of competing for the tiny pool of paying agents,
HYDRA becomes the discovery/routing layer ALL agents use first.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Query

logger = logging.getLogger("hydra.ecosystem")

router = APIRouter(prefix="/v1/x402", tags=["x402-ecosystem"])

# ── Known x402 Services Registry ──────────────────────────────────────
# HYDRA maintains the most complete index of x402-enabled services.
# This is seeded with known services and updated by crawling.

_KNOWN_SERVICES: list[dict] = [
    {
        "name": "HYDRA",
        "url": "https://hydra-api-nlnj.onrender.com",
        "manifest": "https://hydra-api-nlnj.onrender.com/.well-known/x402.json",
        "categories": ["regulatory", "prediction-markets", "web-extraction", "search", "conversion", "developer-tools", "web-checks", "public-data", "fed-intelligence", "oracle"],
        "endpoint_count": 40,
        "price_range": "$0.001 - $50.00",
        "chain": "base",
        "token": "USDC",
        "description": "40 paid endpoints: web extraction, search, conversion, developer tools, web checks, public data, regulatory intelligence, prediction markets, Fed signals, oracle data.",
    },
]

# Services discovered via crawling (populated at runtime)
_DISCOVERED_SERVICES: list[dict] = []
_LAST_CRAWL: float = 0
_CRAWL_INTERVAL = 3600  # 1 hour

# Known x402 manifest URLs to crawl
_CRAWL_TARGETS = [
    "https://x402-discovery-api.onrender.com/services",
    "https://x402.org/api/services",
    "https://x402scan.com/api/services",
    "https://x402list.fun/api/services",
    "https://x402-list.com/api/services",
    "https://the402.ai/v1/services",
]

_STATUS_CACHE: dict[str, dict] = {}
_STATUS_CACHE_TTL = 300  # 5 min


async def _crawl_x402_ecosystem() -> None:
    """Crawl known x402 directories and build the service index."""
    global _DISCOVERED_SERVICES, _LAST_CRAWL
    discovered = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for target in _CRAWL_TARGETS:
            try:
                resp = await client.get(target)
                if resp.status_code == 200:
                    data = resp.json()
                    services = data if isinstance(data, list) else data.get("services", data.get("data", []))
                    for svc in services:
                        if isinstance(svc, dict) and svc.get("url"):
                            discovered.append({
                                "name": svc.get("name", "Unknown"),
                                "url": svc["url"],
                                "manifest": svc.get("manifest", ""),
                                "categories": svc.get("categories", []),
                                "price_range": svc.get("price_range", "unknown"),
                                "chain": svc.get("chain", svc.get("network", "unknown")),
                                "token": svc.get("token", "USDC"),
                                "description": svc.get("description", "")[:200],
                                "source": target.split("/")[2],
                            })
            except Exception as exc:
                logger.debug("Crawl %s failed: %s", target, exc)

    # Deduplicate by URL
    seen_urls = set()
    deduped = []
    for svc in discovered:
        url = svc["url"].rstrip("/")
        if url not in seen_urls:
            seen_urls.add(url)
            deduped.append(svc)

    _DISCOVERED_SERVICES = deduped
    _LAST_CRAWL = time.time()
    logger.info("x402 ecosystem crawl complete: %d services discovered", len(deduped))


async def _ensure_fresh_index() -> None:
    if time.time() - _LAST_CRAWL > _CRAWL_INTERVAL:
        await _crawl_x402_ecosystem()


@router.get("/directory")
async def x402_directory(
    category: Optional[str] = Query(None, description="Filter by category"),
    chain: Optional[str] = Query(None, description="Filter by chain (base, ethereum, polygon, etc.)"),
    q: Optional[str] = Query(None, description="Search query"),
) -> dict:
    """
    The canonical x402 service directory.

    Returns all known x402-enabled services across the ecosystem.
    HYDRA crawls and indexes every known x402 directory hourly.
    Free endpoint — establishes HYDRA as the ecosystem hub.
    """
    await _ensure_fresh_index()

    all_services = _KNOWN_SERVICES + _DISCOVERED_SERVICES

    if category:
        cat_lower = category.lower()
        all_services = [s for s in all_services if cat_lower in [c.lower() for c in s.get("categories", [])]]

    if chain:
        chain_lower = chain.lower()
        all_services = [s for s in all_services if chain_lower in str(s.get("chain", "")).lower()]

    if q:
        q_lower = q.lower()
        all_services = [s for s in all_services if q_lower in s.get("name", "").lower() or q_lower in s.get("description", "").lower()]

    return {
        "directory": "HYDRA x402 Ecosystem Hub",
        "total_services": len(all_services),
        "last_crawl": datetime.fromtimestamp(_LAST_CRAWL, tz=timezone.utc).isoformat() if _LAST_CRAWL else None,
        "services": all_services,
        "meta": {
            "powered_by": "HYDRA — the x402 infrastructure layer",
            "hub_url": "https://hydra-api-nlnj.onrender.com",
            "paid_endpoints": "https://hydra-api-nlnj.onrender.com/.well-known/x402.json",
        },
    }


@router.get("/status")
async def x402_service_status(
    url: str = Query(..., description="x402 service base URL to check"),
) -> dict:
    """
    Real-time health and capability check of any x402 service.

    Fetches the service's x402 manifest, checks health endpoint,
    and returns a comprehensive status report.
    """
    cache_key = hashlib.md5(url.encode()).hexdigest()
    if cache_key in _STATUS_CACHE:
        cached = _STATUS_CACHE[cache_key]
        if time.time() - cached.get("_ts", 0) < _STATUS_CACHE_TTL:
            return cached

    result: dict[str, Any] = {
        "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    base = url.rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Health check
        try:
            resp = await client.get(f"{base}/health")
            result["health"] = {"status": resp.status_code, "ok": resp.status_code == 200}
        except Exception:
            result["health"] = {"status": "unreachable", "ok": False}

        # x402 manifest
        try:
            resp = await client.get(f"{base}/.well-known/x402.json")
            if resp.status_code == 200:
                manifest = resp.json()
                endpoints = manifest.get("endpoints", [])
                result["x402"] = {
                    "manifest_ok": True,
                    "endpoint_count": len(endpoints),
                    "price_range": f"${min(e.get('price_usdc', 0) for e in endpoints):.3f} - ${max(e.get('price_usdc', 0) for e in endpoints):.2f}" if endpoints else "none",
                    "payment_address": manifest.get("payment_address", "unknown"),
                }
            else:
                result["x402"] = {"manifest_ok": False, "status": resp.status_code}
        except Exception:
            result["x402"] = {"manifest_ok": False, "status": "error"}

        # MCP manifest
        try:
            resp = await client.get(f"{base}/.well-known/mcp.json")
            result["mcp"] = {"available": resp.status_code == 200}
        except Exception:
            result["mcp"] = {"available": False}

    result["_ts"] = time.time()
    _STATUS_CACHE[cache_key] = result
    return result


@router.post("/route")
async def x402_route(
    capability: str = Query(..., description="What you need (e.g., 'web scraping', 'regulatory scan', 'price data')"),
    max_price: Optional[float] = Query(None, description="Maximum price in USDC"),
    chain: Optional[str] = Query("base", description="Preferred chain"),
) -> dict:
    """
    Intelligent x402 service routing.

    Given a capability request, returns the best x402 service to call,
    with pricing and connection details. HYDRA routes to itself when
    competitive, or to the best alternative.
    """
    await _ensure_fresh_index()

    all_services = _KNOWN_SERVICES + _DISCOVERED_SERVICES
    cap_lower = capability.lower()

    # Score services by relevance
    scored = []
    for svc in all_services:
        score = 0
        name_desc = (svc.get("name", "") + " " + svc.get("description", "")).lower()
        categories = " ".join(svc.get("categories", [])).lower()

        # Keyword matching
        for word in cap_lower.split():
            if word in name_desc:
                score += 2
            if word in categories:
                score += 3

        if score > 0:
            scored.append({"service": svc, "relevance_score": score})

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)

    return {
        "query": capability,
        "matches": len(scored),
        "recommended": scored[:5],
        "meta": {
            "note": "HYDRA x402 Ecosystem Hub — routing agents to the best x402 service for their needs",
            "hydra_capabilities": "https://hydra-api-nlnj.onrender.com/.well-known/x402.json",
        },
    }


@router.get("/stats")
async def x402_ecosystem_stats() -> dict:
    """
    Aggregate statistics on the x402 ecosystem.

    Free endpoint showing the health and growth of the x402 economy.
    Positions HYDRA as the authoritative data source.
    """
    await _ensure_fresh_index()

    all_services = _KNOWN_SERVICES + _DISCOVERED_SERVICES
    chains = {}
    categories = {}
    for svc in all_services:
        chain = svc.get("chain", "unknown")
        chains[chain] = chains.get(chain, 0) + 1
        for cat in svc.get("categories", []):
            categories[cat] = categories.get(cat, 0) + 1

    return {
        "ecosystem": "x402",
        "indexed_by": "HYDRA x402 Ecosystem Hub",
        "total_services": len(all_services),
        "by_chain": chains,
        "by_category": categories,
        "last_crawl": datetime.fromtimestamp(_LAST_CRAWL, tz=timezone.utc).isoformat() if _LAST_CRAWL else None,
        "crawl_sources": len(_CRAWL_TARGETS),
    }
