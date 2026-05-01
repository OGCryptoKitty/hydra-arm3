"""
HYDRA Live Market Data Engine
==============================
Perpetually live, free, no-API-key data connectors for:
  - CoinGecko: crypto prices, market caps, trending coins
  - DeFi Llama: TVL, protocol yields, stablecoin supply/peg
  - Alternative.me: Crypto Fear & Greed Index
  - ECB: EUR/USD and major forex rates
  - Base/Ethereum RPCs: gas prices, block data

All endpoints require NO API keys and are perpetually available.
Cache TTLs are tuned per data freshness requirements.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

_price_cache: TTLCache = TTLCache(maxsize=100, ttl=60)
_market_cache: TTLCache = TTLCache(maxsize=30, ttl=120)
_defi_cache: TTLCache = TTLCache(maxsize=30, ttl=120)
_sentiment_cache: TTLCache = TTLCache(maxsize=5, ttl=300)
_gas_cache: TTLCache = TTLCache(maxsize=10, ttl=15)
_stablecoin_cache: TTLCache = TTLCache(maxsize=10, ttl=120)

_HTTP_TIMEOUT = httpx.Timeout(12.0, connect=5.0)
_HEADERS = {
    "User-Agent": "HYDRA-MarketIntelligence/3.0 (hydra-api-nlnj.onrender.com)",
    "Accept": "application/json",
}


async def _async_get(url: str, params: dict | None = None) -> dict | list | None:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HEADERS) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.debug("Request failed %s: %s", url, exc)
            return None


# ─────────────────────────────────────────────────────────────
# CoinGecko — Free crypto market data (no key, 10-30 req/min)
# ─────────────────────────────────────────────────────────────

async def get_crypto_prices(ids: list[str], vs_currency: str = "usd") -> dict[str, Any]:
    cache_key = f"prices_{'_'.join(sorted(ids))}_{vs_currency}"
    if cache_key in _price_cache:
        return _price_cache[cache_key]

    data = await _async_get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": ",".join(ids),
            "vs_currencies": vs_currency,
            "include_24hr_change": "true",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_last_updated_at": "true",
        },
    )

    result: dict[str, Any] = {
        "prices": {},
        "vs_currency": vs_currency,
        "source": "CoinGecko (free, no API key)",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        for coin_id, info in data.items():
            if isinstance(info, dict):
                result["prices"][coin_id] = {
                    "price": info.get(vs_currency),
                    "market_cap": info.get(f"{vs_currency}_market_cap"),
                    "volume_24h": info.get(f"{vs_currency}_24h_vol"),
                    "change_24h_pct": info.get(f"{vs_currency}_24h_change"),
                    "last_updated": info.get("last_updated_at"),
                }

    _price_cache[cache_key] = result
    return result


async def get_crypto_global() -> dict[str, Any]:
    cache_key = "crypto_global"
    if cache_key in _market_cache:
        return _market_cache[cache_key]

    data = await _async_get("https://api.coingecko.com/api/v3/global")

    result: dict[str, Any] = {
        "global_market": {},
        "source": "CoinGecko Global Market Data",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        d = data.get("data", {})
        result["global_market"] = {
            "total_market_cap_usd": d.get("total_market_cap", {}).get("usd"),
            "total_volume_24h_usd": d.get("total_volume", {}).get("usd"),
            "btc_dominance": d.get("market_cap_percentage", {}).get("btc"),
            "eth_dominance": d.get("market_cap_percentage", {}).get("eth"),
            "active_cryptocurrencies": d.get("active_cryptocurrencies"),
            "markets": d.get("markets"),
            "market_cap_change_24h_pct": d.get("market_cap_change_percentage_24h_usd"),
        }

    _market_cache[cache_key] = result
    return result


async def get_trending_coins() -> dict[str, Any]:
    cache_key = "trending"
    if cache_key in _market_cache:
        return _market_cache[cache_key]

    data = await _async_get("https://api.coingecko.com/api/v3/search/trending")

    result: dict[str, Any] = {
        "trending_coins": [],
        "source": "CoinGecko Trending",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        for item in (data.get("coins") or [])[:15]:
            coin = item.get("item", {})
            result["trending_coins"].append({
                "id": coin.get("id"),
                "symbol": coin.get("symbol"),
                "name": coin.get("name"),
                "market_cap_rank": coin.get("market_cap_rank"),
                "price_btc": coin.get("price_btc"),
                "score": coin.get("score"),
            })

    _market_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# DeFi Llama — Free DeFi data (no key, generous limits)
# ─────────────────────────────────────────────────────────────

async def get_defi_tvl() -> dict[str, Any]:
    cache_key = "defi_tvl"
    if cache_key in _defi_cache:
        return _defi_cache[cache_key]

    data = await _async_get("https://api.llama.fi/v2/protocols")

    result: dict[str, Any] = {
        "top_protocols": [],
        "total_protocols": 0,
        "source": "DeFi Llama (free, no API key)",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, list):
        result["total_protocols"] = len(data)
        sorted_protocols = sorted(data, key=lambda x: x.get("tvl") or 0, reverse=True)
        for p in sorted_protocols[:25]:
            result["top_protocols"].append({
                "name": p.get("name"),
                "symbol": p.get("symbol"),
                "tvl": p.get("tvl"),
                "chain": p.get("chain"),
                "chains": p.get("chains", [])[:5],
                "category": p.get("category"),
                "change_1d": p.get("change_1d"),
                "change_7d": p.get("change_7d"),
                "mcap_tvl": p.get("mcapTvl"),
            })

    _defi_cache[cache_key] = result
    return result


async def get_defi_yields(min_tvl: float = 1_000_000) -> dict[str, Any]:
    cache_key = f"defi_yields_{min_tvl}"
    if cache_key in _defi_cache:
        return _defi_cache[cache_key]

    data = await _async_get("https://yields.llama.fi/pools")

    result: dict[str, Any] = {
        "top_yields": [],
        "total_pools": 0,
        "source": "DeFi Llama Yields (free, no API key)",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        pools = data.get("data", [])
        result["total_pools"] = len(pools)
        filtered = [p for p in pools if (p.get("tvlUsd") or 0) >= min_tvl]
        sorted_pools = sorted(filtered, key=lambda x: x.get("apy") or 0, reverse=True)
        for p in sorted_pools[:30]:
            result["top_yields"].append({
                "pool": p.get("pool"),
                "project": p.get("project"),
                "chain": p.get("chain"),
                "symbol": p.get("symbol"),
                "tvl_usd": p.get("tvlUsd"),
                "apy": p.get("apy"),
                "apy_base": p.get("apyBase"),
                "apy_reward": p.get("apyReward"),
                "stablecoin": p.get("stablecoin"),
                "il_risk": p.get("ilRisk"),
                "exposure": p.get("exposure"),
            })

    _defi_cache[cache_key] = result
    return result


async def get_stablecoin_data() -> dict[str, Any]:
    cache_key = "stablecoins"
    if cache_key in _stablecoin_cache:
        return _stablecoin_cache[cache_key]

    data = await _async_get("https://stablecoins.llama.fi/stablecoins?includePrices=true")

    result: dict[str, Any] = {
        "stablecoins": [],
        "total_mcap": 0,
        "source": "DeFi Llama Stablecoins (free, no API key)",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        coins = data.get("peggedAssets", [])
        sorted_coins = sorted(coins, key=lambda x: (x.get("circulating", {}).get("peggedUSD") or 0), reverse=True)
        total = 0
        for c in sorted_coins[:20]:
            circ = c.get("circulating", {}).get("peggedUSD") or 0
            total += circ
            price = c.get("price")
            peg_deviation = None
            if price is not None:
                try:
                    peg_deviation = round((float(price) - 1.0) * 100, 4)
                except (ValueError, TypeError):
                    pass
            result["stablecoins"].append({
                "name": c.get("name"),
                "symbol": c.get("symbol"),
                "circulating_usd": circ,
                "price": price,
                "peg_deviation_pct": peg_deviation,
                "peg_type": c.get("pegType"),
                "peg_mechanism": c.get("pegMechanism"),
                "chains": (c.get("chains") or [])[:10],
            })
        result["total_mcap"] = total

    _stablecoin_cache[cache_key] = result
    return result


async def get_chain_tvl() -> dict[str, Any]:
    cache_key = "chain_tvl"
    if cache_key in _defi_cache:
        return _defi_cache[cache_key]

    data = await _async_get("https://api.llama.fi/v2/chains")

    result: dict[str, Any] = {
        "chains": [],
        "source": "DeFi Llama Chains (free, no API key)",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, list):
        sorted_chains = sorted(data, key=lambda x: x.get("tvl") or 0, reverse=True)
        for c in sorted_chains[:30]:
            result["chains"].append({
                "name": c.get("name"),
                "gecko_id": c.get("gecko_id"),
                "tvl": c.get("tvl"),
                "token_symbol": c.get("tokenSymbol"),
            })

    _defi_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# Fear & Greed Index — Alternative.me (free, no key)
# ─────────────────────────────────────────────────────────────

async def get_fear_greed() -> dict[str, Any]:
    cache_key = "fear_greed"
    if cache_key in _sentiment_cache:
        return _sentiment_cache[cache_key]

    data = await _async_get(
        "https://api.alternative.me/fng/",
        params={"limit": "7", "format": "json"},
    )

    result: dict[str, Any] = {
        "current": None,
        "history": [],
        "source": "Alternative.me Crypto Fear & Greed Index",
        "trust_tier": 5,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        entries = data.get("data", [])
        for entry in entries:
            item = {
                "value": int(entry.get("value", 0)),
                "classification": entry.get("value_classification", ""),
                "timestamp": entry.get("timestamp"),
            }
            result["history"].append(item)
        if result["history"]:
            result["current"] = result["history"][0]

    _sentiment_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# Gas Prices — Public RPC calls (no key)
# ─────────────────────────────────────────────────────────────

async def _rpc_call(rpc_url: str, method: str, params: list | None = None) -> Any:
    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
        try:
            resp = await client.post(
                rpc_url,
                json={"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1},
            )
            data = resp.json()
            return data.get("result")
        except Exception as exc:
            logger.debug("RPC call %s failed on %s: %s", method, rpc_url, exc)
            return None


async def get_gas_prices() -> dict[str, Any]:
    cache_key = "gas_all"
    if cache_key in _gas_cache:
        return _gas_cache[cache_key]

    import asyncio

    async def _get_chain_gas(name: str, rpc: str) -> dict[str, Any]:
        gas_price = await _rpc_call(rpc, "eth_gasPrice")
        block = await _rpc_call(rpc, "eth_getBlockByNumber", ["latest", False])
        gas_gwei = None
        base_fee_gwei = None
        if gas_price:
            try:
                gas_gwei = round(int(gas_price, 16) / 1e9, 4)
            except (ValueError, TypeError):
                pass
        if block and isinstance(block, dict) and block.get("baseFeePerGas"):
            try:
                base_fee_gwei = round(int(block["baseFeePerGas"], 16) / 1e9, 4)
            except (ValueError, TypeError):
                pass
        return {
            "chain": name,
            "gas_price_gwei": gas_gwei,
            "base_fee_gwei": base_fee_gwei,
            "block_number": int(block["number"], 16) if block and isinstance(block, dict) and block.get("number") else None,
        }

    chains = {
        "ethereum": "https://eth.llamarpc.com",
        "base": "https://mainnet.base.org",
        "arbitrum": "https://arb1.arbitrum.io/rpc",
        "optimism": "https://mainnet.optimism.io",
        "polygon": "https://polygon-rpc.com",
    }

    tasks = [_get_chain_gas(name, rpc) for name, rpc in chains.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    chain_gas = []
    for r in results:
        if isinstance(r, dict):
            chain_gas.append(r)

    result = {
        "chains": chain_gas,
        "source": "Public RPC endpoints (no API key)",
        "trust_tier": 1,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _gas_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# ECB Forex Rates — European Central Bank (free, no key)
# ─────────────────────────────────────────────────────────────

async def get_forex_rates() -> dict[str, Any]:
    cache_key = "forex_ecb"
    if cache_key in _market_cache:
        return _market_cache[cache_key]

    result: dict[str, Any] = {
        "rates": {},
        "base": "EUR",
        "source": "European Central Bank (ECB)",
        "trust_tier": 1,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(
                "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
            )
            resp.raise_for_status()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            ns = {"gesmes": "http://www.gesmes.org/xml/2002-08-01", "ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
            cube = root.find(".//ecb:Cube/ecb:Cube", ns)
            if cube is not None:
                result["date"] = cube.get("time")
                for rate in cube.findall("ecb:Cube", ns):
                    currency = rate.get("currency")
                    value = rate.get("rate")
                    if currency and value:
                        result["rates"][currency] = float(value)
                if "USD" in result["rates"]:
                    eur_usd = result["rates"]["USD"]
                    result["eur_usd"] = eur_usd
                    result["usd_eur"] = round(1 / eur_usd, 6)
    except Exception as exc:
        logger.debug("ECB forex fetch failed: %s", exc)

    _market_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# Composite: Full Market Snapshot
# ─────────────────────────────────────────────────────────────

async def get_full_market_snapshot() -> dict[str, Any]:
    import asyncio

    major_prices = get_crypto_prices(
        ["bitcoin", "ethereum", "solana", "cardano", "ripple", "dogecoin", "chainlink", "avalanche-2", "polkadot", "uniswap"]
    )
    global_data = get_crypto_global()
    fear_greed = get_fear_greed()
    gas = get_gas_prices()
    stablecoins = get_stablecoin_data()

    results = await asyncio.gather(
        major_prices, global_data, fear_greed, gas, stablecoins,
        return_exceptions=True,
    )

    def _safe(idx: int) -> dict:
        r = results[idx]
        return r if not isinstance(r, Exception) else {"error": str(r)}

    return {
        "crypto_prices": _safe(0),
        "global_market": _safe(1),
        "fear_greed": _safe(2),
        "gas_prices": _safe(3),
        "stablecoins": _safe(4),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": [
            "CoinGecko (crypto prices, market caps)",
            "Alternative.me (Fear & Greed Index)",
            "Public RPCs (gas prices across 5 chains)",
            "DeFi Llama (stablecoin supply & pegs)",
        ],
    }
