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
# Binance — Real-time CEX data (no key, 6000 weight/min)
# ─────────────────────────────────────────────────────────────

_binance_cache: TTLCache = TTLCache(maxsize=50, ttl=30)


async def get_binance_prices(symbols: list[str] | None = None) -> dict[str, Any]:
    cache_key = f"binance_prices_{'_'.join(sorted(symbols or []))}"
    if cache_key in _binance_cache:
        return _binance_cache[cache_key]

    result: dict[str, Any] = {
        "tickers": [],
        "source": "Binance (no API key, real-time)",
        "trust_tier": 3,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if symbols:
        import asyncio
        tasks = []
        for sym in symbols[:20]:
            tasks.append(_async_get(
                "https://api.binance.com/api/v3/ticker/24hr",
                params={"symbol": sym.upper()},
            ))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, dict):
                result["tickers"].append({
                    "symbol": r.get("symbol"),
                    "price": r.get("lastPrice"),
                    "change_24h_pct": r.get("priceChangePercent"),
                    "high_24h": r.get("highPrice"),
                    "low_24h": r.get("lowPrice"),
                    "volume_24h": r.get("volume"),
                    "quote_volume_24h": r.get("quoteVolume"),
                    "trades_24h": r.get("count"),
                    "bid": r.get("bidPrice"),
                    "ask": r.get("askPrice"),
                })
    else:
        data = await _async_get("https://api.binance.com/api/v3/ticker/24hr")
        if data and isinstance(data, list):
            usdt_pairs = [t for t in data if isinstance(t, dict) and str(t.get("symbol", "")).endswith("USDT")]
            sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x.get("quoteVolume") or 0), reverse=True)
            for t in sorted_pairs[:30]:
                result["tickers"].append({
                    "symbol": t.get("symbol"),
                    "price": t.get("lastPrice"),
                    "change_24h_pct": t.get("priceChangePercent"),
                    "high_24h": t.get("highPrice"),
                    "low_24h": t.get("lowPrice"),
                    "volume_24h": t.get("volume"),
                    "quote_volume_24h": t.get("quoteVolume"),
                    "trades_24h": t.get("count"),
                })

    _binance_cache[cache_key] = result
    return result


async def get_binance_orderbook(symbol: str, limit: int = 20) -> dict[str, Any]:
    cache_key = f"binance_book_{symbol}_{limit}"
    if cache_key in _binance_cache:
        return _binance_cache[cache_key]

    data = await _async_get(
        "https://api.binance.com/api/v3/depth",
        params={"symbol": symbol.upper(), "limit": min(limit, 100)},
    )

    result: dict[str, Any] = {
        "symbol": symbol.upper(),
        "bids": [],
        "asks": [],
        "source": "Binance (no API key, real-time)",
        "trust_tier": 3,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        for bid in (data.get("bids") or [])[:limit]:
            result["bids"].append({"price": bid[0], "quantity": bid[1]})
        for ask in (data.get("asks") or [])[:limit]:
            result["asks"].append({"price": ask[0], "quantity": ask[1]})
        spread = None
        if result["bids"] and result["asks"]:
            try:
                spread = round(float(result["asks"][0]["price"]) - float(result["bids"][0]["price"]), 8)
            except (ValueError, TypeError):
                pass
        result["spread"] = spread

    _binance_cache[cache_key] = result
    return result


async def get_binance_klines(symbol: str, interval: str = "1h", limit: int = 24) -> dict[str, Any]:
    cache_key = f"binance_klines_{symbol}_{interval}_{limit}"
    if cache_key in _binance_cache:
        return _binance_cache[cache_key]

    data = await _async_get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": symbol.upper(), "interval": interval, "limit": min(limit, 100)},
    )

    result: dict[str, Any] = {
        "symbol": symbol.upper(),
        "interval": interval,
        "candles": [],
        "source": "Binance (no API key, real-time)",
        "trust_tier": 3,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, list):
        for k in data:
            if isinstance(k, list) and len(k) >= 6:
                result["candles"].append({
                    "open_time": k[0],
                    "open": k[1],
                    "high": k[2],
                    "low": k[3],
                    "close": k[4],
                    "volume": k[5],
                })

    _binance_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# DexScreener — DEX pair data across all chains (no key)
# ─────────────────────────────────────────────────────────────

_dex_cache: TTLCache = TTLCache(maxsize=50, ttl=60)


async def get_dex_token_pairs(token_address: str) -> dict[str, Any]:
    cache_key = f"dex_token_{token_address}"
    if cache_key in _dex_cache:
        return _dex_cache[cache_key]

    data = await _async_get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}")

    result: dict[str, Any] = {
        "token_address": token_address,
        "pairs": [],
        "source": "DexScreener (free, no API key, real-time DEX data)",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        for pair in (data.get("pairs") or [])[:20]:
            result["pairs"].append({
                "chain": pair.get("chainId"),
                "dex": pair.get("dexId"),
                "pair_address": pair.get("pairAddress"),
                "base_token": pair.get("baseToken", {}).get("symbol"),
                "quote_token": pair.get("quoteToken", {}).get("symbol"),
                "price_usd": pair.get("priceUsd"),
                "price_native": pair.get("priceNative"),
                "txns_24h": pair.get("txns", {}).get("h24", {}),
                "volume_24h": pair.get("volume", {}).get("h24"),
                "liquidity_usd": pair.get("liquidity", {}).get("usd"),
                "price_change_5m": pair.get("priceChange", {}).get("m5"),
                "price_change_1h": pair.get("priceChange", {}).get("h1"),
                "price_change_24h": pair.get("priceChange", {}).get("h24"),
                "fdv": pair.get("fdv"),
            })

    _dex_cache[cache_key] = result
    return result


async def get_dex_search(query: str) -> dict[str, Any]:
    cache_key = f"dex_search_{query}"
    if cache_key in _dex_cache:
        return _dex_cache[cache_key]

    data = await _async_get(
        f"https://api.dexscreener.com/latest/dex/search",
        params={"q": query},
    )

    result: dict[str, Any] = {
        "query": query,
        "pairs": [],
        "source": "DexScreener (free, no API key)",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        for pair in (data.get("pairs") or [])[:15]:
            result["pairs"].append({
                "chain": pair.get("chainId"),
                "dex": pair.get("dexId"),
                "base_token": pair.get("baseToken", {}).get("symbol"),
                "base_token_name": pair.get("baseToken", {}).get("name"),
                "quote_token": pair.get("quoteToken", {}).get("symbol"),
                "price_usd": pair.get("priceUsd"),
                "volume_24h": pair.get("volume", {}).get("h24"),
                "liquidity_usd": pair.get("liquidity", {}).get("usd"),
                "price_change_24h": pair.get("priceChange", {}).get("h24"),
                "url": pair.get("url"),
            })

    _dex_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# Mempool.space — Bitcoin fees, mempool, Lightning (no key)
# ─────────────────────────────────────────────────────────────

_btc_cache: TTLCache = TTLCache(maxsize=20, ttl=30)


async def get_btc_fees() -> dict[str, Any]:
    cache_key = "btc_fees"
    if cache_key in _btc_cache:
        return _btc_cache[cache_key]

    import asyncio
    fees_task = _async_get("https://mempool.space/api/v1/fees/recommended")
    mempool_task = _async_get("https://mempool.space/api/mempool")
    hashrate_task = _async_get("https://mempool.space/api/v1/mining/hashrate/1m")

    results = await asyncio.gather(fees_task, mempool_task, hashrate_task, return_exceptions=True)

    fees = results[0] if not isinstance(results[0], Exception) else None
    mempool = results[1] if not isinstance(results[1], Exception) else None
    hashrate = results[2] if not isinstance(results[2], Exception) else None

    result: dict[str, Any] = {
        "recommended_fees": {},
        "mempool": {},
        "mining": {},
        "source": "mempool.space (free, no API key, real-time)",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if fees and isinstance(fees, dict):
        result["recommended_fees"] = {
            "fastest_sat_vb": fees.get("fastestFee"),
            "half_hour_sat_vb": fees.get("halfHourFee"),
            "hour_sat_vb": fees.get("hourFee"),
            "economy_sat_vb": fees.get("economyFee"),
            "minimum_sat_vb": fees.get("minimumFee"),
        }

    if mempool and isinstance(mempool, dict):
        result["mempool"] = {
            "tx_count": mempool.get("count"),
            "vsize_bytes": mempool.get("vsize"),
            "total_fee_btc": mempool.get("total_fee"),
        }

    if hashrate and isinstance(hashrate, dict):
        hr = hashrate.get("hashrates", [])
        if hr:
            latest = hr[-1] if isinstance(hr, list) else {}
            result["mining"] = {
                "current_hashrate": latest.get("avgHashrate") if isinstance(latest, dict) else None,
                "current_difficulty": hashrate.get("currentDifficulty"),
            }

    _btc_cache[cache_key] = result
    return result


async def get_btc_lightning() -> dict[str, Any]:
    cache_key = "btc_lightning"
    if cache_key in _btc_cache:
        return _btc_cache[cache_key]

    data = await _async_get("https://mempool.space/api/v1/lightning/statistics/latest")

    result: dict[str, Any] = {
        "lightning": {},
        "source": "mempool.space Lightning (free, no API key)",
        "trust_tier": 4,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, dict):
        latest = data.get("latest", data)
        result["lightning"] = {
            "channel_count": latest.get("channel_count"),
            "node_count": latest.get("node_count"),
            "total_capacity_btc": latest.get("total_capacity"),
            "average_capacity_sat": latest.get("avg_capacity"),
            "median_base_fee_msat": latest.get("med_base_fee_mtokens"),
            "median_fee_rate_ppm": latest.get("med_fee_rate"),
        }

    _btc_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# TreasuryDirect — Auction results (Tier 1 government, no key)
# ─────────────────────────────────────────────────────────────

_auction_cache: TTLCache = TTLCache(maxsize=10, ttl=900)


async def get_treasury_auctions(security_type: str = "", limit: int = 10) -> dict[str, Any]:
    cache_key = f"auctions_{security_type}_{limit}"
    if cache_key in _auction_cache:
        return _auction_cache[cache_key]

    params: dict[str, str] = {
        "format": "json",
        "pagesize": str(min(limit, 25)),
    }
    if security_type:
        params["type"] = security_type

    data = await _async_get(
        "https://www.treasurydirect.gov/TA_WS/securities/auctioned",
        params=params,
    )

    result: dict[str, Any] = {
        "auctions": [],
        "security_type_filter": security_type or "all",
        "source": "TreasuryDirect (U.S. Department of the Treasury)",
        "trust_tier": 1,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if data and isinstance(data, list):
        for auction in data[:limit]:
            if isinstance(auction, dict):
                result["auctions"].append({
                    "cusip": auction.get("cusip"),
                    "security_type": auction.get("securityType"),
                    "security_term": auction.get("securityTerm"),
                    "auction_date": auction.get("auctionDate"),
                    "issue_date": auction.get("issueDate"),
                    "maturity_date": auction.get("maturityDate"),
                    "high_yield": auction.get("highYield"),
                    "interest_rate": auction.get("interestRate"),
                    "bid_to_cover_ratio": auction.get("bidToCoverRatio"),
                    "competitive_accepted": auction.get("competitiveAccepted"),
                    "total_accepted": auction.get("totalAccepted"),
                    "total_tendered": auction.get("totalTendered"),
                })

    _auction_cache[cache_key] = result
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
