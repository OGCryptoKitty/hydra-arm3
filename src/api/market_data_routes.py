"""
market_data_routes.py — HYDRA Live Market Data Endpoints
=========================================================
Perpetually live market data from free, no-API-key sources:
  - CoinGecko: crypto prices, global market, trending
  - DeFi Llama: TVL, yields, stablecoins, chain TVL
  - Alternative.me: Fear & Greed Index
  - Public RPCs: gas prices across 5 chains
  - ECB: major forex rates
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Optional

market_data_router = APIRouter(tags=["market-data"])


@market_data_router.get("/v1/market/prices")
async def crypto_prices(
    ids: str = Query(
        "bitcoin,ethereum,solana",
        description="Comma-separated CoinGecko coin IDs",
    ),
    vs: str = Query("usd", description="Quote currency (usd, eur, btc, eth)"),
) -> dict:
    """
    Live crypto prices, market caps, 24h volume & change.
    Source: CoinGecko (free, no API key). Refreshes every 60 seconds.
    $0.001 USDC.
    """
    from src.services.live_market_data import get_crypto_prices

    coin_ids = [c.strip() for c in ids.split(",") if c.strip()][:20]
    return await get_crypto_prices(coin_ids, vs_currency=vs)


@market_data_router.get("/v1/market/global")
async def global_market() -> dict:
    """
    Global crypto market overview: total market cap, BTC/ETH dominance,
    24h volume, active coins count, market cap change.
    Source: CoinGecko. $0.001 USDC.
    """
    from src.services.live_market_data import get_crypto_global

    return await get_crypto_global()


@market_data_router.get("/v1/market/trending")
async def trending_coins() -> dict:
    """
    Top trending cryptocurrencies on CoinGecko (most searched in last 24h).
    Source: CoinGecko. $0.001 USDC.
    """
    from src.services.live_market_data import get_trending_coins

    return await get_trending_coins()


@market_data_router.get("/v1/market/fear-greed")
async def fear_greed_index() -> dict:
    """
    Crypto Fear & Greed Index — 0 (extreme fear) to 100 (extreme greed).
    7-day history included. Source: Alternative.me. $0.001 USDC.
    """
    from src.services.live_market_data import get_fear_greed

    return await get_fear_greed()


@market_data_router.get("/v1/market/gas")
async def multi_chain_gas() -> dict:
    """
    Live gas prices across Ethereum, Base, Arbitrum, Optimism, Polygon.
    Direct from public RPCs — 15 second cache. $0.001 USDC.
    """
    from src.services.live_market_data import get_gas_prices

    return await get_gas_prices()


@market_data_router.get("/v1/market/stablecoins")
async def stablecoin_monitor() -> dict:
    """
    Top 20 stablecoins by circulating supply with peg deviation tracking.
    Source: DeFi Llama. $0.002 USDC.
    """
    from src.services.live_market_data import get_stablecoin_data

    return await get_stablecoin_data()


@market_data_router.get("/v1/market/defi/tvl")
async def defi_tvl() -> dict:
    """
    Top 25 DeFi protocols by TVL with 1d/7d change and category breakdown.
    Source: DeFi Llama. $0.002 USDC.
    """
    from src.services.live_market_data import get_defi_tvl

    return await get_defi_tvl()


@market_data_router.get("/v1/market/defi/yields")
async def defi_yields(
    min_tvl: float = Query(1_000_000, description="Minimum TVL in USD to include"),
) -> dict:
    """
    Top DeFi yield opportunities across all chains. Filtered by TVL.
    Includes base APY, reward APY, IL risk, stablecoin flag.
    Source: DeFi Llama. $0.005 USDC.
    """
    from src.services.live_market_data import get_defi_yields

    return await get_defi_yields(min_tvl=min_tvl)


@market_data_router.get("/v1/market/defi/chains")
async def chain_tvl() -> dict:
    """
    Top 30 blockchains by total DeFi TVL.
    Source: DeFi Llama. $0.001 USDC.
    """
    from src.services.live_market_data import get_chain_tvl

    return await get_chain_tvl()


@market_data_router.get("/v1/market/forex")
async def forex_rates() -> dict:
    """
    Major forex rates from the European Central Bank.
    ~30 currency pairs vs EUR, with EUR/USD and USD/EUR highlighted.
    Updated daily. Source: ECB. $0.001 USDC.
    """
    from src.services.live_market_data import get_forex_rates

    return await get_forex_rates()


@market_data_router.get("/v1/market/snapshot")
async def full_market_snapshot() -> dict:
    """
    Complete market snapshot: top 10 crypto prices, global market data,
    fear & greed index, gas prices across 5 chains, stablecoin pegs.
    All from free, live, no-API-key sources. $0.05 USDC.
    """
    from src.services.live_market_data import get_full_market_snapshot

    return await get_full_market_snapshot()


# ── Binance (real-time CEX data, no API key) ────────────────

@market_data_router.get("/v1/market/binance/prices")
async def binance_prices(
    symbols: Optional[str] = Query(
        None,
        description="Comma-separated Binance symbols (e.g., BTCUSDT,ETHUSDT). Omit for top 30 by volume.",
    ),
) -> dict:
    """
    Real-time Binance prices with 24h stats (volume, high/low, trades, bid/ask).
    Source: Binance public API (no key, real-time). $0.002 USDC.
    """
    from src.services.live_market_data import get_binance_prices

    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else None
    return await get_binance_prices(sym_list)


@market_data_router.get("/v1/market/binance/orderbook")
async def binance_orderbook(
    symbol: str = Query("BTCUSDT", description="Binance trading pair symbol"),
    limit: int = Query(20, ge=5, le=100, description="Order book depth"),
) -> dict:
    """
    Binance order book with bids, asks, and spread.
    Source: Binance public API (no key, real-time). $0.005 USDC.
    """
    from src.services.live_market_data import get_binance_orderbook

    return await get_binance_orderbook(symbol, limit)


@market_data_router.get("/v1/market/binance/klines")
async def binance_klines(
    symbol: str = Query("BTCUSDT", description="Binance trading pair symbol"),
    interval: str = Query("1h", description="Candle interval: 1m, 5m, 15m, 1h, 4h, 1d"),
    limit: int = Query(24, ge=1, le=100, description="Number of candles"),
) -> dict:
    """
    Binance candlestick/OHLCV data for charting and technical analysis.
    Source: Binance public API (no key, real-time). $0.005 USDC.
    """
    from src.services.live_market_data import get_binance_klines

    return await get_binance_klines(symbol, interval, limit)


# ── DexScreener (DEX pair data across all chains) ───────────

@market_data_router.get("/v1/market/dex/token")
async def dex_token_pairs(
    address: str = Query(..., description="Token contract address (any chain)"),
) -> dict:
    """
    All DEX trading pairs for a token across all chains and DEXes.
    Includes price, volume, liquidity, and price changes.
    Source: DexScreener (free, no key, real-time). $0.01 USDC.
    """
    from src.services.live_market_data import get_dex_token_pairs

    return await get_dex_token_pairs(address)


@market_data_router.get("/v1/market/dex/search")
async def dex_search(
    q: str = Query(..., description="Search query (token name, symbol, or address)"),
) -> dict:
    """
    Search DEX pairs by token name, symbol, or address across all chains.
    Source: DexScreener (free, no key). $0.005 USDC.
    """
    from src.services.live_market_data import get_dex_search

    return await get_dex_search(q)


# ── Mempool.space (Bitcoin network data) ────────────────────

@market_data_router.get("/v1/market/bitcoin/fees")
async def bitcoin_fees() -> dict:
    """
    Bitcoin recommended fees, mempool stats, and mining hashrate/difficulty.
    Source: mempool.space (free, no key, real-time). $0.002 USDC.
    """
    from src.services.live_market_data import get_btc_fees

    return await get_btc_fees()


@market_data_router.get("/v1/market/bitcoin/lightning")
async def bitcoin_lightning() -> dict:
    """
    Bitcoin Lightning Network statistics: node count, channel count,
    total capacity, fee rates.
    Source: mempool.space (free, no key). $0.002 USDC.
    """
    from src.services.live_market_data import get_btc_lightning

    return await get_btc_lightning()


# ── TreasuryDirect (Tier 1 government auction data) ─────────

@market_data_router.get("/v1/market/treasury/auctions")
async def treasury_auctions(
    security_type: Optional[str] = Query(
        None,
        description="Filter: Bill, Note, Bond, TIPS, FRN, CMB",
    ),
    limit: int = Query(10, ge=1, le=25, description="Number of recent auctions"),
) -> dict:
    """
    U.S. Treasury auction results: high yield, bid-to-cover ratio,
    accepted/tendered amounts. Tier 1 government data.
    Source: TreasuryDirect (no key). $0.005 USDC.
    """
    from src.services.live_market_data import get_treasury_auctions

    return await get_treasury_auctions(security_type or "", limit)
