"""
HYDRA — Public data search endpoints.

Wikipedia, arXiv, SEC EDGAR. Free public APIs, no keys required.
Pay-per-call via x402 on Base L2.
"""

from __future__ import annotations

import time
from urllib.parse import quote

import feedparser
import httpx
from cachetools import TTLCache
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

data_router = APIRouter(tags=["Public Data"])

_http_client: httpx.AsyncClient | None = None
_wiki_cache: TTLCache = TTLCache(maxsize=200, ttl=600)
_edgar_cache: TTLCache = TTLCache(maxsize=100, ttl=300)


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            headers={"User-Agent": "HYDRA-Data/1.0 (x402; +https://hydra-api-nlnj.onrender.com)"},
        )
    return _http_client


@data_router.get("/v1/data/wikipedia", tags=["Public Data"])
async def data_wikipedia(
    q: str = Query(..., min_length=1, max_length=300, description="Article title or search term"),
    lang: str = Query(default="en", max_length=5, description="Language code"),
):
    """
    Wikipedia article summary. Returns extract, thumbnail, description,
    and page URL. Cached 10 minutes. $0.01 USDC.
    """
    start = time.monotonic()

    cache_key = f"{lang}:{q.lower()}"
    cached = _wiki_cache.get(cache_key)
    if cached:
        cached["cached"] = True
        cached["elapsed_ms"] = 0
        return cached

    client = await _get_client()
    title = quote(q.replace(" ", "_"))

    try:
        resp = await client.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}")
    except httpx.RequestError:
        return JSONResponse(status_code=502, content={"error": "Wikipedia API unavailable"})

    if resp.status_code == 404:
        try:
            search_resp = await client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={"action": "opensearch", "search": q, "limit": 5, "format": "json"},
            )
            suggestions = search_resp.json()[1] if search_resp.status_code == 200 else []
        except (httpx.RequestError, IndexError, KeyError):
            suggestions = []

        return {
            "found": False,
            "query": q,
            "suggestions": suggestions,
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        }

    data = resp.json()
    result = {
        "found": True,
        "title": data.get("title"),
        "description": data.get("description"),
        "extract": data.get("extract"),
        "extract_html": data.get("extract_html"),
        "thumbnail": data.get("thumbnail", {}).get("source") if data.get("thumbnail") else None,
        "page_url": data.get("content_urls", {}).get("desktop", {}).get("page"),
        "language": lang,
        "cached": False,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }

    _wiki_cache[cache_key] = result
    return result


@data_router.get("/v1/data/arxiv", tags=["Public Data"])
async def data_arxiv(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    max_results: int = Query(default=10, ge=1, le=50),
    sort_by: str = Query(default="relevance", description="Sort: relevance, lastUpdatedDate, submittedDate"),
):
    """
    Search arXiv for academic papers. Returns titles, authors, abstracts,
    categories, and PDF links. $0.02 USDC.
    """
    start = time.monotonic()
    client = await _get_client()

    sort_map = {
        "relevance": "relevance",
        "lastupdateddate": "lastUpdatedDate",
        "submitteddate": "submittedDate",
    }
    sort_param = sort_map.get(sort_by.lower(), "relevance")

    try:
        resp = await client.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{q}",
                "start": 0,
                "max_results": max_results,
                "sortBy": sort_param,
                "sortOrder": "descending",
            },
        )
        resp.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError):
        return JSONResponse(status_code=502, content={"error": "arXiv API unavailable"})

    feed = feedparser.parse(resp.text)
    papers = []

    for entry in feed.entries:
        authors = [a.get("name", "") for a in entry.get("authors", [])]
        categories = [t.get("term", "") for t in entry.get("tags", [])]

        pdf_link = None
        for link in entry.get("links", []):
            if link.get("type") == "application/pdf" or link.get("title") == "pdf":
                pdf_link = link.get("href")
                break

        papers.append({
            "id": entry.get("id", ""),
            "title": entry.get("title", "").replace("\n", " ").strip(),
            "authors": authors,
            "abstract": entry.get("summary", "").replace("\n", " ").strip()[:1000],
            "categories": categories,
            "published": entry.get("published", ""),
            "updated": entry.get("updated", ""),
            "pdf_url": pdf_link,
            "arxiv_url": entry.get("id", ""),
        })

    return {
        "query": q,
        "results": papers,
        "result_count": len(papers),
        "total_results": int(feed.feed.get("opensearch_totalresults", 0)),
        "source": "arxiv",
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }


@data_router.get("/v1/data/edgar", tags=["Public Data"])
async def data_edgar(
    q: str = Query(..., min_length=1, max_length=300, description="Search query (company name, ticker, keyword)"),
    forms: str = Query(default="10-K,10-Q,8-K", description="Comma-separated form types"),
    max_results: int = Query(default=10, ge=1, le=40),
):
    """
    Search SEC EDGAR for company filings. Returns filing type, company,
    date, and document URLs. $0.02 USDC.
    """
    start = time.monotonic()

    cache_key = f"{q}:{forms}:{max_results}"
    cached = _edgar_cache.get(cache_key)
    if cached:
        cached["cached"] = True
        cached["elapsed_ms"] = 0
        return cached

    client = await _get_client()

    try:
        resp = await client.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={
                "q": q,
                "forms": forms,
                "from": "0",
                "size": str(max_results),
            },
            headers={
                "User-Agent": "HYDRA x402-agent support@hydra-api.com",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.RequestError, httpx.HTTPStatusError):
        try:
            resp = await client.get(
                "https://www.sec.gov/cgi-bin/browse-edgar",
                params={
                    "company": q,
                    "CIK": "",
                    "type": forms.split(",")[0] if forms else "10-K",
                    "dateb": "",
                    "owner": "include",
                    "count": str(max_results),
                    "search_text": "",
                    "action": "getcompany",
                    "output": "atom",
                },
                headers={"User-Agent": "HYDRA x402-agent support@hydra-api.com"},
            )
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            filings = []
            for entry in feed.entries:
                filings.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:500],
                    "filed": entry.get("updated", ""),
                    "url": entry.get("link", ""),
                })

            result = {
                "query": q,
                "results": filings,
                "result_count": len(filings),
                "source": "edgar_atom",
                "cached": False,
                "elapsed_ms": round((time.monotonic() - start) * 1000),
            }
            _edgar_cache[cache_key] = result
            return result
        except (httpx.RequestError, httpx.HTTPStatusError):
            return JSONResponse(status_code=502, content={"error": "SEC EDGAR unavailable"})

    hits = data.get("hits", {}).get("hits", [])
    filings = []
    for hit in hits:
        source = hit.get("_source", {})
        filings.append({
            "filing_type": source.get("forms", source.get("form_type", "")),
            "entity": source.get("entity_name", source.get("display_names", [""])[0] if source.get("display_names") else ""),
            "filed": source.get("file_date", source.get("period_of_report", "")),
            "description": source.get("display_description", "")[:500],
            "url": f"https://www.sec.gov/Archives/edgar/data/{source.get('entity_id', '')}/{source.get('file_num', '')}",
            "cik": source.get("entity_id", ""),
        })

    result = {
        "query": q,
        "forms_filter": forms,
        "results": filings,
        "result_count": len(filings),
        "total_results": data.get("hits", {}).get("total", {}).get("value", len(filings)),
        "source": "edgar_efts",
        "cached": False,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }
    _edgar_cache[cache_key] = result
    return result
