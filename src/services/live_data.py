"""
HYDRA Arm 3 — Live Economic Data Pipeline
===========================================
Fetches real-time economic data from public government sources to replace
hardcoded values. All sources are free, public, and require no API keys.

Sources:
  - Federal Reserve: FRED API (free, requires key) or RSS feeds (no key)
  - BLS: Employment data via public JSON API
  - Federal Reserve website: FOMC statements via RSS
  - Treasury: Yield curve data

Fallback: If any live fetch fails, returns None and the caller uses
hardcoded data. This ensures the system ALWAYS works.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("hydra.live_data")

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_CACHE: dict[str, tuple[datetime, Any]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour


def _get_cached(key: str) -> Optional[Any]:
    """Return cached value if fresh, else None."""
    if key in _CACHE:
        cached_at, value = _CACHE[key]
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if age < _CACHE_TTL_SECONDS:
            return value
    return None


def _set_cached(key: str, value: Any) -> None:
    _CACHE[key] = (datetime.now(timezone.utc), value)


async def fetch_latest_fed_statement() -> Optional[dict[str, Any]]:
    """
    Fetch the latest FOMC press release from the Federal Reserve RSS feed.
    Returns parsed metadata or None on failure.
    """
    cached = _get_cached("fed_statement")
    if cached:
        return cached

    url = "https://www.federalreserve.gov/feeds/press_monetary.xml"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        import feedparser
        feed = feedparser.parse(resp.text)
        if not feed.entries:
            return None

        latest = feed.entries[0]
        result = {
            "title": latest.get("title", ""),
            "link": latest.get("link", ""),
            "published": latest.get("published", ""),
            "summary": latest.get("summary", ""),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "is_live": True,
        }
        _set_cached("fed_statement", result)
        logger.info("Fetched live Fed statement: %s", result["title"][:80])
        return result
    except Exception as exc:
        logger.warning("Failed to fetch live Fed statement: %s", exc)
        return None


async def fetch_treasury_yields() -> Optional[dict[str, Any]]:
    """
    Fetch current Treasury yield curve from Treasury.gov XML feed.
    Returns yield data or None on failure.
    """
    cached = _get_cached("treasury_yields")
    if cached:
        return cached

    url = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/2026?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        # Parse the CSV — last row is most recent
        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            return None
        headers = [h.strip('"') for h in lines[0].split(",")]
        values = [v.strip('"') for v in lines[-1].split(",")]

        yields = {}
        for h, v in zip(headers, values):
            try:
                yields[h] = float(v)
            except (ValueError, TypeError):
                yields[h] = v

        result = {
            "yields": yields,
            "date": yields.get("Date", ""),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "is_live": True,
        }
        _set_cached("treasury_yields", result)
        logger.info("Fetched live Treasury yields for: %s", result["date"])
        return result
    except Exception as exc:
        logger.warning("Failed to fetch Treasury yields: %s", exc)
        return None


async def fetch_fed_funds_rate() -> Optional[dict[str, Any]]:
    """
    Fetch current effective federal funds rate from NY Fed.
    """
    cached = _get_cached("fed_funds_rate")
    if cached:
        return cached

    url = "https://markets.newyorkfed.org/api/rates/effr/last/1.json"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        data = resp.json()
        if "refRates" in data and data["refRates"]:
            rate_data = data["refRates"][0]
            result = {
                "effective_rate": rate_data.get("percentRate"),
                "target_rate_from": rate_data.get("targetRateFrom"),
                "target_rate_to": rate_data.get("targetRateTo"),
                "date": rate_data.get("effectiveDate"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_live": True,
            }
            _set_cached("fed_funds_rate", result)
            logger.info("Fetched live Fed funds rate: %s%%", result["effective_rate"])
            return result
    except Exception as exc:
        logger.warning("Failed to fetch Fed funds rate: %s", exc)
    return None


async def fetch_all_live_data() -> dict[str, Any]:
    """
    Fetch all available live economic data. Returns whatever is available,
    with None for anything that failed.
    """
    import asyncio

    results = await asyncio.gather(
        fetch_fed_funds_rate(),
        fetch_latest_fed_statement(),
        fetch_treasury_yields(),
        return_exceptions=True,
    )

    return {
        "fed_funds_rate": results[0] if not isinstance(results[0], Exception) else None,
        "latest_fed_statement": results[1] if not isinstance(results[1], Exception) else None,
        "treasury_yields": results[2] if not isinstance(results[2], Exception) else None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
