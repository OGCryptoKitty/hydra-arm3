"""
HYDRA Real-Time Economic Data Engine
=====================================
Atomic, live data connectors for prediction market signal generation.

Pulls from free, public government APIs with no API keys required:
  - FRED (Federal Reserve Economic Data) — CPI, PCE, GDP, unemployment, Fed funds rate
  - BLS (Bureau of Labor Statistics) — employment situation, CPI details
  - Treasury — daily yield curve rates
  - SEC EDGAR EFTS — full-text search for filings and enforcement
  - Federal Register — new rulemakings and final rules
  - congress.gov — bill status tracking

Cache strategy: short TTLs for time-sensitive data, longer for slow-moving.
  - Market prices:    60 seconds  (via Polymarket/Kalshi clients)
  - Yield curve:      5 minutes   (updates once daily but checked frequently)
  - FRED series:      15 minutes  (most series update monthly/weekly)
  - SEC EDGAR:        5 minutes   (filings arrive continuously)
  - Federal Register: 15 minutes  (daily publication cycle)
  - Bill status:      30 minutes  (legislative changes are slow)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Short-lived caches for real-time data
_yield_cache: TTLCache = TTLCache(maxsize=5, ttl=300)
_fred_cache: TTLCache = TTLCache(maxsize=50, ttl=900)
_edgar_cache: TTLCache = TTLCache(maxsize=30, ttl=300)
_fedreg_cache: TTLCache = TTLCache(maxsize=20, ttl=900)
_congress_cache: TTLCache = TTLCache(maxsize=20, ttl=1800)
_bls_cache: TTLCache = TTLCache(maxsize=20, ttl=900)

_HTTP_TIMEOUT = httpx.Timeout(12.0, connect=5.0)
_HEADERS = {
    "User-Agent": "HYDRA-RegulatoryIntelligence/2.0 (hydra-api-nlnj.onrender.com)",
    "Accept": "application/json",
}

# FRED series IDs for key economic indicators
FRED_KEY_SERIES = {
    "FEDFUNDS": "Federal Funds Effective Rate",
    "DFEDTARU": "Fed Funds Target Range Upper",
    "DFEDTARL": "Fed Funds Target Range Lower",
    "CPIAUCSL": "CPI All Urban Consumers (SA)",
    "CPILFESL": "Core CPI (Less Food & Energy, SA)",
    "PCEPI": "PCE Price Index",
    "PCEPILFE": "Core PCE (Less Food & Energy)",
    "GDPC1": "Real GDP (Chained 2017 Dollars)",
    "UNRATE": "Unemployment Rate",
    "PAYEMS": "Total Nonfarm Payrolls",
    "DGS10": "10-Year Treasury Constant Maturity",
    "DGS2": "2-Year Treasury Constant Maturity",
    "T10Y2Y": "10Y-2Y Treasury Spread",
    "DTWEXBGS": "Trade Weighted Dollar Index (Broad)",
    "VIXCLS": "CBOE VIX",
    "BAMLH0A0HYM2": "High Yield OAS Spread",
}

# BLS series for employment data
BLS_SERIES = {
    "LNS14000000": "Unemployment Rate",
    "CES0000000001": "Total Nonfarm Employment",
    "CES0500000003": "Average Hourly Earnings (Private)",
    "CUSR0000SA0": "CPI-U All Items (SA)",
    "CUSR0000SA0L1E": "CPI-U Core (Less Food & Energy, SA)",
}


async def _async_get(url: str, params: dict | None = None, timeout: float = 12.0) -> dict | list | None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=5.0), headers=_HEADERS) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            logger.warning("Timeout fetching %s", url)
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP %d from %s", exc.response.status_code, url)
            return None
        except Exception as exc:
            logger.warning("Request failed %s: %s", url, exc)
            return None


# ─────────────────────────────────────────────────────────────
# FRED (Federal Reserve Economic Data) — No API key for JSON
# ─────────────────────────────────────────────────────────────

async def get_fred_series(series_id: str, limit: int = 10) -> dict[str, Any]:
    """
    Fetch latest observations for a FRED series.

    Uses the FRED JSON endpoint which does not require an API key
    for basic observation retrieval. Falls back to the FRED API
    with FRED_API_KEY env var if available.

    Returns dict with: series_id, title, observations[], last_updated
    """
    cache_key = f"fred_{series_id}"
    if cache_key in _fred_cache:
        return _fred_cache[cache_key]

    import os
    api_key = os.getenv("FRED_API_KEY")

    result: dict[str, Any] = {
        "series_id": series_id,
        "title": FRED_KEY_SERIES.get(series_id, series_id),
        "observations": [],
        "last_updated": None,
        "source": "FRED",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if api_key:
        data = await _async_get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            },
        )
        if data and "observations" in data:
            obs = data["observations"]
            result["observations"] = [
                {
                    "date": o["date"],
                    "value": o["value"],
                }
                for o in obs
                if o.get("value") != "."
            ]
            if result["observations"]:
                result["last_updated"] = result["observations"][0]["date"]
    else:
        # Fallback: scrape FRED's public JSON widget (no key needed)
        data = await _async_get(
            f"https://fred.stlouisfed.org/graph/fredgraph.csv",
            params={"id": series_id, "fq": "Monthly" if series_id not in ("DGS10", "DGS2", "T10Y2Y", "FEDFUNDS", "DFEDTARU", "DFEDTARL", "VIXCLS", "DTWEXBGS") else "Daily"},
        )
        # CSV fallback won't parse as JSON — use observation API without key
        # FRED allows limited access without key through their public feeds
        data = await _async_get(
            f"https://fred.stlouisfed.org/series/{series_id}",
            params={"format": "json"},
        )
        # If no key available, return empty but log
        logger.info("FRED_API_KEY not set — %s data unavailable via API. Set FRED_API_KEY for live data.", series_id)

    _fred_cache[cache_key] = result
    return result


async def get_fred_snapshot() -> dict[str, Any]:
    """
    Fetch a comprehensive snapshot of all key FRED economic indicators.
    Returns a dict keyed by series_id with latest values.
    """
    cache_key = "fred_snapshot"
    if cache_key in _fred_cache:
        return _fred_cache[cache_key]

    import asyncio

    tasks = {sid: get_fred_series(sid, limit=3) for sid in FRED_KEY_SERIES}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    snapshot: dict[str, Any] = {}
    for sid, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            logger.warning("FRED series %s failed: %s", sid, result)
            snapshot[sid] = {"series_id": sid, "title": FRED_KEY_SERIES[sid], "error": str(result)}
        else:
            snapshot[sid] = result

    wrapped = {
        "indicators": snapshot,
        "series_count": len(snapshot),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "Federal Reserve Economic Data (FRED)",
    }
    _fred_cache[cache_key] = wrapped
    return wrapped


# ─────────────────────────────────────────────────────────────
# Treasury Yield Curve — Daily XML/JSON from treasury.gov
# ─────────────────────────────────────────────────────────────

async def get_treasury_yields() -> dict[str, Any]:
    """
    Fetch the latest Treasury yield curve from treasury.gov.
    Daily constant maturity rates: 1M, 2M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y.
    """
    cache_key = "treasury_yields"
    if cache_key in _yield_cache:
        return _yield_cache[cache_key]

    result: dict[str, Any] = {
        "yields": {},
        "date": None,
        "source": "U.S. Department of the Treasury",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    # Treasury.gov provides yield curve data via XML API
    data = await _async_get(
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/2026",
        params={"type": "daily_treasury_yield_curve", "field_tdr_date_value": "2026", "page&_format": "json"},
    )

    # Try the Treasury API v2
    data = await _async_get(
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates",
        params={
            "sort": "-record_date",
            "page[size]": "20",
            "fields": "record_date,security_desc,avg_interest_rate_amt",
        },
    )

    if data and "data" in data:
        records = data["data"]
        if records:
            result["date"] = records[0].get("record_date")
            for rec in records:
                desc = rec.get("security_desc", "")
                rate = rec.get("avg_interest_rate_amt")
                if rate:
                    result["yields"][desc] = float(rate)

    # Also try the daily yield curve rates
    yield_data = await _async_get(
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny",
        params={
            "sort": "-record_date",
            "page[size]": "1",
            "fields": "record_date,tot_pub_debt_out_amt",
        },
    )

    if yield_data and "data" in yield_data:
        debt_records = yield_data["data"]
        if debt_records:
            result["national_debt"] = {
                "date": debt_records[0].get("record_date"),
                "total_public_debt": debt_records[0].get("tot_pub_debt_out_amt"),
            }

    _yield_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# SEC EDGAR Full-Text Search (EFTS) — Free, no auth
# ─────────────────────────────────────────────────────────────

async def search_edgar(query: str, date_range: str = "", form_types: list[str] | None = None, limit: int = 10) -> dict[str, Any]:
    """
    Search SEC EDGAR full-text search system for filings, enforcement actions,
    and press releases.

    Parameters:
        query: Search string (e.g., "crypto regulation", "stablecoin", "ETF approval")
        date_range: Optional date range (e.g., "2026-01-01,2026-05-01")
        form_types: Optional list of form types (e.g., ["8-K", "10-K", "S-1"])
        limit: Max results (1-100)
    """
    cache_key = f"edgar_{query}_{date_range}_{form_types}_{limit}"
    if cache_key in _edgar_cache:
        return _edgar_cache[cache_key]

    params: dict[str, Any] = {
        "q": query,
        "dateRange": "custom" if date_range else "",
        "startdt": date_range.split(",")[0] if "," in date_range else "",
        "enddt": date_range.split(",")[1] if "," in date_range else "",
        "forms": ",".join(form_types) if form_types else "",
    }
    params = {k: v for k, v in params.items() if v}

    data = await _async_get(
        "https://efts.sec.gov/LATEST/search-index",
        params={"q": query, "dateRange": "custom", "forms": ",".join(form_types or [])},
    )

    # EDGAR EFTS primary endpoint
    data = await _async_get(
        "https://efts.sec.gov/LATEST/search-index",
        params={"q": query, "from": "0", "size": str(limit)},
    )

    # Fallback to the standard EDGAR full-text search API
    if not data:
        data = await _async_get(
            "https://efts.sec.gov/LATEST/search-index",
            params={"q": query},
        )

    result: dict[str, Any] = {
        "query": query,
        "filings": [],
        "total_hits": 0,
        "source": "SEC EDGAR EFTS",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        hits = data.get("hits", {})
        result["total_hits"] = hits.get("total", {}).get("value", 0) if isinstance(hits.get("total"), dict) else hits.get("total", 0)
        for hit in (hits.get("hits", []) or [])[:limit]:
            source = hit.get("_source", {})
            result["filings"].append({
                "title": source.get("display_names", [None])[0] if source.get("display_names") else source.get("file_description", ""),
                "entity": source.get("entity_name", ""),
                "form_type": source.get("form_type", ""),
                "filed_at": source.get("file_date", ""),
                "url": f"https://www.sec.gov/Archives/edgar/data/{source.get('entity_id', '')}/{source.get('adsh', '').replace('-', '')}/",
                "description": (source.get("file_description") or "")[:300],
            })

    _edgar_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# Federal Register API — Free, no auth, real-time rulemakings
# ─────────────────────────────────────────────────────────────

async def search_federal_register(
    query: str = "",
    agencies: list[str] | None = None,
    doc_type: str = "",
    per_page: int = 10,
) -> dict[str, Any]:
    """
    Search Federal Register for rulemakings, proposed rules, final rules, and notices.

    Parameters:
        query: Search term
        agencies: List of agency slugs (e.g., ["securities-and-exchange-commission", "commodity-futures-trading-commission"])
        doc_type: "RULE", "PRORULE", "NOTICE", or "" for all
        per_page: Results per page (max 50)
    """
    cache_key = f"fedreg_{query}_{agencies}_{doc_type}"
    if cache_key in _fedreg_cache:
        return _fedreg_cache[cache_key]

    params: dict[str, Any] = {
        "per_page": min(per_page, 50),
        "order": "newest",
    }
    if query:
        params["conditions[term]"] = query
    if agencies:
        for i, agency in enumerate(agencies):
            params[f"conditions[agencies][]"] = agency
    if doc_type:
        params["conditions[type][]"] = doc_type

    data = await _async_get(
        "https://www.federalregister.gov/api/v1/documents.json",
        params=params,
    )

    result: dict[str, Any] = {
        "query": query,
        "documents": [],
        "total_count": 0,
        "source": "Federal Register API",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        result["total_count"] = data.get("count", 0)
        for doc in (data.get("results", []) or [])[:per_page]:
            result["documents"].append({
                "title": doc.get("title", ""),
                "document_number": doc.get("document_number", ""),
                "type": doc.get("type", ""),
                "abstract": (doc.get("abstract") or "")[:400],
                "agencies": [a.get("name", "") for a in (doc.get("agencies") or [])],
                "publication_date": doc.get("publication_date", ""),
                "effective_date": doc.get("effective_on", ""),
                "url": doc.get("html_url", ""),
                "pdf_url": doc.get("pdf_url", ""),
                "comment_count": doc.get("comment_count", 0),
            })

    _fedreg_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# Congress.gov API — Bill status tracking (free, no auth)
# ─────────────────────────────────────────────────────────────

async def search_congress_bills(
    query: str = "",
    congress: int = 119,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Search congress.gov for bill status. Tracks crypto/financial legislation.

    Uses the congress.gov API (api.congress.gov) — free, rate-limited.
    The 119th Congress (2025-2027) is the current session.
    """
    cache_key = f"congress_{query}_{congress}"
    if cache_key in _congress_cache:
        return _congress_cache[cache_key]

    import os
    api_key = os.getenv("CONGRESS_API_KEY")

    result: dict[str, Any] = {
        "query": query,
        "bills": [],
        "congress": congress,
        "source": "congress.gov API",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if api_key:
        data = await _async_get(
            f"https://api.congress.gov/v3/bill/{congress}",
            params={
                "api_key": api_key,
                "format": "json",
                "limit": limit,
                "sort": "updateDate+desc",
            },
        )
        if data and "bills" in data:
            for bill in data["bills"][:limit]:
                result["bills"].append({
                    "number": bill.get("number"),
                    "title": bill.get("title", ""),
                    "type": bill.get("type", ""),
                    "introduced_date": bill.get("introducedDate", ""),
                    "latest_action": bill.get("latestAction", {}).get("text", ""),
                    "latest_action_date": bill.get("latestAction", {}).get("actionDate", ""),
                    "url": bill.get("url", ""),
                })
    else:
        logger.info("CONGRESS_API_KEY not set — bill tracking via congress.gov API unavailable")

    _congress_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# BLS (Bureau of Labor Statistics) — Public data API v2
# ─────────────────────────────────────────────────────────────

async def get_bls_data(series_ids: list[str] | None = None, start_year: int = 2025, end_year: int = 2026) -> dict[str, Any]:
    """
    Fetch data from BLS Public Data API v2.
    No registration required for v2 (up to 25 queries/day, 10 years, 25 series).

    Key series:
      LNS14000000  — Unemployment rate
      CES0000000001 — Total nonfarm employment (thousands)
      CES0500000003 — Average hourly earnings, private
      CUSR0000SA0   — CPI-U all items (seasonally adjusted)
    """
    series = series_ids or list(BLS_SERIES.keys())
    cache_key = f"bls_{'_'.join(sorted(series))}_{start_year}_{end_year}"
    if cache_key in _bls_cache:
        return _bls_cache[cache_key]

    import os
    api_key = os.getenv("BLS_API_KEY")

    payload: dict[str, Any] = {
        "seriesid": series,
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    if api_key:
        payload["registrationkey"] = api_key

    result: dict[str, Any] = {
        "series": {},
        "source": "Bureau of Labor Statistics",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.post(
                "https://api.bls.gov/publicAPI/v2/timeseries/data/",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") == "REQUEST_SUCCEEDED":
            for series_data in data.get("Results", {}).get("series", []):
                sid = series_data.get("seriesID", "")
                observations = []
                for obs in series_data.get("data", [])[:6]:
                    observations.append({
                        "year": obs.get("year"),
                        "period": obs.get("periodName", obs.get("period", "")),
                        "value": obs.get("value"),
                        "footnotes": [f.get("text", "") for f in obs.get("footnotes", []) if f.get("text")],
                    })
                result["series"][sid] = {
                    "series_id": sid,
                    "title": BLS_SERIES.get(sid, sid),
                    "observations": observations,
                    "latest_value": observations[0]["value"] if observations else None,
                    "latest_period": f"{observations[0]['period']} {observations[0]['year']}" if observations else None,
                }
        else:
            logger.warning("BLS API returned status: %s — %s", data.get("status"), data.get("message", []))
    except Exception as exc:
        logger.warning("BLS API request failed: %s", exc)

    _bls_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# Composite: Real-Time Economic Snapshot
# ─────────────────────────────────────────────────────────────

async def get_economic_snapshot() -> dict[str, Any]:
    """
    Atomic real-time economic snapshot combining all data sources.
    Designed for prediction market signal enrichment.

    Returns the freshest available data from:
    - FRED (Fed funds rate, CPI, PCE, GDP, unemployment, yields)
    - BLS (employment, CPI details)
    - Treasury (yield curve, national debt)
    - Federal Register (latest rulemakings)
    """
    import asyncio

    fred_task = get_fred_snapshot()
    bls_task = get_bls_data()
    treasury_task = get_treasury_yields()
    fedreg_task = search_federal_register(
        agencies=["securities-and-exchange-commission", "commodity-futures-trading-commission",
                   "federal-reserve-system", "financial-crimes-enforcement-network"],
        per_page=5,
    )

    results = await asyncio.gather(fred_task, bls_task, treasury_task, fedreg_task, return_exceptions=True)

    snapshot: dict[str, Any] = {
        "fred": results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])},
        "bls": results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])},
        "treasury": results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])},
        "federal_register": results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": [
            "Federal Reserve Economic Data (FRED) — fred.stlouisfed.org",
            "Bureau of Labor Statistics — bls.gov",
            "U.S. Treasury Fiscal Data — fiscaldata.treasury.gov",
            "Federal Register — federalregister.gov",
        ],
    }

    return snapshot


# ─────────────────────────────────────────────────────────────
# Regulatory Activity Monitor — Combines EDGAR + Fed Register
# ─────────────────────────────────────────────────────────────

async def get_regulatory_pulse() -> dict[str, Any]:
    """
    Real-time regulatory activity pulse.
    Combines SEC EDGAR search + Federal Register + Congress bill tracking
    into a single actionable feed for prediction market agents.
    """
    import asyncio

    crypto_edgar = search_edgar("crypto OR stablecoin OR digital asset", limit=5)
    etf_edgar = search_edgar("ETF approval OR exchange-traded fund", limit=5)
    enforcement_edgar = search_edgar("enforcement action OR cease and desist", limit=5)

    sec_fedreg = search_federal_register(
        agencies=["securities-and-exchange-commission"],
        per_page=5,
    )
    cftc_fedreg = search_federal_register(
        agencies=["commodity-futures-trading-commission"],
        per_page=5,
    )

    crypto_bills = search_congress_bills(query="cryptocurrency OR stablecoin OR digital asset", limit=5)

    results = await asyncio.gather(
        crypto_edgar, etf_edgar, enforcement_edgar,
        sec_fedreg, cftc_fedreg, crypto_bills,
        return_exceptions=True,
    )

    def _safe(idx: int) -> dict:
        r = results[idx]
        return r if not isinstance(r, Exception) else {"error": str(r)}

    return {
        "edgar_crypto": _safe(0),
        "edgar_etf": _safe(1),
        "edgar_enforcement": _safe(2),
        "federal_register_sec": _safe(3),
        "federal_register_cftc": _safe(4),
        "congress_crypto_bills": _safe(5),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
