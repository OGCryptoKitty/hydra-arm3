"""
HYDRA — Extraction endpoints.

General-purpose web extraction for agents and developers.
Pay-per-call via x402 on Base L2.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup
from cachetools import TTLCache
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.utils.url_validation import is_safe_url

extract_router = APIRouter(tags=["Extraction"])

_http_client: httpx.AsyncClient | None = None
_search_cache: TTLCache = TTLCache(maxsize=200, ttl=300)


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            headers={"User-Agent": "HYDRA-Extract/1.0 (x402; +https://hydra-api-nlnj.onrender.com)"},
        )
    return _http_client


def _extract_page(html: str, url: str, max_length: int = 12000) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "svg"]):
        tag.decompose()

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag["content"] if desc_tag and desc_tag.get("content") else None

    og = {}
    for prop in ["og:title", "og:description", "og:image", "og:type", "og:site_name"]:
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"):
            og[prop.split(":")[1]] = tag["content"]

    headings = []
    for h in soup.find_all(["h1", "h2", "h3"], limit=20):
        text = h.get_text(strip=True)
        if text:
            headings.append({"level": int(h.name[1]), "text": text[:200]})

    links = []
    for a in soup.find_all("a", href=True, limit=30):
        href = a["href"]
        if href.startswith(("http://", "https://")):
            link_text = a.get_text(strip=True)[:100]
            if link_text:
                links.append({"text": link_text, "href": href})

    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)
    truncated = len(clean_text) > max_length
    if truncated:
        clean_text = clean_text[:max_length]

    return {
        "url": url,
        "title": title,
        "description": description,
        "og": og or None,
        "headings": headings,
        "text": clean_text,
        "text_length": len(clean_text),
        "truncated": truncated,
        "links": links,
    }


class ExtractURLRequest(BaseModel):
    url: str = Field(..., description="URL to extract content from")
    max_length: int = Field(default=12000, ge=100, le=50000)
    include_links: bool = Field(default=True)


@extract_router.post("/v1/extract/url", tags=["Extraction"])
async def extract_url(req: ExtractURLRequest):
    """
    Extract structured content from a URL. Returns title, headings,
    clean text, links, and OpenGraph metadata. $0.01 USDC.
    """
    start = time.monotonic()

    if not is_safe_url(req.url):
        return JSONResponse(status_code=422, content={
            "error": "Invalid URL",
            "detail": "URL must use http(s) and target a public host.",
        })

    client = await _get_client()

    try:
        resp = await client.get(req.url)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return JSONResponse(status_code=502, content={
            "error": "Upstream HTTP error",
            "status_code": e.response.status_code,
            "url": req.url,
        })
    except httpx.RequestError as e:
        return JSONResponse(status_code=502, content={
            "error": "Request failed",
            "detail": str(type(e).__name__),
            "url": req.url,
        })

    result = _extract_page(resp.text, req.url, req.max_length)
    if not req.include_links:
        result.pop("links", None)
    result["elapsed_ms"] = round((time.monotonic() - start) * 1000)
    return result


class ExtractMultiRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=5, description="URLs to extract (max 5)")
    max_length: int = Field(default=8000, ge=100, le=30000)


@extract_router.post("/v1/extract/multi", tags=["Extraction"])
async def extract_multi(req: ExtractMultiRequest):
    """
    Extract structured content from up to 5 URLs in parallel.
    Returns results for each URL. $0.05 USDC.
    """
    start = time.monotonic()
    client = await _get_client()

    async def fetch_one(url: str) -> dict[str, Any]:
        if not is_safe_url(url):
            return {"url": url, "error": "invalid_url", "detail": "Must use http(s) and target a public host."}
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return _extract_page(resp.text, url, req.max_length)
        except httpx.HTTPStatusError as e:
            return {"url": url, "error": "upstream_http_error", "status_code": e.response.status_code}
        except httpx.RequestError as e:
            return {"url": url, "error": "request_failed", "detail": str(type(e).__name__)}

    results = await asyncio.gather(*[fetch_one(u) for u in req.urls])
    return {
        "results": list(results),
        "urls_requested": len(req.urls),
        "urls_succeeded": sum(1 for r in results if "error" not in r),
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }


@extract_router.get("/v1/extract/search", tags=["Extraction"])
async def extract_search(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    max_results: int = Query(default=8, ge=1, le=20),
):
    """
    Web search with structured result extraction. Returns titles,
    snippets, and URLs from DuckDuckGo. $0.02 USDC.
    """
    start = time.monotonic()

    cache_key = hashlib.md5(f"{q}:{max_results}".encode()).hexdigest()
    cached = _search_cache.get(cache_key)
    if cached is not None:
        cached["cached"] = True
        cached["elapsed_ms"] = 0
        return cached

    client = await _get_client()

    try:
        resp = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": q},
            headers={"User-Agent": "HYDRA-Search/1.0"},
        )
        resp.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError):
        return JSONResponse(status_code=502, content={
            "error": "Search upstream unavailable",
            "detail": "Could not reach search provider. Try again.",
        })

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for item in soup.select(".result"):
        title_el = item.select_one(".result__title a, .result__a")
        snippet_el = item.select_one(".result__snippet")
        url_el = item.select_one(".result__url")

        if not title_el:
            continue

        href = title_el.get("href", "")
        if href.startswith("//duckduckgo.com/l/"):
            import urllib.parse
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            href = parsed.get("uddg", [href])[0]

        results.append({
            "title": title_el.get_text(strip=True),
            "snippet": snippet_el.get_text(strip=True) if snippet_el else None,
            "url": href,
            "display_url": url_el.get_text(strip=True) if url_el else None,
        })

        if len(results) >= max_results:
            break

    output = {
        "query": q,
        "results": results,
        "result_count": len(results),
        "source": "duckduckgo",
        "cached": False,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }
    _search_cache[cache_key] = output
    return output
