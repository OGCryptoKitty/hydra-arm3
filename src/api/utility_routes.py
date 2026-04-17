"""
HYDRA Arm 3 — High-Volume Utility Endpoints

Low-price ($0.001–$0.005) general-purpose data services designed to capture
high-volume x402 agent traffic. These leverage HYDRA's existing dependencies
(httpx, beautifulsoup4, feedparser, web3) — no additional installs required.

Pricing rationale: x402 ecosystem average is $0.001–$0.01 per call.
High-volume utility endpoints generate more revenue than niche high-price
endpoints because AI agent demand is concentrated on general-purpose tools.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from cachetools import TTLCache
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config.settings import WALLET_ADDRESS, BASE_RPC_URL

logger = logging.getLogger(__name__)

utility_router = APIRouter(tags=["Utility Data Services"])

_http_client: httpx.AsyncClient | None = None

_price_cache: TTLCache = TTLCache(maxsize=200, ttl=30)
_gas_cache: TTLCache = TTLCache(maxsize=1, ttl=12)


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            headers={"User-Agent": "HYDRA-Utility/1.0 (x402)"},
        )
    return _http_client


# ─────────────────────────────────────────────────────────────
# Free discovery endpoint
# ─────────────────────────────────────────────────────────────

@utility_router.get("/v1/util", tags=["Utility Data Services"])
async def utility_index():
    """List available utility endpoints and pricing. Free — no payment required."""
    return {
        "service": "HYDRA Utility Data Services",
        "description": "High-volume, low-cost data endpoints for AI agents. Pay per call via x402.",
        "endpoints": [
            {
                "path": "/v1/util/scrape",
                "method": "POST",
                "price_usdc": "0.005",
                "description": "URL → clean structured text. HTML parsed, scripts/styles removed.",
            },
            {
                "path": "/v1/util/crypto/price",
                "method": "GET",
                "price_usdc": "0.001",
                "description": "Token price in USD. Supports any CoinGecko-listed token. Cached 30s.",
            },
            {
                "path": "/v1/util/rss",
                "method": "POST",
                "price_usdc": "0.002",
                "description": "RSS/Atom feed → structured JSON with parsed entries.",
            },
            {
                "path": "/v1/util/crypto/balance",
                "method": "GET",
                "price_usdc": "0.001",
                "description": "Wallet ETH + USDC balance on Base L2.",
            },
            {
                "path": "/v1/util/gas",
                "method": "GET",
                "price_usdc": "0.001",
                "description": "Base L2 gas prices + estimated costs for transfers, swaps, mints. Cached per block.",
            },
            {
                "path": "/v1/util/tx",
                "method": "GET",
                "price_usdc": "0.001",
                "description": "Transaction receipt lookup — status, gas used, block number.",
            },
            {
                "path": "/v1/batch",
                "method": "POST",
                "price_usdc": "0.01",
                "description": "Batch up to 5 utility calls in one request. Saves gas vs individual payments.",
            },
        ],
        "payment_protocol": "x402",
        "payment_network": "Base (chain 8453)",
        "payment_token": "USDC",
        "wallet": WALLET_ADDRESS,
    }


# ─────────────────────────────────────────────────────────────
# 1. Web Scrape — $0.005/call
# ─────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url: str = Field(..., description="URL to scrape")
    max_length: int = Field(default=8000, ge=100, le=50000, description="Max text length to return")
    include_links: bool = Field(default=False, description="Include extracted links")
    include_metadata: bool = Field(default=True, description="Include page title, description, etc.")


@utility_router.post("/v1/util/scrape", tags=["Utility Data Services"])
async def scrape_url(req: ScrapeRequest):
    """
    Fetch a URL and return clean structured text.
    HTML is parsed, scripts/styles/nav removed. $0.005 USDC per call.
    """
    start = time.monotonic()
    client = await _get_client()

    try:
        resp = await client.get(req.url)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return JSONResponse(status_code=422, content={
            "error": "Upstream HTTP error",
            "status_code": e.response.status_code,
            "url": req.url,
        })
    except httpx.RequestError as e:
        return JSONResponse(status_code=422, content={
            "error": "Request failed",
            "detail": str(type(e).__name__),
            "url": req.url,
        })

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        return JSONResponse(content={
            "url": req.url,
            "content_type": content_type,
            "text": resp.text[:req.max_length],
            "length": len(resp.text),
            "truncated": len(resp.text) > req.max_length,
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        })

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
        tag.decompose()

    metadata = {}
    if req.include_metadata:
        title_tag = soup.find("title")
        metadata["title"] = title_tag.get_text(strip=True) if title_tag else None
        desc_tag = soup.find("meta", attrs={"name": "description"})
        metadata["description"] = desc_tag["content"] if desc_tag and desc_tag.get("content") else None
        og_title = soup.find("meta", attrs={"property": "og:title"})
        metadata["og_title"] = og_title["content"] if og_title and og_title.get("content") else None

    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    if len(clean_text) > req.max_length:
        clean_text = clean_text[:req.max_length]
        truncated = True
    else:
        truncated = False

    result: dict = {
        "url": req.url,
        "text": clean_text,
        "length": len(clean_text),
        "truncated": truncated,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }

    if req.include_metadata:
        result["metadata"] = metadata

    if req.include_links:
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("http://", "https://")):
                links.append({"text": a.get_text(strip=True)[:100], "href": href})
        result["links"] = links[:50]

    return result


# ─────────────────────────────────────────────────────────────
# 2. Crypto Price — $0.001/call
# ─────────────────────────────────────────────────────────────

@utility_router.get("/v1/util/crypto/price", tags=["Utility Data Services"])
async def crypto_price(
    token: str = Query(default="ethereum", description="CoinGecko token ID (e.g., ethereum, bitcoin, usd-coin)"),
    vs_currency: str = Query(default="usd", description="Target currency (e.g., usd, eur, btc)"),
):
    """
    Get current token price from CoinGecko. $0.001 USDC per call.
    Supports any CoinGecko-listed token by ID.
    """
    client = await _get_client()
    start = time.monotonic()

    cache_key = f"{token.lower().strip()}:{vs_currency.lower().strip()}"
    cached = _price_cache.get(cache_key)
    if cached is not None:
        cached["elapsed_ms"] = 0
        cached["cached"] = True
        return cached

    try:
        resp = await client.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": token.lower().strip(),
                "vs_currencies": vs_currency.lower().strip(),
                "include_24hr_change": "true",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError:
        return JSONResponse(status_code=502, content={
            "error": "Upstream API error",
            "detail": "CoinGecko API returned an error. Try again shortly.",
        })
    except httpx.RequestError:
        return JSONResponse(status_code=502, content={
            "error": "Upstream connection failed",
            "detail": "Could not reach CoinGecko API.",
        })

    token_data = data.get(token.lower().strip())
    if not token_data:
        return JSONResponse(status_code=404, content={
            "error": "Token not found",
            "detail": f"'{token}' is not a valid CoinGecko token ID.",
            "hint": "Use the CoinGecko ID format (e.g., 'bitcoin', 'ethereum', 'usd-coin', 'solana').",
        })

    vs = vs_currency.lower().strip()
    result = {
        "token": token.lower().strip(),
        "currency": vs,
        "price": token_data.get(vs),
        "change_24h_pct": token_data.get(f"{vs}_24h_change"),
        "market_cap": token_data.get(f"{vs}_market_cap"),
        "volume_24h": token_data.get(f"{vs}_24h_vol"),
        "source": "coingecko",
        "elapsed_ms": round((time.monotonic() - start) * 1000),
        "cached": False,
    }
    _price_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# 3. RSS Feed Parser — $0.002/call
# ─────────────────────────────────────────────────────────────

class RssRequest(BaseModel):
    url: str = Field(..., description="RSS or Atom feed URL")
    max_entries: int = Field(default=20, ge=1, le=100, description="Max entries to return")
    include_content: bool = Field(default=False, description="Include full entry content (increases response size)")


@utility_router.post("/v1/util/rss", tags=["Utility Data Services"])
async def parse_rss(req: RssRequest):
    """
    Parse an RSS or Atom feed into structured JSON. $0.002 USDC per call.
    Returns feed metadata and parsed entries.
    """
    import feedparser

    client = await _get_client()
    start = time.monotonic()

    try:
        resp = await client.get(req.url)
        resp.raise_for_status()
        raw = resp.text
    except httpx.HTTPStatusError as e:
        return JSONResponse(status_code=422, content={
            "error": "Feed fetch failed",
            "status_code": e.response.status_code,
            "url": req.url,
        })
    except httpx.RequestError:
        return JSONResponse(status_code=422, content={
            "error": "Feed unreachable",
            "url": req.url,
        })

    feed = feedparser.parse(raw)

    if feed.bozo and not feed.entries:
        return JSONResponse(status_code=422, content={
            "error": "Invalid feed",
            "detail": "URL did not return a valid RSS or Atom feed.",
            "url": req.url,
        })

    entries = []
    for entry in feed.entries[:req.max_entries]:
        item: dict = {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", entry.get("updated", "")),
            "author": entry.get("author", ""),
        }
        summary = entry.get("summary", "")
        if summary:
            soup = BeautifulSoup(summary, "html.parser")
            item["summary"] = soup.get_text(strip=True)[:500]

        if req.include_content:
            content = ""
            if entry.get("content"):
                content = entry.content[0].get("value", "")
            elif entry.get("description"):
                content = entry.description
            if content:
                soup = BeautifulSoup(content, "html.parser")
                item["content"] = soup.get_text(strip=True)[:2000]

        entries.append(item)

    return {
        "feed": {
            "title": feed.feed.get("title", ""),
            "link": feed.feed.get("link", ""),
            "description": feed.feed.get("description", "")[:300] if feed.feed.get("description") else None,
            "updated": feed.feed.get("updated", ""),
        },
        "entry_count": len(entries),
        "total_entries": len(feed.entries),
        "entries": entries,
        "url": req.url,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }


# ─────────────────────────────────────────────────────────────
# 4. Crypto Wallet Balance — $0.001/call
# ─────────────────────────────────────────────────────────────

@utility_router.get("/v1/util/crypto/balance", tags=["Utility Data Services"])
async def crypto_balance(
    address: str = Query(..., description="Wallet address (0x-prefixed, checksummed or lowercase)"),
    include_usdc: bool = Query(default=True, description="Also check USDC balance"),
):
    """
    Check wallet ETH and USDC balance on Base L2. $0.001 USDC per call.
    """
    from web3 import Web3

    start = time.monotonic()

    if not address.startswith("0x") or len(address) != 42:
        return JSONResponse(status_code=422, content={
            "error": "Invalid address",
            "detail": "Address must be a 0x-prefixed 42-character hex string.",
        })

    try:
        w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
        checksummed = Web3.to_checksum_address(address)
    except Exception:
        return JSONResponse(status_code=422, content={
            "error": "Invalid address format",
            "detail": "Could not parse the provided address.",
        })

    result: dict = {
        "address": checksummed,
        "network": "base",
        "chain_id": 8453,
    }

    try:
        eth_balance_wei = w3.eth.get_balance(checksummed)
        result["eth_balance"] = str(Web3.from_wei(eth_balance_wei, "ether"))
        result["eth_balance_wei"] = str(eth_balance_wei)
    except Exception as e:
        result["eth_balance"] = None
        result["eth_error"] = str(e)[:100]

    if include_usdc:
        usdc_contract = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
        erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
            }
        ]
        try:
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(usdc_contract),
                abi=erc20_abi,
            )
            usdc_raw = contract.functions.balanceOf(checksummed).call()
            result["usdc_balance"] = str(usdc_raw / 10**6)
            result["usdc_balance_raw"] = str(usdc_raw)
        except Exception as e:
            result["usdc_balance"] = None
            result["usdc_error"] = str(e)[:100]

    result["elapsed_ms"] = round((time.monotonic() - start) * 1000)
    return result


# ─────────────────────────────────────────────────────────────
# 5. Gas Prices — $0.001/call
# ─────────────────────────────────────────────────────────────

@utility_router.get("/v1/util/gas", tags=["Utility Data Services"])
async def gas_prices():
    """
    Current gas prices on Base L2 with estimated costs for common operations.
    $0.001 USDC per call. Cached per block (~12s).
    """
    from web3 import Web3

    cached = _gas_cache.get("gas")
    if cached is not None:
        cached["cached"] = True
        return cached

    start = time.monotonic()

    try:
        w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
        block = w3.eth.get_block("latest")
        gas_price_wei = w3.eth.gas_price
        base_fee = block.get("baseFeePerGas", 0)
        gas_price_gwei = float(Web3.from_wei(gas_price_wei, "gwei"))
        base_fee_gwei = float(Web3.from_wei(base_fee, "gwei"))
        eth_price = None
        try:
            client = await _get_client()
            resp = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "ethereum", "vs_currencies": "usd"},
            )
            if resp.status_code == 200:
                eth_price = resp.json().get("ethereum", {}).get("usd")
        except Exception:
            pass

        estimates = {}
        gas_units = {"eth_transfer": 21_000, "erc20_transfer": 65_000, "swap": 150_000, "nft_mint": 100_000}
        for op, gas in gas_units.items():
            cost_eth = float(Web3.from_wei(gas_price_wei * gas, "ether"))
            estimates[op] = {
                "gas_units": gas,
                "cost_eth": f"{cost_eth:.8f}",
                "cost_usd": f"${cost_eth * eth_price:.4f}" if eth_price else None,
            }

        result = {
            "network": "base",
            "chain_id": 8453,
            "block_number": block["number"],
            "gas_price_gwei": round(gas_price_gwei, 6),
            "base_fee_gwei": round(base_fee_gwei, 6),
            "eth_price_usd": eth_price,
            "estimates": estimates,
            "elapsed_ms": round((time.monotonic() - start) * 1000),
            "cached": False,
        }
        _gas_cache["gas"] = result
        return result
    except Exception as exc:
        return JSONResponse(status_code=502, content={
            "error": "RPC error",
            "detail": str(exc)[:200],
        })


# ─────────────────────────────────────────────────────────────
# 6. Transaction Status — $0.001/call
# ─────────────────────────────────────────────────────────────

@utility_router.get("/v1/util/tx", tags=["Utility Data Services"])
async def tx_status(
    tx_hash: str = Query(..., description="Transaction hash (0x-prefixed)"),
):
    """
    Look up a transaction receipt on Base L2. $0.001 USDC per call.
    Returns confirmation status, gas used, block number, and log count.
    """
    from web3 import Web3

    start = time.monotonic()

    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        return JSONResponse(status_code=422, content={
            "error": "Invalid transaction hash",
            "detail": "Must be a 0x-prefixed 64-character hex string.",
        })

    try:
        w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception:
        return JSONResponse(content={
            "tx_hash": tx_hash,
            "status": "not_found",
            "detail": "Transaction not found or not yet confirmed.",
            "network": "base",
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        })

    return {
        "tx_hash": tx_hash,
        "status": "success" if receipt.get("status") == 1 else "reverted",
        "block_number": receipt.get("blockNumber"),
        "gas_used": receipt.get("gasUsed"),
        "effective_gas_price": str(receipt.get("effectiveGasPrice", 0)),
        "from": receipt.get("from"),
        "to": receipt.get("to"),
        "contract_address": receipt.get("contractAddress"),
        "log_count": len(receipt.get("logs", [])),
        "network": "base",
        "chain_id": 8453,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }


# ─────────────────────────────────────────────────────────────
# 7. Batch Utility Calls — $0.01/call
# ─────────────────────────────────────────────────────────────

class BatchItem(BaseModel):
    endpoint: str = Field(..., description="Utility endpoint path (e.g., /v1/util/crypto/price)")
    params: dict = Field(default_factory=dict, description="Query parameters or request body fields")


class BatchRequest(BaseModel):
    requests: list[BatchItem] = Field(..., min_length=1, max_length=5, description="Up to 5 utility calls per batch")


_BATCHABLE = {
    "/v1/util/crypto/price",
    "/v1/util/crypto/balance",
    "/v1/util/gas",
    "/v1/util/tx",
}


@utility_router.post("/v1/batch", tags=["Utility Data Services"])
async def batch_utility(req: BatchRequest):
    """
    Execute up to 5 utility calls in a single request. $0.01 USDC.
    Saves gas costs vs individual x402 payments (one on-chain tx instead of five).
    Supports: /v1/util/crypto/price, /v1/util/crypto/balance, /v1/util/gas, /v1/util/tx.
    """
    start = time.monotonic()
    results = []

    for item in req.requests:
        if item.endpoint not in _BATCHABLE:
            results.append({"endpoint": item.endpoint, "error": f"Not batchable. Supported: {sorted(_BATCHABLE)}"})
            continue

        try:
            if item.endpoint == "/v1/util/crypto/price":
                data = await crypto_price(
                    token=item.params.get("token", "ethereum"),
                    vs_currency=item.params.get("vs_currency", "usd"),
                )
            elif item.endpoint == "/v1/util/crypto/balance":
                addr = item.params.get("address", "")
                data = await crypto_balance(
                    address=addr,
                    include_usdc=item.params.get("include_usdc", True),
                )
            elif item.endpoint == "/v1/util/gas":
                data = await gas_prices()
            elif item.endpoint == "/v1/util/tx":
                data = await tx_status(tx_hash=item.params.get("tx_hash", ""))
            else:
                data = {"error": "Unknown endpoint"}

            if hasattr(data, "body"):
                import json as _json
                data = _json.loads(data.body)
            results.append({"endpoint": item.endpoint, "data": data})
        except Exception as exc:
            results.append({"endpoint": item.endpoint, "error": str(exc)[:200]})

    return {
        "batch_size": len(results),
        "results": results,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }
