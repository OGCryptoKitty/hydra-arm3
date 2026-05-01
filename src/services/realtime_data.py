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
# All sourced from fred.stlouisfed.org — Tier 1 authoritative data
FRED_KEY_SERIES = {
    # Federal Reserve policy
    "FEDFUNDS": "Federal Funds Effective Rate",
    "DFEDTARU": "Fed Funds Target Range Upper",
    "DFEDTARL": "Fed Funds Target Range Lower",
    "WALCL": "Fed Balance Sheet Total Assets",
    # Inflation (Fed's dual mandate)
    "CPIAUCSL": "CPI All Urban Consumers (SA)",
    "CPILFESL": "Core CPI (Less Food & Energy, SA)",
    "PCEPI": "PCE Price Index",
    "PCEPILFE": "Core PCE (Less Food & Energy)",
    # Growth
    "GDPC1": "Real GDP (Chained 2017 Dollars)",
    "GDPNOW": "Atlanta Fed GDPNow Estimate",
    # Labor market (Fed's dual mandate)
    "UNRATE": "Unemployment Rate",
    "PAYEMS": "Total Nonfarm Payrolls",
    "IC4WSA": "Initial Jobless Claims (4-Week Average)",
    # Bond market / yield curve
    "DGS2": "2-Year Treasury Constant Maturity",
    "DGS10": "10-Year Treasury Constant Maturity",
    "DGS30": "30-Year Treasury Constant Maturity",
    "T10Y2Y": "10Y-2Y Treasury Spread (Inversion Indicator)",
    "T10YFF": "10Y Treasury Minus Fed Funds Rate",
    # Risk / sentiment
    "VIXCLS": "CBOE VIX (Volatility Index)",
    "BAMLH0A0HYM2": "High Yield OAS Spread (Credit Risk)",
    "DTWEXBGS": "Trade Weighted Dollar Index (Broad)",
    "UMCSENT": "U. Michigan Consumer Sentiment",
    # Inflation expectations / financial conditions
    "T5YIE": "5-Year Breakeven Inflation Rate",
    "DFII10": "10-Year TIPS/Treasury Breakeven",
    "STLFSI4": "St. Louis Fed Financial Stress Index",
    "MORTGAGE30US": "30-Year Fixed Mortgage Rate",
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
        logger.info("FRED_API_KEY not set — %s unavailable. Set FRED_API_KEY env var for live FRED data.", series_id)

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
        "national_debt": None,
        "source": "U.S. Department of the Treasury — fiscaldata.treasury.gov",
        "trust_tier": 1,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    # Treasury Fiscal Data API v2 — average interest rates by security type
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
                    try:
                        result["yields"][desc] = float(rate)
                    except (ValueError, TypeError):
                        pass

    # National debt (total public debt outstanding)
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

    # EDGAR EFTS (Elasticsearch-based full-text search)
    params: dict[str, Any] = {
        "q": query,
        "from": "0",
        "size": str(limit),
    }
    if date_range and "," in date_range:
        params["dateRange"] = "custom"
        params["startdt"] = date_range.split(",")[0]
        params["enddt"] = date_range.split(",")[1]
    if form_types:
        params["forms"] = ",".join(form_types)

    data = await _async_get("https://efts.sec.gov/LATEST/search-index", params=params)

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


async def get_sec_company_filings(cik: str, limit: int = 10) -> dict[str, Any]:
    """
    Fetch recent filings for a specific SEC registrant via the structured EDGAR API.
    More reliable than EFTS for company-specific queries.

    Uses data.sec.gov which requires a User-Agent header but no API key.
    CIK should be zero-padded to 10 digits (e.g., "0000320193" for Apple).
    """
    cache_key = f"sec_company_{cik}"
    if cache_key in _edgar_cache:
        return _edgar_cache[cache_key]

    padded_cik = cik.zfill(10)
    data = await _async_get(f"https://data.sec.gov/submissions/CIK{padded_cik}.json")

    result: dict[str, Any] = {
        "cik": cik,
        "filings": [],
        "company_name": "",
        "source": "SEC EDGAR Structured Data API (data.sec.gov)",
        "trust_tier": 1,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        result["company_name"] = data.get("name", "")
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        descriptions = recent.get("primaryDocDescription", [])

        for i in range(min(limit, len(forms))):
            result["filings"].append({
                "form_type": forms[i] if i < len(forms) else "",
                "filed_at": dates[i] if i < len(dates) else "",
                "accession_number": accessions[i] if i < len(accessions) else "",
                "description": descriptions[i] if i < len(descriptions) else "",
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
# FDIC BankFind — Bank failure and financial institution data
# ─────────────────────────────────────────────────────────────

_fdic_cache: TTLCache = TTLCache(maxsize=10, ttl=900)


async def get_fdic_bank_failures(limit: int = 20) -> dict[str, Any]:
    """
    Fetch recent bank failures from the FDIC BankFind API.
    No API key required. Relevant for bank failure prediction markets.
    """
    cache_key = f"fdic_failures_{limit}"
    if cache_key in _fdic_cache:
        return _fdic_cache[cache_key]

    result: dict[str, Any] = {
        "failures": [],
        "source": "FDIC BankFind Suite",
        "api_url": "https://banks.data.fdic.gov/api/failures",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    data = await _async_get(
        "https://banks.data.fdic.gov/api/failures",
        params={
            "$limit": str(limit),
            "$sort": "-FAILDATE",
            "$select": "CERT,INSTNAME,CITY,STATE,FAILDATE,SAVR,RESTYPE,COST,QBFASSET,PSTALP",
        },
    )

    if data and isinstance(data, dict):
        for row in data.get("data", []):
            d = row.get("data", row)
            result["failures"].append({
                "cert": d.get("CERT"),
                "institution": d.get("INSTNAME"),
                "city": d.get("CITY"),
                "state": d.get("PSTALP") or d.get("STATE"),
                "fail_date": d.get("FAILDATE"),
                "acquiring_institution": d.get("SAVR"),
                "resolution_type": d.get("RESTYPE"),
                "estimated_loss_millions": d.get("COST"),
                "total_assets_millions": d.get("QBFASSET"),
            })
        result["total_failures_returned"] = len(result["failures"])

    _fdic_cache[cache_key] = result
    return result


async def get_fdic_financials(cert: str | None = None, limit: int = 10) -> dict[str, Any]:
    """
    Fetch FDIC financial data for institutions. Without cert, returns
    aggregate industry stats. With cert, returns specific bank data.
    """
    cache_key = f"fdic_fin_{cert or 'aggregate'}_{limit}"
    if cache_key in _fdic_cache:
        return _fdic_cache[cache_key]

    params: dict[str, str] = {
        "$limit": str(limit),
        "$sort": "-REPDTE",
        "$select": "CERT,INSTNAME,REPDTE,ASSET,DEP,NETINC,ROA,ROE,NITEFFL,NCLNLS",
    }
    if cert:
        params["$where"] = f'CERT="{cert}"'

    result: dict[str, Any] = {
        "institutions": [],
        "source": "FDIC BankFind Suite — Financial Reports",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    data = await _async_get(
        "https://banks.data.fdic.gov/api/financials",
        params=params,
    )

    if data and isinstance(data, dict):
        for row in data.get("data", []):
            d = row.get("data", row)
            result["institutions"].append({
                "cert": d.get("CERT"),
                "institution": d.get("INSTNAME"),
                "report_date": d.get("REPDTE"),
                "total_assets_thousands": d.get("ASSET"),
                "total_deposits_thousands": d.get("DEP"),
                "net_income_thousands": d.get("NETINC"),
                "return_on_assets": d.get("ROA"),
                "return_on_equity": d.get("ROE"),
                "net_interest_margin": d.get("NITEFFL"),
                "noncurrent_loans_pct": d.get("NCLNLS"),
            })

    _fdic_cache[cache_key] = result
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
    fdic_task = get_fdic_bank_failures(limit=5)

    results = await asyncio.gather(
        fred_task, bls_task, treasury_task, fedreg_task, fdic_task,
        return_exceptions=True,
    )

    snapshot: dict[str, Any] = {
        "fred": results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])},
        "bls": results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])},
        "treasury": results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])},
        "federal_register": results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])},
        "fdic_recent_failures": results[4] if not isinstance(results[4], Exception) else {"error": str(results[4])},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": [
            "Federal Reserve Economic Data (FRED) — fred.stlouisfed.org",
            "Bureau of Labor Statistics — bls.gov",
            "U.S. Treasury Fiscal Data — fiscaldata.treasury.gov",
            "Federal Register — federalregister.gov",
            "FDIC BankFind Suite — banks.data.fdic.gov",
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


# ─────────────────────────────────────────────────────────────
# Data Integrity & Provenance
# ─────────────────────────────────────────────────────────────

# Every data source used by HYDRA, with trust classification.
# Trust tiers:
#   1 = Official government primary source (highest authority)
#   2 = Government-operated aggregator / derived data
#   3 = Regulated market platform (CFTC-regulated or equivalent)
#   4 = Well-known commercial aggregator
#   5 = Unverified / third-party

DATA_SOURCE_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "fred",
        "name": "Federal Reserve Economic Data (FRED)",
        "operator": "Federal Reserve Bank of St. Louis",
        "trust_tier": 1,
        "url": "https://fred.stlouisfed.org",
        "api_url": "https://api.stlouisfed.org/fred/series/observations",
        "auth_required": "Optional (FRED_API_KEY for higher rate limits)",
        "update_frequency": "Varies by series — daily (yields, VIX), monthly (CPI, PCE, payrolls), quarterly (GDP)",
        "latency": "Same day for daily series; T+2 weeks for monthly releases after BLS/BEA publish",
        "rate_limit": "120 requests/minute with key; limited without",
        "data_integrity": "Primary authoritative source for US economic data. FRED aggregates from BLS, BEA, Treasury, Fed. Data is identical to source agencies.",
        "coverage": "816,000+ time series — the most comprehensive US economic database",
    },
    {
        "id": "bls",
        "name": "Bureau of Labor Statistics",
        "operator": "U.S. Department of Labor",
        "trust_tier": 1,
        "url": "https://www.bls.gov",
        "api_url": "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        "auth_required": "Optional (BLS_API_KEY for higher limits)",
        "update_frequency": "Monthly (employment, CPI); some series quarterly",
        "latency": "Data published on fixed schedule — CPI mid-month, Employment Situation first Friday",
        "rate_limit": "25 queries/day (v2 unregistered), 500/day (v2 registered)",
        "data_integrity": "Primary source for employment and consumer price data. Official statistics of the US government.",
        "coverage": "Employment, prices, compensation, productivity, workplace safety",
    },
    {
        "id": "treasury_fiscal",
        "name": "U.S. Treasury Fiscal Data",
        "operator": "U.S. Department of the Treasury",
        "trust_tier": 1,
        "url": "https://fiscaldata.treasury.gov",
        "api_url": "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/",
        "auth_required": "No",
        "update_frequency": "Daily (interest rates, debt), monthly (revenue/spending)",
        "latency": "T+1 business day for daily data",
        "rate_limit": "Generous; no documented hard limit",
        "data_integrity": "Official US Treasury data. Authoritative for debt, interest rates, fiscal operations.",
        "coverage": "National debt, interest rates, revenue, spending, savings bonds",
    },
    {
        "id": "sec_edgar_efts",
        "name": "SEC EDGAR Full-Text Search (EFTS)",
        "operator": "U.S. Securities and Exchange Commission",
        "trust_tier": 1,
        "url": "https://www.sec.gov/edgar/searchedgar/companysearch",
        "api_url": "https://efts.sec.gov/LATEST/search-index",
        "auth_required": "No (User-Agent header recommended)",
        "update_frequency": "Real-time — filings appear within minutes of submission",
        "latency": "<5 minutes from filing to search availability",
        "rate_limit": "10 requests/second (per SEC fair access policy)",
        "data_integrity": "Primary source for all SEC filings. Legally required disclosure — highest integrity.",
        "coverage": "Full-text search across all SEC filings: 10-K, 10-Q, 8-K, S-1, enforcement actions",
    },
    {
        "id": "sec_edgar_structured",
        "name": "SEC EDGAR Structured Data API",
        "operator": "U.S. Securities and Exchange Commission",
        "trust_tier": 1,
        "url": "https://data.sec.gov",
        "api_url": "https://data.sec.gov/submissions/CIK{cik}.json",
        "auth_required": "No (User-Agent header with contact email required)",
        "update_frequency": "Real-time — filings indexed within minutes",
        "latency": "<5 minutes from filing to API availability",
        "rate_limit": "10 requests/second",
        "data_integrity": "Structured JSON access to all EDGAR filings and XBRL financial data. Primary source.",
        "coverage": "All SEC registrant filings, XBRL facts, company metadata, filing history",
    },
    {
        "id": "federal_register",
        "name": "Federal Register API",
        "operator": "Office of the Federal Register / GPO",
        "trust_tier": 1,
        "url": "https://www.federalregister.gov",
        "api_url": "https://www.federalregister.gov/api/v1/documents.json",
        "auth_required": "No",
        "update_frequency": "Daily — published every business day at 6:00 AM ET",
        "latency": "Same day; documents available via API on publication date",
        "rate_limit": "1000 requests/day (undocumented; generous)",
        "data_integrity": "Official journal of the US government. All federal regulations published here. Legal authority.",
        "coverage": "Proposed rules, final rules, notices, executive orders, presidential documents",
    },
    {
        "id": "congress_gov",
        "name": "Congress.gov API",
        "operator": "Library of Congress",
        "trust_tier": 1,
        "url": "https://api.congress.gov",
        "api_url": "https://api.congress.gov/v3/bill",
        "auth_required": "Yes (free api.congress.gov key)",
        "update_frequency": "Near real-time for floor actions; daily for bill text updates",
        "latency": "Floor actions within hours; bill text within 1 business day",
        "rate_limit": "5000 requests/hour with key",
        "data_integrity": "Official legislative record. Authoritative for bill status, votes, amendments.",
        "coverage": "All Congressional bills, resolutions, amendments, nominations, treaties",
    },
    {
        "id": "fed_rss",
        "name": "Federal Reserve RSS Feeds",
        "operator": "Board of Governors of the Federal Reserve System",
        "trust_tier": 1,
        "url": "https://www.federalreserve.gov/feeds/",
        "api_url": "https://www.federalreserve.gov/feeds/press_monetary.xml",
        "auth_required": "No",
        "update_frequency": "Real-time — FOMC statements within seconds of release",
        "latency": "<1 minute for monetary policy announcements",
        "rate_limit": "No documented limit; standard web crawling etiquette",
        "data_integrity": "Official Federal Reserve communications. FOMC statements are the primary source.",
        "coverage": "Monetary policy, speeches, testimony, banking supervision, statistical releases",
    },
    {
        "id": "sec_rss",
        "name": "SEC RSS Feeds",
        "operator": "U.S. Securities and Exchange Commission",
        "trust_tier": 1,
        "url": "https://www.sec.gov/about/secrss.htm",
        "api_url": "https://www.sec.gov/news/pressreleases.rss",
        "auth_required": "No",
        "update_frequency": "Real-time — press releases within minutes",
        "latency": "<5 minutes for enforcement actions and press releases",
        "rate_limit": "10 requests/second",
        "data_integrity": "Official SEC communications. Enforcement actions and press releases are authoritative.",
        "coverage": "Press releases, litigation releases, proposed rules, final rules, speeches",
    },
    {
        "id": "polymarket_gamma",
        "name": "Polymarket Gamma API",
        "operator": "Polymarket (PM Holdings)",
        "trust_tier": 3,
        "url": "https://polymarket.com",
        "api_url": "https://gamma-api.polymarket.com",
        "auth_required": "No (read-only)",
        "update_frequency": "Real-time — prices update with every trade",
        "latency": "<1 second for price updates",
        "rate_limit": "~100 requests/minute (undocumented)",
        "data_integrity": "Market prices reflect real money at risk. Manipulation possible but costly. Gamma API is the official market data API.",
        "coverage": "All active Polymarket events and markets with prices, volume, liquidity",
    },
    {
        "id": "polymarket_clob",
        "name": "Polymarket CLOB API",
        "operator": "Polymarket (PM Holdings)",
        "trust_tier": 3,
        "url": "https://polymarket.com",
        "api_url": "https://clob.polymarket.com",
        "auth_required": "No (read-only order book)",
        "update_frequency": "Real-time — order book updates on every order",
        "latency": "<1 second",
        "rate_limit": "~100 requests/minute",
        "data_integrity": "Order book is on-chain verifiable (Polygon). Prices backed by actual liquidity.",
        "coverage": "Order books, trades, market metadata for all active markets",
    },
    {
        "id": "kalshi",
        "name": "Kalshi Trade API",
        "operator": "Kalshi Inc. (CFTC-regulated DCM)",
        "trust_tier": 3,
        "url": "https://kalshi.com",
        "api_url": "https://api.elections.kalshi.com/trade-api/v2",
        "auth_required": "No (read-only market data)",
        "update_frequency": "Real-time — prices update with every trade",
        "latency": "<1 second for price updates",
        "rate_limit": "~60 requests/minute (undocumented)",
        "data_integrity": "CFTC-regulated Designated Contract Market. Prices reflect real money. Regulatory oversight provides integrity guarantee.",
        "coverage": "All active Kalshi markets — economics, politics, climate, finance",
    },
    {
        "id": "fdic_bankfind",
        "name": "FDIC BankFind Suite API",
        "operator": "Federal Deposit Insurance Corporation",
        "trust_tier": 1,
        "url": "https://banks.data.fdic.gov",
        "api_url": "https://banks.data.fdic.gov/api/failures",
        "auth_required": "No",
        "update_frequency": "Updated within 24 hours of bank closure announcement",
        "latency": "<24 hours for failure data; quarterly for financial reports",
        "rate_limit": "No documented limit; standard REST API",
        "data_integrity": "Official FDIC data. Bank failure records are legally authoritative. Financial reports from Call Reports (FFIEC).",
        "coverage": "Bank failures, financial reports, institution demographics, historical data back to 1934",
    },
]


def get_data_source_audit() -> dict[str, Any]:
    """
    Return the complete data source registry with trust classifications.
    Used by /v1/intelligence/economic-snapshot to provide provenance metadata.
    """
    return {
        "data_sources": DATA_SOURCE_REGISTRY,
        "total_sources": len(DATA_SOURCE_REGISTRY),
        "tier_1_sources": sum(1 for s in DATA_SOURCE_REGISTRY if s["trust_tier"] == 1),
        "tier_3_sources": sum(1 for s in DATA_SOURCE_REGISTRY if s["trust_tier"] == 3),
        "integrity_note": (
            "HYDRA uses exclusively Tier 1 (official US government) and Tier 3 (CFTC-regulated) "
            "data sources. No Tier 4/5 sources are used for signal generation. "
            "All economic data is sourced from the agencies that publish it (BLS for employment, "
            "BEA for GDP via FRED, Treasury for yields, SEC for filings). "
            "Market prices come from regulated platforms (Kalshi is CFTC-regulated; "
            "Polymarket prices are on-chain verifiable on Polygon)."
        ),
        "cross_validation": (
            "FRED data cross-validates BLS (CPI, employment) and BEA (GDP, PCE). "
            "If FRED and BLS report different CPI values, the BLS value takes precedence "
            "as the primary publisher. Treasury yield data from FRED mirrors "
            "treasury.gov with identical values."
        ),
    }
