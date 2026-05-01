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
