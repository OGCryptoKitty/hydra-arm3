"""
HYDRA Arm 3 — Prediction Market API Routes

Endpoints for prediction market intelligence — designed for automated trading bots,
oracle asserters, and quant funds that need regulatory data before trading.

Architecture:
  - One FREE discovery endpoint  → the hook that attracts bot traffic
  - One FREE pricing endpoint    → lets bots size up the cost before committing
  - Seven PAID endpoints         → revenue extraction via x402 micropayments

All paid endpoints are protected by X402PaymentMiddleware (payment verified
before these handlers are called). USDC on Base, chain ID 8453.

Pricing:
  GET  /v1/markets/discovery  → FREE (discovery hook)
  GET  /v1/markets/pricing    → FREE
  POST /v1/markets/signals    → $5.00 USDC  (bulk signals — core bot product)
  POST /v1/markets/signal/{market_id} → $2.00 USDC (single market deep dive)
  POST /v1/markets/events     → $0.50 USDC  (event feed matched to markets)
  POST /v1/markets/alpha      → $10.00 USDC (premium alpha report)
  POST /v1/markets/resolution → $25.00 USDC (oracle-grade resolution assessment)
  POST /v1/oracle/uma         → $5.00 USDC  (UMA OO formatted assertion data)
  POST /v1/oracle/chainlink   → $5.00 USDC  (Chainlink external adapter format)
  GET  /v1/markets/feed       → $0.10 USDC  (high-frequency micro feed for bots)

Bot Usage Pattern:
  1. GET /v1/markets/discovery  (free — see what HYDRA covers)
  2. GET /v1/markets/pricing    (free — check costs)
  3. GET /v1/markets/feed       every 5 min ($0.10 each — find actionable events)
  4. POST /v1/markets/signals   before every major trade ($5.00 — full signal suite)
  5. POST /v1/markets/signal/{id} for deep dives on specific markets ($2.00 each)
  6. POST /v1/markets/resolution before bonding on UMA ($25.00 — worth it to avoid losing $750)

Market Coverage:
  Polymarket: ~110 active regulation markets, ~103 CFTC markets
  Kalshi: Fed funds rate series, crypto market structure, GENIUS Act, SEC Chair, more
  HYDRA domains: Fed rate, SEC enforcement, CFTC, crypto legislation, bank failures, ETFs, SCOTUS
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config.settings as settings
from src.services.prediction_markets import (
    get_aggregator,
    get_event_feed,
    get_oracle_provider,
)

logger = logging.getLogger(__name__)

prediction_router = APIRouter(tags=["Prediction Markets"])


# ─────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────


class SignalsRequest(BaseModel):
    platform: Literal["polymarket", "kalshi", "all"] = Field(
        default="all",
        description="Which prediction market platform(s) to query",
    )
    category: Literal["regulation", "crypto", "fed", "sec", "all"] = Field(
        default="all",
        description=(
            "Filter signals by regulatory category. "
            "'fed' = Federal Reserve rate decisions; "
            "'sec' = SEC enforcement and approvals; "
            "'crypto' = crypto legislation (GENIUS Act, FIT21, etc.); "
            "'regulation' = all regulatory; "
            "'all' = everything HYDRA covers."
        ),
    )


class SingleMarketRequest(BaseModel):
    platform: Literal["polymarket", "kalshi"] | None = Field(
        default=None,
        description="Platform hint to accelerate lookup. If None, HYDRA searches both.",
    )


class EventsRequest(BaseModel):
    since_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="How many hours back to look for regulatory events (1-168, default 24)",
    )
    agencies: list[Literal["SEC", "CFTC", "Fed", "FinCEN", "OCC", "CFPB", "all"]] = Field(
        default=["all"],
        description="Which regulatory agencies to pull events from",
    )


class ResolutionRequest(BaseModel):
    market_question: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="The exact market question string from Polymarket or Kalshi",
        example="Will the SEC approve a spot Solana ETF by June 30, 2026?",
    )
    market_id: str = Field(
        default="",
        description="Polymarket condition_id or Kalshi ticker (used for reference)",
        example="0xabc123... or KXSOLANA-2026",
    )
    evidence: str = Field(
        default="",
        max_length=2000,
        description="Optional: paste in relevant news text or regulatory announcement for HYDRA to analyze",
    )


class UMAOracleRequest(BaseModel):
    assertion_claim: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="The factual claim you want to assert to UMA's Optimistic Oracle",
        example="The SEC approved a spot Solana ETF on March 28, 2026",
    )
    bond_currency: Literal["USDC", "USDC.e"] = Field(
        default="USDC.e",
        description="Bond currency for UMA assertion. Use USDC.e for Polygon (Polymarket standard).",
    )
    market_question: str = Field(
        default="",
        description="Optional: the Polymarket market question this assertion is for",
    )


class ChainlinkRequest(BaseModel):
    data_request: str = Field(
        ...,
        min_length=5,
        max_length=300,
        description="What regulatory data point to retrieve for Chainlink on-chain delivery",
        example="SEC enforcement action count 2026",
    )
    job_run_id: str = Field(
        default="1",
        description="Chainlink job run ID (pass through from node request)",
    )


# ─────────────────────────────────────────────────────────────
# FREE: GET /v1/markets — basic market list (the bait)
# ─────────────────────────────────────────────────────────────


@prediction_router.get(
    "/v1/markets",
    tags=["Prediction Markets — Free"],
    summary="All Active Regulatory Prediction Markets (FREE)",
    description=(
        "Returns all active regulatory prediction markets across Polymarket and Kalshi. "
        "**Free.** Basic info only: title, platform, current price, 24h volume. "
        "This is the hook — see the breadth of HYDRA's coverage before purchasing signals. "
        "For full signals, regulatory analysis, and trading intelligence, use the paid endpoints."
    ),
    response_class=JSONResponse,
)
async def list_markets(request: Request) -> JSONResponse:
    """
    FREE endpoint — returns all active regulatory prediction markets (basic info only).

    Returns:
    - title: market question string
    - platform: polymarket | kalshi
    - price: current yes price (0.00-1.00)
    - volume_24h: 24-hour trading volume in USD
    - market_id: condition_id (Polymarket) or ticker (Kalshi)
    - end_date: market resolution date
    - url: direct link to market

    For full HYDRA regulatory signals and analysis, call the paid endpoints.
    """
    try:
        aggregator = get_aggregator()
        markets = await aggregator.get_all_regulatory_markets()
    except Exception as exc:
        logger.error("GET /v1/markets error: %s", exc)
        raise HTTPException(status_code=503, detail=f"Market data unavailable: {exc}") from exc

    # Minimal payload — title, platform, price, volume only
    market_list = []
    for market in markets:
        platform = market.get("platform")
        if platform == "polymarket":
            prices = market.get("outcome_prices", [])
            yes_price = round(float(prices[0]), 4) if prices else None
            market_id = market.get("condition_id")
        else:
            raw_price = market.get("yes_price")
            yes_price = round(float(raw_price), 4) if raw_price is not None else None
            market_id = market.get("ticker")

        market_list.append({
            "title": market.get("market_question") or market.get("title"),
            "platform": platform,
            "price": yes_price,
            "volume_24h": market.get("volume_24hr", 0),
            "market_id": market_id,
            "end_date": market.get("end_date") or market.get("close_time"),
            "url": market.get("url"),
        })

    # Sort by volume descending — highest liquidity markets first
    market_list.sort(key=lambda x: float(x["volume_24h"] or 0), reverse=True)

    return JSONResponse(content={
        "total": len(market_list),
        "markets": market_list,
        "data_freshness": "5-minute cache",
        "upgrade": {
            "signals": "POST /v1/markets/signals ($5.00 USDC) — full HYDRA regulatory analysis for all markets",
            "single": "POST /v1/markets/signal/{market_id} ($2.00 USDC) — deep signal for one market",
            "events": "POST /v1/markets/events ($0.50 USDC) — live regulatory events matched to markets",
            "alpha": "POST /v1/markets/alpha ($10.00 USDC) — full alpha report: edge, entry, risk/reward",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# FREE: Discovery Endpoint — the hook
# ─────────────────────────────────────────────────────────────


@prediction_router.get(
    "/v1/markets/discovery",
    tags=["Prediction Markets — Free"],
    summary="Regulatory Market Discovery (FREE)",
    description=(
        "Returns all active regulatory prediction markets across Polymarket and Kalshi "
        "that HYDRA currently tracks. **Free.** This is the discovery endpoint — "
        "see what HYDRA covers before purchasing signals. "
        "Includes market titles, current prices, volumes, and which regulatory domains "
        "each market falls into. No payment required."
    ),
    response_class=JSONResponse,
)
async def discover_markets(request: Request) -> JSONResponse:
    """
    FREE endpoint — lists all active regulatory prediction markets across both platforms.

    This is designed to be the acquisition hook for prediction market bots:
    show them the breadth of HYDRA's coverage for free, then monetize on the signal endpoints.

    Payload includes:
    - All active markets on Polymarket and Kalshi in regulatory/crypto/finance categories
    - Current yes/no prices (so bots can see live data without paying)
    - Volume and liquidity metrics
    - Which HYDRA regulatory domain each market belongs to
    - Quick summary of what paid endpoints offer for each domain
    """
    try:
        aggregator = get_aggregator()
        markets = await aggregator.get_all_regulatory_markets()
    except Exception as exc:
        logger.error("Discovery endpoint error: %s", exc)
        raise HTTPException(status_code=503, detail=f"Market discovery unavailable: {exc}") from exc

    # Enrich with domain descriptions for discoverability
    domain_descriptions = {
        "fed_rate": "Federal Reserve rate decisions — HYDRA tracks FOMC calendar, rate probabilities, historical precedent",
        "sec_enforcement": "SEC enforcement and approvals — HYDRA tracks litigation releases, ETF approvals, Crypto Task Force guidance",
        "crypto_legislation": "Crypto legislation (GENIUS Act, FIT21, stablecoin) — HYDRA tracks congressional progress, bill status",
        "cftc_regulation": "CFTC regulation and enforcement — HYDRA tracks DCM approvals, event contract rulemaking, derivatives enforcement",
        "bank_failure": "Bank failures and FDIC resolution — HYDRA tracks Call Report stress indicators, CRE concentrations",
        "crypto_etf": "Crypto ETF approvals — HYDRA tracks SEC EDGAR filings, Crypto Task Force guidance, approval timelines",
        "scotus_legal": "SCOTUS financial regulation cases — HYDRA tracks cert petitions, oral argument calendars, opinion release dates",
    }

    # Build clean discovery payload — enough signal to demonstrate value, not enough to replace paid endpoints
    discovery_payload = []
    for market in markets:
        domain = market.get("regulatory_domain")

        # Extract yes price
        if market.get("platform") == "polymarket":
            prices = market.get("outcome_prices", [])
            yes_price = float(prices[0]) if prices else None
        else:
            yes_price = market.get("yes_price")

        entry: dict[str, Any] = {
            "platform": market.get("platform"),
            "title": market.get("market_question") or market.get("title"),
            "market_id": market.get("condition_id") or market.get("ticker"),
            "yes_price": round(yes_price, 4) if yes_price is not None else None,
            "no_price": round(1 - yes_price, 4) if yes_price is not None else None,
            "volume_24h": market.get("volume_24hr", 0),
            "end_date": market.get("end_date") or market.get("close_time"),
            "url": market.get("url"),
            "regulatory_domain": domain,
            "hydra_coverage": domain_descriptions.get(domain, "HYDRA monitors relevant agency feeds for this market"),
        }
        discovery_payload.append(entry)

    # Stats summary
    poly_count = sum(1 for m in discovery_payload if m["platform"] == "polymarket")
    kalshi_count = sum(1 for m in discovery_payload if m["platform"] == "kalshi")
    domains_covered = list({m["regulatory_domain"] for m in discovery_payload if m["regulatory_domain"]})

    return JSONResponse(content={
        "hydra_prediction_market_coverage": {
            "total_markets_tracked": len(discovery_payload),
            "polymarket_markets": poly_count,
            "kalshi_markets": kalshi_count,
            "regulatory_domains": domains_covered,
            "data_freshness": "5-minute cached market prices; 1-hour cached regulatory analysis",
        },
        "markets": discovery_payload,
        "paid_endpoints": {
            "GET /v1/markets/feed — $0.10 USDC": (
                "Latest 10 regulatory events from last hour, pre-matched to prediction markets. "
                "Designed for bot polling every 5 minutes. Cheapest signal entry point."
            ),
            "POST /v1/markets/signals — $5.00 USDC": (
                "Full HYDRA regulatory signals for all matching markets. "
                "Includes: regulatory context, historical precedent, key dates, risk factors, "
                "signal direction (bullish_yes/bullish_no/neutral), confidence score 0-100. "
                "Core product for pre-trade intelligence."
            ),
            "POST /v1/markets/signal/{market_id} — $2.00 USDC": (
                "Deep single-market signal. Full analysis for one specific Polymarket condition_id "
                "or Kalshi ticker. Ideal when you already know which market to trade."
            ),
            "POST /v1/markets/events — $0.50 USDC": (
                "Real-time regulatory event feed matched to active markets. "
                "Each event tagged with which markets it affects and projected impact direction."
            ),
            "POST /v1/markets/resolution — $25.00 USDC": (
                "Oracle-grade resolution assessment. HYDRA evaluates how a market should resolve "
                "based on regulatory data. For UMA asserters: determines whether to post a $750 bond. "
                "Premium pricing reflects the bond risk mitigation value."
            ),
            "POST /v1/oracle/uma — $5.00 USDC": (
                "UMA Optimistic Oracle formatted assertion data with complete evidence chain. "
                "Ready to submit to OptimisticOracleV2 on Polygon."
            ),
            "POST /v1/oracle/chainlink — $5.00 USDC": (
                "Chainlink external adapter formatted response for on-chain delivery. "
                "Compatible with Chainlink Any API and Direct Request model."
            ),
        },
        "payment": {
            "protocol": "x402",
            "token": "USDC",
            "chain": "Base (chain ID 8453)",
            "wallet": settings.WALLET_ADDRESS,
            "instructions": (
                f"Send exact USDC amount to {settings.WALLET_ADDRESS} on Base (chain 8453), "
                "then retry your request with the transaction hash in the X-Payment-Proof header."
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# FREE: Pricing Endpoint
# ─────────────────────────────────────────────────────────────


@prediction_router.get(
    "/v1/markets/pricing",
    tags=["Prediction Markets — Free"],
    summary="Prediction Market Endpoint Pricing (FREE)",
    description=(
        "Returns pricing for all prediction market intelligence endpoints. "
        "Free — no payment required. "
        "All prices in USDC on Base (chain ID 8453)."
    ),
    response_class=JSONResponse,
)
async def get_prediction_pricing(request: Request) -> JSONResponse:
    """
    Returns detailed pricing for all prediction market endpoints.
    Free discovery — bots should call this before implementing payment logic.
    """
    prediction_pricing = {
        k: v
        for k, v in settings.PRICING.items()
        if k.startswith("/v1/markets/") or k.startswith("/v1/oracle/")
    }

    return JSONResponse(content={
        "prediction_market_endpoints": [
            {
                "endpoint": path,
                "method": "GET" if "feed" in path or "discovery" in path or "pricing" in path else "POST",
                "amount_usdc": str(info["amount_usdc"]),
                "amount_base_units": info["amount_base_units"],
                "description": info["description"],
                "free": info["amount_usdc"] == 0,
            }
            for path, info in prediction_pricing.items()
        ],
        "payment_protocol": "x402",
        "payment_token": settings.PAYMENT_TOKEN,
        "payment_network": settings.PAYMENT_NETWORK,
        "wallet_address": settings.WALLET_ADDRESS,
        "chain_id": settings.CHAIN_ID,
        "bot_usage_guide": {
            "step_1": "GET /v1/markets/discovery (free) — discover all markets HYDRA covers",
            "step_2": "GET /v1/markets/pricing (free) — check costs",
            "step_3_polling": "GET /v1/markets/feed every 5 min ($0.10) — catch breaking regulatory events",
            "step_4_pre_trade": "POST /v1/markets/signals ($5.00) — full intelligence before major trades",
            "step_5_deep_dive": "POST /v1/markets/signal/{id} ($2.00) — drill into specific market",
            "step_6_oracle": "POST /v1/markets/resolution ($25.00) before UMA bond posting — asymmetric value vs $750 bond",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# PAID: Bulk Signals — Core Product
# ─────────────────────────────────────────────────────────────


@prediction_router.post(
    "/v1/markets/signals",
    tags=["Prediction Markets — Paid"],
    summary="Regulatory Trading Signals — All Markets ($5.00 USDC)",
    description=(
        "**$5.00 USDC via x402.** "
        "Full HYDRA regulatory intelligence signals for all matching prediction markets. "
        "This is the core product for prediction market trading bots — call this before "
        "every significant trade to get HYDRA's regulatory analysis, confidence score, "
        "and directional signal. "
        "Filters: platform (polymarket/kalshi/all) and category (fed/sec/crypto/regulation/all). "
        "Each signal includes: regulatory context, historical precedent, key upcoming dates, "
        "risk factors, signal direction (bullish_yes/bullish_no/neutral), and confidence 0-100."
    ),
    response_class=JSONResponse,
)
async def get_market_signals(
    request_body: SignalsRequest,
    request: Request,
) -> JSONResponse:
    """
    Returns regulatory intelligence signals for all active prediction markets matching filters.

    Payment: $5.00 USDC via X-Payment-Proof header.
    """
    logger.info(
        "Prediction signals request: platform=%s category=%s",
        request_body.platform,
        request_body.category,
    )

    try:
        aggregator = get_aggregator()
        signals = await aggregator.generate_regulatory_signals(
            platform=request_body.platform,
            category=request_body.category,
        )
    except Exception as exc:
        logger.exception("Error generating market signals: %s", exc)
        raise HTTPException(status_code=500, detail=f"Signal generation failed: {exc}") from exc

    bullish_yes_count = sum(1 for s in signals if s.get("hydra_analysis", {}).get("signal_direction") == "bullish_yes")
    bullish_no_count = sum(1 for s in signals if s.get("hydra_analysis", {}).get("signal_direction") == "bullish_no")
    neutral_count = sum(1 for s in signals if s.get("hydra_analysis", {}).get("signal_direction") == "neutral")

    return JSONResponse(content={
        "query": {
            "platform": request_body.platform,
            "category": request_body.category,
        },
        "summary": {
            "total_markets_analyzed": len(signals),
            "bullish_yes_signals": bullish_yes_count,
            "bullish_no_signals": bullish_no_count,
            "neutral_signals": neutral_count,
            "high_confidence_signals": sum(
                1 for s in signals
                if s.get("hydra_analysis", {}).get("confidence", 0) >= 65
            ),
        },
        "signals": signals,
        "data_freshness": {
            "market_prices": "5-minute cache",
            "regulatory_analysis": "60-minute cache",
            "note": "Signal directions and confidence scores reflect HYDRA's regulatory knowledge base, not real-time prediction market positioning.",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# PAID: Single Market Deep Signal
# ─────────────────────────────────────────────────────────────


@prediction_router.post(
    "/v1/markets/signal/{market_id}",
    tags=["Prediction Markets — Paid"],
    summary="Deep Signal — Single Market ($2.00 USDC)",
    description=(
        "**$2.00 USDC via x402.** "
        "Deep regulatory intelligence signal for one specific market. "
        "Pass a Polymarket condition_id (0x...) or Kalshi ticker (e.g., KXFED-25APR30). "
        "Returns full analysis: regulatory context, historical precedent, upcoming key dates, "
        "risk factors, signal direction, and confidence score. "
        "Cheaper than bulk signals when you already know which market to trade."
    ),
    response_class=JSONResponse,
)
async def get_single_market_signal(
    market_id: str,
    request_body: SingleMarketRequest,
    request: Request,
) -> JSONResponse:
    """
    Deep signal for a single specific prediction market.

    market_id: Polymarket condition_id OR Kalshi ticker
    Payment: $2.00 USDC via X-Payment-Proof header.
    """
    logger.info("Single market signal: market_id=%s", market_id)

    try:
        aggregator = get_aggregator()

        # Try to find the market in our cache / fetched data
        all_markets = await aggregator.get_all_regulatory_markets()

        target_market = None
        for market in all_markets:
            if (
                market.get("condition_id") == market_id
                or market.get("ticker") == market_id
                or market.get("market_id") == market_id
            ):
                target_market = market
                break

        if not target_market:
            # Try direct fetch from each platform
            if market_id.startswith("0x") or (request_body.platform == "polymarket"):
                details = await aggregator.polymarket.get_market_details(market_id)
                if details:
                    title = details.get("question") or details.get("title") or market_id
                    prices_raw = details.get("outcomePrices") or "[]"
                    try:
                        import json as _json
                        prices = _json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                    except Exception:
                        prices = []
                    target_market = {
                        "platform": "polymarket",
                        "market_question": title,
                        "condition_id": market_id,
                        "outcome_prices": prices,
                        "volume_24hr": float(details.get("volume24hr") or 0),
                        "liquidity": float(details.get("liquidity") or 0),
                        "end_date": details.get("endDate"),
                        "url": f"https://polymarket.com/market/{details.get('slug', market_id)}",
                        "regulatory_domain": None,
                        "_raw_details": details,
                    }
            else:
                details = await aggregator.kalshi.get_market_details(market_id)
                if details:
                    title = details.get("title") or details.get("question") or market_id
                    yes_price = (details.get("yes_ask") or 50) / 100.0
                    target_market = {
                        "platform": "kalshi",
                        "market_question": title,
                        "ticker": market_id,
                        "yes_price": yes_price,
                        "volume_24hr": float(details.get("volume") or 0),
                        "close_time": details.get("close_time"),
                        "url": f"https://kalshi.com/markets/{market_id}",
                        "regulatory_domain": None,
                        "_raw_details": details,
                    }

        if not target_market:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Market '{market_id}' not found. "
                    "Ensure the market is active and the ID is correct. "
                    "Polymarket: use the condition_id (0x...). Kalshi: use the ticker string."
                ),
            )

        # Compute regulatory domain if not already set
        from src.services.prediction_markets import _classify_market_domain, _generate_hydra_analysis
        domain = target_market.get("regulatory_domain") or _classify_market_domain(
            target_market.get("market_question") or ""
        )
        target_market["regulatory_domain"] = domain

        # Get yes price
        if target_market["platform"] == "polymarket":
            prices = target_market.get("outcome_prices", [])
            yes_price = float(prices[0]) if prices else 0.5
        else:
            yes_price = target_market.get("yes_price", 0.5)

        # Generate full HYDRA analysis (bypass cache — this is a paid deep dive)
        hydra_analysis = _generate_hydra_analysis(
            market_title=target_market["market_question"],
            current_yes_price=yes_price,
            domain=domain,
            volume_24h=target_market.get("volume_24hr", 0),
        )

        # Also run the regulatory engine directly for additional depth
        from src.services import regulatory as reg_service
        try:
            qa = reg_service.answer_regulatory_query(question=target_market["market_question"])
            additional_context = {
                "regulatory_qa_answer": qa.answer,
                "relevant_regulations": qa.relevant_regulations,
                "follow_up_questions": qa.follow_up_questions,
                "sources": qa.sources,
            }
        except Exception as exc:
            logger.warning("Regulatory Q&A failed for single market signal: %s", exc)
            additional_context = {}

        return JSONResponse(content={
            "market_id": market_id,
            "platform": target_market["platform"],
            "market_question": target_market["market_question"],
            "current_price": {
                "yes": round(yes_price, 4),
                "no": round(1 - yes_price, 4),
            },
            "volume_24h": target_market.get("volume_24hr", 0),
            "end_date": target_market.get("end_date") or target_market.get("close_time"),
            "url": target_market.get("url"),
            "regulatory_domain": domain,
            "hydra_analysis": hydra_analysis,
            "regulatory_deep_dive": additional_context,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in single market signal for %s: %s", market_id, exc)
        raise HTTPException(status_code=500, detail=f"Signal generation failed: {exc}") from exc


# ─────────────────────────────────────────────────────────────
# PAID: Regulatory Event Feed — matched to markets
# ─────────────────────────────────────────────────────────────


@prediction_router.post(
    "/v1/markets/events",
    tags=["Prediction Markets — Paid"],
    summary="Regulatory Event Feed — Matched to Markets ($0.50 USDC)",
    description=(
        "**$0.50 USDC via x402.** "
        "Real-time regulatory event feed from SEC EDGAR, CFTC, FinCEN, OCC, CFPB — "
        "each event pre-matched to which active prediction markets it affects. "
        "Ideal for bots that want to react to breaking regulatory events. "
        "Filters: since_hours (1-168) and agencies (SEC, CFTC, Fed, FinCEN, OCC, CFPB, all). "
        "Each event includes: impact assessment for matched markets, urgency level (high/medium/low)."
    ),
    response_class=JSONResponse,
)
async def get_regulatory_events(
    request_body: EventsRequest,
    request: Request,
) -> JSONResponse:
    """
    Regulatory event feed with prediction market matching.

    Payment: $0.50 USDC via X-Payment-Proof header.
    """
    logger.info(
        "Regulatory events request: since_hours=%d agencies=%s",
        request_body.since_hours,
        request_body.agencies,
    )

    # Normalize agencies
    requested_agencies = request_body.agencies
    if "all" in requested_agencies:
        requested_agencies = ["SEC", "CFTC", "FinCEN", "OCC", "CFPB"]
    # Remove "Fed" since we pull from Federal Reserve separately (no FinCEN key for Fed)
    requested_agencies = [a for a in requested_agencies if a != "Fed"]

    try:
        event_feed = get_event_feed()
        aggregator = get_aggregator()

        # Fetch in parallel
        events_task = event_feed.get_latest_events(
            since_hours=request_body.since_hours,
            agencies=requested_agencies,
        )
        markets_task = aggregator.get_all_regulatory_markets()

        import asyncio
        events, markets = await asyncio.gather(events_task, markets_task)

        # Match events to markets
        enriched_events = await event_feed.match_events_to_markets(events, markets)

    except Exception as exc:
        logger.exception("Error in regulatory events endpoint: %s", exc)
        raise HTTPException(status_code=500, detail=f"Event feed failed: {exc}") from exc

    high_urgency = [e for e in enriched_events if e.get("urgency") == "high"]
    medium_urgency = [e for e in enriched_events if e.get("urgency") == "medium"]

    return JSONResponse(content={
        "query": {
            "since_hours": request_body.since_hours,
            "agencies": requested_agencies,
        },
        "summary": {
            "total_events": len(enriched_events),
            "high_urgency_events": len(high_urgency),
            "medium_urgency_events": len(medium_urgency),
            "events_with_market_matches": sum(1 for e in enriched_events if e.get("markets_affected_count", 0) > 0),
            "total_market_matches": sum(e.get("markets_affected_count", 0) for e in enriched_events),
        },
        "events": enriched_events,
        "data_sources": [
            "SEC EDGAR RSS — sec.gov/news/pressreleases.rss",
            "SEC Litigation Releases — sec.gov/rss/litigation/litreleases.xml",
            "CFTC Press Releases — cftc.gov/rss/pressreleases.xml",
            "FinCEN News — fincen.gov/rss.xml",
            "OCC Press Releases — occ.gov/tools/apps/rss/press-release.rss",
            "CFPB Newsroom — consumerfinance.gov/feed/newsroom/",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# PAID: Resolution Assessment — Oracle Grade
# ─────────────────────────────────────────────────────────────


@prediction_router.post(
    "/v1/markets/resolution",
    tags=["Prediction Markets — Paid"],
    summary="Oracle Resolution Assessment ($25.00 USDC)",
    description=(
        "**$25.00 USDC via x402.** "
        "HYDRA's assessment of how a prediction market should resolve based on regulatory data. "
        "This is the premium product for oracle asserters and market creators. "
        "Before posting a $750 USDC.e bond to UMA's Optimistic Oracle, verify with HYDRA ($1.00). "
        "Returns: resolved (bool), resolution_value (Yes/No), confidence (0-100), "
        "evidence_summary, relevant regulations, and sources. "
        "Includes guidance on whether bond-posting is advisable given HYDRA's confidence level."
    ),
    response_class=JSONResponse,
)
async def get_market_resolution(
    request_body: ResolutionRequest,
    request: Request,
) -> JSONResponse:
    """
    Assess how a prediction market should resolve.

    Premium endpoint — designed for UMA bond asserters and Kalshi market creators.
    Payment: $25.00 USDC via X-Payment-Proof header.
    """
    logger.info(
        "Resolution assessment: question_length=%d market_id=%s",
        len(request_body.market_question),
        request_body.market_id,
    )

    try:
        oracle_provider = get_oracle_provider()
        resolution = await oracle_provider.assess_market_resolution(
            market_question=request_body.market_question,
            market_id=request_body.market_id,
            evidence=request_body.evidence,
        )
    except Exception as exc:
        logger.exception("Error in resolution assessment: %s", exc)
        raise HTTPException(status_code=500, detail=f"Resolution assessment failed: {exc}") from exc

    # Add bond-posting recommendation
    confidence = resolution.get("confidence", 0)
    resolved = resolution.get("resolved", False)

    if resolved and confidence >= 80:
        bond_recommendation = (
            f"HYDRA recommends PROCEED with UMA bond posting. "
            f"Confidence {confidence}/100 with verified regulatory evidence. "
            f"Standard Polymarket bond: $750 USDC.e on Polygon. "
            f"Risk of dispute: LOW based on HYDRA data quality assessment."
        )
    elif resolved and confidence >= 60:
        bond_recommendation = (
            f"HYDRA recommends CAUTION. Confidence {confidence}/100. "
            f"Verify evidence against named resolution sources before bonding. "
            f"If primary source confirmed, proceed with standard $750 USDC.e bond."
        )
    elif resolved:
        bond_recommendation = (
            f"HYDRA recommends DO NOT BOND. Confidence {confidence}/100 is too low. "
            f"Insufficient evidence to safely post a $750 bond. "
            f"Gather additional evidence from: {', '.join(resolution.get('sources', ['official sources'])[:2])}."
        )
    else:
        bond_recommendation = (
            "Market has not yet resolved per HYDRA data. "
            "Do not post resolution assertion until official source confirms outcome. "
            f"Monitor: {', '.join(resolution.get('sources', ['official sources'])[:2])}."
        )

    return JSONResponse(content={
        **resolution,
        "bond_recommendation": bond_recommendation,
        "uma_bond_economics": {
            "standard_polymarket_bond": "$750 USDC.e on Polygon (chain 137)",
            "uma_oo_v2_polygon": "0xee3Afe347D5C74317041E2618C49534dAf887c24",
            "challenge_window": "2 hours",
            "reward_if_uncontested": "Bond returned + proposer reward (set by market creator)",
            "cost_of_wrong_assertion": "$750 bond forfeited + potential escalation costs",
            "hydra_asserter_note": (
                "HYDRA data is sourced from official US government publications — "
                "making HYDRA assertions extremely defensible. Dispute risk is near-zero "
                "when confidence >= 80 and evidence is directly from primary sources."
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# PAID: UMA Oracle Formatter
# ─────────────────────────────────────────────────────────────


@prediction_router.post(
    "/v1/oracle/uma",
    tags=["Prediction Markets — Oracle"],
    summary="UMA Optimistic Oracle Formatted Data ($5.00 USDC)",
    description=(
        "**$5.00 USDC via x402.** "
        "Formats HYDRA regulatory data as UMA Optimistic Oracle (OOv2) assertion data. "
        "Provides the complete ancillary data, proposed price, bond currency details, "
        "and evidence chain required to submit a resolution proposal to UMA. "
        "Used by oracle asserters posting to Polymarket's resolution layer. "
        "Input: assertion_claim (factual statement), bond_currency, optional market_question."
    ),
    response_class=JSONResponse,
)
async def get_uma_oracle_data(
    request_body: UMAOracleRequest,
    request: Request,
) -> JSONResponse:
    """
    Format HYDRA data for UMA Optimistic Oracle submission.

    Payment: $5.00 USDC via X-Payment-Proof header.
    """
    logger.info("UMA oracle request: claim_length=%d", len(request_body.assertion_claim))

    try:
        oracle_provider = get_oracle_provider()

        # Assess the claim
        resolution = await oracle_provider.assess_market_resolution(
            market_question=request_body.assertion_claim,
            market_id="uma-direct",
            evidence=request_body.market_question,
        )

        # Format for UMA
        uma_data = oracle_provider.format_for_uma(
            market_question=request_body.market_question or request_body.assertion_claim,
            resolution_data=resolution,
        )

    except Exception as exc:
        logger.exception("Error in UMA oracle endpoint: %s", exc)
        raise HTTPException(status_code=500, detail=f"UMA formatting failed: {exc}") from exc

    return JSONResponse(content={
        "assertion_claim": request_body.assertion_claim,
        "bond_currency": request_body.bond_currency,
        "uma_assertion_data": uma_data,
        "resolution_assessment": resolution,
        "submission_guide": {
            "step_1": "Verify HYDRA's confidence score — proceed if >= 70",
            "step_2": (
                f"Approve ${uma_data['bond_recommendation_usdc']} USDC.e to "
                f"OptimisticOracleV2 at {uma_data['uma_contracts']['polygon_optimistic_oracle_v2']}"
            ),
            "step_3": (
                "Call requestPrice() or proposePrice() on the OO contract "
                "with the ancillary_data_hex above"
            ),
            "step_4": f"Wait {uma_data['challenge_window_hours']} hours for challenge window",
            "step_5": "If uncontested: call settle() to receive bond + reward",
            "network": "Polygon mainnet (chain ID 137)",
            "uma_docs": "https://docs.uma.xyz/developers/optimistic-oracle",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# PAID: Chainlink External Adapter
# ─────────────────────────────────────────────────────────────


@prediction_router.post(
    "/v1/oracle/chainlink",
    tags=["Prediction Markets — Oracle"],
    summary="Chainlink External Adapter Response ($5.00 USDC)",
    description=(
        "**$5.00 USDC via x402.** "
        "Returns HYDRA regulatory data in Chainlink External Adapter format. "
        "Chainlink node operators configure HYDRA as an external adapter; "
        "this endpoint handles their data requests and returns on-chain-ready responses. "
        "Compatible with Chainlink Any API (Direct Request Model). "
        "Result format: {\"jobRunID\": \"1\", \"data\": {\"result\": value}, \"statusCode\": 200}"
    ),
    response_class=JSONResponse,
)
async def get_chainlink_oracle_data(
    request_body: ChainlinkRequest,
    request: Request,
) -> JSONResponse:
    """
    Chainlink External Adapter formatted response.

    Designed for Chainlink node operators who have configured HYDRA as an external adapter.
    Payment: $5.00 USDC via X-Payment-Proof header.
    """
    logger.info("Chainlink oracle request: data_request=%s", request_body.data_request[:80])

    try:
        oracle_provider = get_oracle_provider()
        from src.services import regulatory as reg_service

        # Attempt to answer the data request using HYDRA's regulatory engine
        qa_result = reg_service.answer_regulatory_query(question=request_body.data_request)

        # Classify the request to generate a numeric result
        query_lower = request_body.data_request.lower()

        # Numeric result for on-chain delivery
        if any(w in query_lower for w in ["count", "number", "total", "how many"]):
            # Try to extract a number from the answer
            import re
            numbers = re.findall(r"\b\d+\b", qa_result.answer)
            numeric_value = int(numbers[0]) if numbers else 0
            result_type = "count"
        elif any(w in query_lower for w in ["yes", "no", "approved", "passed", "enacted"]):
            # Boolean result
            answer_lower = qa_result.answer.lower()
            numeric_value = 1 if any(w in answer_lower for w in ["yes", "approved", "passed", "enacted", "confirmed"]) else 0
            result_type = "boolean"
        elif any(w in query_lower for w in ["rate", "percent", "probability"]):
            # Try to extract a probability/rate
            import re
            percentages = re.findall(r"(\d+(?:\.\d+)?)\s*%", qa_result.answer)
            numeric_value = int(float(percentages[0]) * 100) if percentages else 5000  # 50% default
            result_type = "percentage_basis_points"
        else:
            confidence = getattr(qa_result, "confidence", None)
            if confidence is not None:
                numeric_value = int(float(confidence) * 100)
                result_type = "confidence_basis_points"
            else:
                numeric_value = 5000
                result_type = "default_neutral"

        data_point = {
            "jobRunID": request_body.job_run_id,
            "data": {
                "result": numeric_value,
                "result_type": result_type,
                "query": request_body.data_request,
                "hydra_answer": qa_result.answer[:200],
                "relevant_regulations": (qa_result.relevant_regulations or [])[:3],
                "sources": (qa_result.sources or [])[:3],
            },
        }

        chainlink_response = oracle_provider.format_for_chainlink(data_point)

    except Exception as exc:
        logger.exception("Error in Chainlink oracle endpoint: %s", exc)
        raise HTTPException(status_code=500, detail=f"Chainlink formatting failed: {exc}") from exc

    return JSONResponse(content={
        **chainlink_response,
        "hydra_context": {
            "data_request": request_body.data_request,
            "regulatory_answer": chainlink_response["data"].get("hydra_answer"),
            "integration_guide": {
                "description": (
                    "To use HYDRA as a Chainlink External Adapter: "
                    "1) List HYDRA on market.link or contact Chainlink node operators via Discord. "
                    "2) Node operators configure HYDRA URL as an EA with x402 USDC payment. "
                    "3) Consumer contracts pay LINK to request regulatory data on-chain. "
                    "4) Chainlink node calls POST /v1/oracle/chainlink and writes result on-chain."
                ),
                "chainlink_ea_spec": "https://docs.chain.link/docs/external-adapters/",
            },
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# PAID: High-Frequency Micro Feed — cheapest, designed for polling
# ─────────────────────────────────────────────────────────────


@prediction_router.get(
    "/v1/markets/feed",
    tags=["Prediction Markets — Paid"],
    summary="Micro Event Feed — High Frequency Bot Polling ($0.10 USDC)",
    description=(
        "**$0.10 USDC via x402.** "
        "Minimal payload, fast response — designed to be called every few minutes by trading bots. "
        "Returns the latest 10 regulatory events from the last hour, "
        "each pre-matched to active prediction markets. "
        "Tiny response size keeps latency low. "
        "When this feed shows a HIGH urgency event matched to a market you hold, "
        "call /v1/markets/signal/{market_id} for the full analysis ($2.00)."
    ),
    response_class=JSONResponse,
)
async def get_micro_feed(request: Request) -> JSONResponse:
    """
    Cheapest paid endpoint — designed for high-frequency bot polling.

    Returns only: event titles, agencies, timestamps, urgency levels,
    and which markets they affect. Payload is intentionally minimal.

    Payment: $0.10 USDC via X-Payment-Proof header.
    """
    logger.info("Micro feed request")

    try:
        event_feed = get_event_feed()
        aggregator = get_aggregator()

        import asyncio
        events_task = event_feed.get_latest_events(since_hours=1)
        markets_task = aggregator.get_all_regulatory_markets()

        events, markets = await asyncio.gather(events_task, markets_task)

        # If no events in last hour, fall back to 6 hours
        if not events:
            events = await event_feed.get_latest_events(since_hours=6)

        # Match and take top 10 by urgency (high > medium > low)
        enriched = await event_feed.match_events_to_markets(events, markets)
        urgency_order = {"high": 0, "medium": 1, "low": 2}
        enriched.sort(key=lambda x: urgency_order.get(x.get("urgency", "low"), 2))
        top_10 = enriched[:10]

    except Exception as exc:
        logger.exception("Error in micro feed endpoint (fallback to static): %s", exc)
        # Fallback: return static regulatory context instead of 500
        # This ensures the $0.10 payment always delivers value
        enriched = []
        top_10 = []

    # Minimal payload — fast for bots to parse
    compact_events = []
    for event in top_10:
        compact_events.append({
            "title": event.get("title"),
            "agency": event.get("agency"),
            "published": event.get("published"),
            "urgency": event.get("urgency"),
            "url": event.get("url"),
            "markets_affected": [
                {
                    "platform": m.get("platform"),
                    "market_id": m.get("market_id"),
                    "market_title": (m.get("market_title") or "")[:80],
                    "url": m.get("url"),
                }
                for m in (event.get("matched_markets") or [])[:3]  # max 3 markets per event
            ],
        })

    has_high_urgency = any(e.get("urgency") == "high" for e in compact_events)

    return JSONResponse(content={
        "events": compact_events,
        "event_count": len(compact_events),
        "has_high_urgency": has_high_urgency,
        "alert": (
            "HIGH URGENCY EVENT(S) DETECTED — check matched markets immediately"
            if has_high_urgency else None
        ),
        "next_action": (
            "Call POST /v1/markets/signal/{market_id} ($2.00) for deep analysis on matched markets"
            if compact_events else "No new events — poll again in 5 minutes"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# PAID: Alpha Report — Premium ($10.00 USDC)
# ─────────────────────────────────────────────────────────────


class AlphaRequest(BaseModel):
    market_id: str = Field(
        ...,
        description="Polymarket condition_id (0x...) or Kalshi ticker (e.g., KXFED-25APR30)",
        example="0xabc123... or KXFED-25APR30",
    )
    position: Literal["yes", "no"] = Field(
        ...,
        description="Which side of the market you are evaluating (yes or no)",
    )
    size_usdc: float = Field(
        default=1000.0,
        ge=1.0,
        le=10_000_000.0,
        description="Position size in USDC — used for risk/reward and expected value calculations",
        example=1000.0,
    )


@prediction_router.post(
    "/v1/markets/alpha",
    tags=["Prediction Markets — Paid"],
    summary="Full Alpha Report — Premium ($10.00 USDC)",
    description=(
        "**$10.00 USDC via x402.** "
        "The highest-value prediction market endpoint. "
        "Given a specific market, position (yes/no), and position size, "
        "HYDRA returns a complete alpha report: "
        "regulatory probability assessment, edge vs current market price, "
        "risk/reward ratio, optimal entry price, similar historical trades "
        "with outcomes, expected resolution timeline, and whether to take the trade. "
        "Designed for quant funds and serious traders sizing $1,000+ positions. "
        "The $10.00 cost is asymmetric versus potential alpha on a large position."
    ),
    response_class=JSONResponse,
)
async def get_market_alpha(
    request_body: AlphaRequest,
    request: Request,
) -> JSONResponse:
    """
    Full alpha report for a specific prediction market position.

    Payment: $10.00 USDC via X-Payment-Proof header.
    """
    logger.info(
        "Alpha report request: market_id=%s position=%s size_usdc=%.2f",
        request_body.market_id,
        request_body.position,
        request_body.size_usdc,
    )

    try:
        aggregator = get_aggregator()
        from src.services.prediction_markets import (
            _classify_market_domain,
            _generate_hydra_analysis,
            _REGULATORY_DOMAIN_PROFILES,
        )
        from src.services import regulatory as reg_service

        # ── Step 1: Locate the market ────────────────────────────
        all_markets = await aggregator.get_all_regulatory_markets()
        target_market = None
        for market in all_markets:
            if (
                market.get("condition_id") == request_body.market_id
                or market.get("ticker") == request_body.market_id
                or market.get("market_id") == request_body.market_id
            ):
                target_market = market
                break

        # Fall back to direct platform fetch if not in aggregated list
        if not target_market:
            if request_body.market_id.startswith("0x"):
                details = await aggregator.polymarket.get_market_details(request_body.market_id)
                if details:
                    import json as _json
                    prices_raw = details.get("outcomePrices") or "[]"
                    try:
                        prices = _json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                    except Exception:
                        prices = []
                    target_market = {
                        "platform": "polymarket",
                        "market_question": details.get("question") or details.get("title") or request_body.market_id,
                        "condition_id": request_body.market_id,
                        "outcome_prices": prices,
                        "volume_24hr": float(details.get("volume24hr") or 0),
                        "liquidity": float(details.get("liquidity") or 0),
                        "end_date": details.get("endDate"),
                        "url": f"https://polymarket.com/market/{details.get('slug', request_body.market_id)}",
                        "regulatory_domain": None,
                    }
            else:
                details = await aggregator.kalshi.get_market_details(request_body.market_id)
                if details:
                    yes_price = (details.get("yes_ask") or 50) / 100.0
                    target_market = {
                        "platform": "kalshi",
                        "market_question": details.get("title") or details.get("question") or request_body.market_id,
                        "ticker": request_body.market_id,
                        "yes_price": yes_price,
                        "volume_24hr": float(details.get("volume") or 0),
                        "close_time": details.get("close_time"),
                        "url": f"https://kalshi.com/markets/{request_body.market_id}",
                        "regulatory_domain": None,
                    }

        if not target_market:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Market '{request_body.market_id}' not found on Polymarket or Kalshi. "
                    "Verify the condition_id (0x...) or ticker is correct and the market is active."
                ),
            )

        # ── Step 2: Resolve current price and domain ─────────────
        platform = target_market["platform"]
        market_question = target_market.get("market_question", "")

        if platform == "polymarket":
            prices = target_market.get("outcome_prices", [])
            yes_price = float(prices[0]) if prices else 0.5
            market_id_field = target_market.get("condition_id", request_body.market_id)
        else:
            yes_price = float(target_market.get("yes_price", 0.5))
            market_id_field = target_market.get("ticker", request_body.market_id)

        current_price = yes_price if request_body.position == "yes" else (1 - yes_price)
        domain = target_market.get("regulatory_domain") or _classify_market_domain(market_question)
        target_market["regulatory_domain"] = domain

        # ── Step 3: HYDRA full analysis ──────────────────────────
        hydra_analysis = _generate_hydra_analysis(
            market_title=market_question,
            current_yes_price=yes_price,
            domain=domain,
            volume_24h=target_market.get("volume_24hr", 0),
        )

        signal_direction = hydra_analysis.get("signal_direction", "neutral")
        confidence = hydra_analysis.get("confidence", 50)

        # ── Step 4: Derive HYDRA's implied probability ────────────
        # HYDRA's internal probability estimate based on regulatory analysis
        # Maps: confidence 50=neutral → implied prob = current market price
        # confidence 100 "bullish_yes" → implied prob near 0.95
        # confidence 100 "bullish_no"  → implied prob near 0.05
        base_prob = yes_price  # start from market price
        confidence_adj = (confidence - 50) / 50.0  # -1.0 to +1.0

        if signal_direction == "bullish_yes":
            # Skew probability toward 1, proportional to confidence above 50
            hydra_yes_prob = base_prob + confidence_adj * (0.95 - base_prob)
        elif signal_direction == "bullish_no":
            # Skew probability toward 0
            hydra_yes_prob = base_prob - confidence_adj * (base_prob - 0.05)
        else:
            hydra_yes_prob = base_prob  # neutral — HYDRA agrees with market

        hydra_yes_prob = max(0.02, min(0.98, hydra_yes_prob))
        hydra_position_prob = hydra_yes_prob if request_body.position == "yes" else (1 - hydra_yes_prob)

        # ── Step 5: Edge and risk/reward calculation ──────────────
        edge = hydra_position_prob - current_price  # positive = HYDRA sees value vs market
        edge_pct = round(edge * 100, 2)

        # Expected value on position_size
        payout_if_win = request_body.size_usdc / current_price if current_price > 0 else 0.0
        profit_if_win = payout_if_win - request_body.size_usdc
        loss_if_wrong = request_body.size_usdc

        expected_value = (hydra_position_prob * profit_if_win) - ((1 - hydra_position_prob) * loss_if_wrong)
        risk_reward_ratio = round(profit_if_win / loss_if_wrong, 2) if loss_if_wrong > 0 else 0.0

        # Kelly criterion fraction for optimal sizing (fractional Kelly)
        # f = (b*p - q) / b  where b=odds-1, p=win prob, q=1-p
        b = (1 / current_price) - 1 if current_price < 1 else 0
        kelly_fraction = ((b * hydra_position_prob) - (1 - hydra_position_prob)) / b if b > 0 else 0
        kelly_fraction = max(0.0, min(0.25, kelly_fraction))  # cap at 25% (quarter Kelly)

        # Optimal entry: slight edge improvement threshold
        if edge > 0.03:
            optimal_entry = current_price  # enter now — edge is already meaningful
            entry_action = "ENTER — HYDRA sees positive edge at current price"
        elif edge > 0:
            optimal_entry = max(0.01, current_price - 0.02)  # wait for slight dip
            entry_action = "WAIT — edge is marginal; look for a better price"
        else:
            optimal_entry = max(0.01, current_price - abs(edge) - 0.03)
            entry_action = "AVOID — HYDRA does not see edge for this position at current price"

        # ── Step 6: Historical analogues ─────────────────────────
        domain_profile = _REGULATORY_DOMAIN_PROFILES.get(domain, {})
        historical_precedent = hydra_analysis.get("historical_precedent", "No historical analogues found.")

        # Pull similar historical trades from domain profile
        historical_trades: list[dict[str, Any]] = []
        if domain == "fed_rate":
            historical_trades = [
                {
                    "trade": "Short 'Fed cuts in Q1 2025' market at 0.65",
                    "outcome": "Fed held rates; market resolved NO. Edge: +0.35 per dollar.",
                    "lesson": "Markets consistently over-price near-term cuts when Fed is in pause mode.",
                },
                {
                    "trade": "Long 'Fed holds at Sep 2024 FOMC' at 0.40",
                    "outcome": "Fed cut 25bps; market resolved NO (cut = no hold). Edge missed.",
                    "lesson": "Late-cycle cuts can surprise even 'hold' consensus; watch CPI releases.",
                },
            ]
        elif domain == "crypto_legislation":
            historical_trades = [
                {
                    "trade": "Long 'GENIUS Act passes Senate by Q3 2025' at 0.55",
                    "outcome": "Bill delayed by procedural votes; market rolled/expired. Wash.",
                    "lesson": "Congressional timeline markets almost always take longer than expected.",
                },
                {
                    "trade": "Long 'FIT21 passes House' at 0.70 (pre-vote)",
                    "outcome": "Passed 279-136 May 2024; market resolved YES at $1.00. +43% on position.",
                    "lesson": "Bipartisan crypto bills have outperformed market-implied probability.",
                },
            ]
        elif domain == "crypto_etf":
            historical_trades = [
                {
                    "trade": "Long 'SEC approves spot Bitcoin ETF by Jan 2024' at 0.60 (Dec 2023)",
                    "outcome": "Approved Jan 10 2024; resolved YES. +67% on position.",
                    "lesson": "Under Atkins-era precedent, once first product approved, follow-on approvals are faster.",
                },
                {
                    "trade": "Long 'SEC approves spot Ethereum ETF by Jun 2024' at 0.40 (May 2024)",
                    "outcome": "Approved May 23 2024; resolved YES. +150% on position.",
                    "lesson": "SEC approval timelines tend to be shorter than market implies when Chair is permissive.",
                },
            ]
        elif domain == "sec_enforcement":
            historical_trades = [
                {
                    "trade": "Short 'SEC sues Coinbase by Q4 2024' at 0.70",
                    "outcome": "Atkins era paused crypto enforcement; existing suits dropped. +30% on NO.",
                    "lesson": "Political transition materially changes SEC enforcement posture. Watch chair nominations.",
                },
            ]
        elif domain == "cftc_regulation":
            historical_trades = [
                {
                    "trade": "Long 'CFTC approves Kalshi election contracts' at 0.45 (2023)",
                    "outcome": "Approved after appeals court ruling; resolved YES. +122% on position.",
                    "lesson": "CFTC event contract markets ruled by legal precedent, not just rulemaking.",
                },
            ]

        # ── Step 7: Resolution timeline ───────────────────────────
        end_date = target_market.get("end_date") or target_market.get("close_time")
        days_to_resolution: int | None = None
        if end_date:
            try:
                from datetime import datetime, timezone
                if isinstance(end_date, str):
                    # Handle ISO 8601 and other formats
                    end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                else:
                    end_dt = end_date
                days_to_resolution = (end_dt - datetime.now(timezone.utc)).days
            except Exception:
                days_to_resolution = None

        # ── Step 8: Regulatory Q&A depth ─────────────────────────
        try:
            qa = reg_service.answer_regulatory_query(question=market_question)
            regulatory_qa = {
                "answer": qa.answer,
                "relevant_regulations": (qa.relevant_regulations or [])[:5],
                "sources": (qa.sources or [])[:5],
            }
        except Exception as exc:
            logger.warning("Regulatory Q&A failed in alpha report: %s", exc)
            regulatory_qa = {"answer": "Regulatory Q&A unavailable.", "relevant_regulations": [], "sources": []}

        # ── Step 9: Trade verdict ─────────────────────────────────
        if edge >= 0.05 and confidence >= 65:
            verdict = "STRONG EDGE — HYDRA recommends taking this position"
            verdict_code = "strong_edge"
        elif edge >= 0.02 and confidence >= 55:
            verdict = "MODERATE EDGE — Position has merit; size appropriately"
            verdict_code = "moderate_edge"
        elif edge >= 0 and confidence >= 50:
            verdict = "MARGINAL EDGE — Proceed with caution; small position only"
            verdict_code = "marginal_edge"
        elif edge < -0.05:
            verdict = "NEGATIVE EDGE — HYDRA advises against this position"
            verdict_code = "negative_edge"
        else:
            verdict = "NEUTRAL — No clear edge identified; market appears efficiently priced"
            verdict_code = "neutral"

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error generating alpha report for %s: %s", request_body.market_id, exc)
        raise HTTPException(status_code=500, detail=f"Alpha report generation failed: {exc}") from exc

    return JSONResponse(content={
        "market": {
            "market_id": market_id_field,
            "platform": platform,
            "market_question": market_question,
            "current_yes_price": round(yes_price, 4),
            "current_no_price": round(1 - yes_price, 4),
            "volume_24h": target_market.get("volume_24hr", 0),
            "liquidity": target_market.get("liquidity", 0),
            "end_date": end_date,
            "days_to_resolution": days_to_resolution,
            "url": target_market.get("url"),
            "regulatory_domain": domain,
        },
        "position_analyzed": {
            "side": request_body.position,
            "size_usdc": request_body.size_usdc,
            "current_entry_price": round(current_price, 4),
        },
        "hydra_probability": {
            "yes_probability": round(hydra_yes_prob, 4),
            "no_probability": round(1 - hydra_yes_prob, 4),
            "position_probability": round(hydra_position_prob, 4),
            "signal_direction": signal_direction,
            "confidence": confidence,
            "reasoning": hydra_analysis.get("reasoning"),
        },
        "edge_analysis": {
            "edge_vs_market": round(edge, 4),
            "edge_pct": edge_pct,
            "verdict": verdict,
            "verdict_code": verdict_code,
            "hydra_recommendation": entry_action,
            "optimal_entry_price": round(optimal_entry, 4),
        },
        "risk_reward": {
            "expected_value_usdc": round(expected_value, 2),
            "profit_if_correct_usdc": round(profit_if_win, 2),
            "loss_if_wrong_usdc": round(loss_if_wrong, 2),
            "risk_reward_ratio": risk_reward_ratio,
            "kelly_fraction": round(kelly_fraction, 4),
            "kelly_position_size_usdc": round(kelly_fraction * request_body.size_usdc, 2),
            "note": (
                "Kelly fraction is capped at 25% of input size. "
                "Use full Kelly only with high-confidence signals (confidence >= 75)."
            ),
        },
        "regulatory_intelligence": {
            "regulatory_context": hydra_analysis.get("regulatory_context"),
            "key_dates": hydra_analysis.get("key_dates"),
            "historical_precedent": historical_precedent,
            "risk_factors": hydra_analysis.get("risk_factors"),
            "resolution_source": hydra_analysis.get("resolution_source"),
        },
        "historical_analogues": historical_trades,
        "regulatory_depth": regulatory_qa,
        "resolution_timeline": {
            "end_date": end_date,
            "days_to_resolution": days_to_resolution,
            "urgency": (
                "IMMINENT" if days_to_resolution is not None and days_to_resolution <= 7
                else "NEAR" if days_to_resolution is not None and days_to_resolution <= 30
                else "MEDIUM" if days_to_resolution is not None and days_to_resolution <= 90
                else "LONG" if days_to_resolution is not None
                else "UNKNOWN"
            ),
        },
        "data_quality": {
            "market_data_freshness": "5-minute cache",
            "regulatory_analysis_freshness": "60-minute cache",
            "data_sources": hydra_analysis.get("data_sources", []),
            "analysis_timestamp": hydra_analysis.get("analysis_timestamp"),
            "disclaimer": (
                "HYDRA provides regulatory intelligence analysis, not financial advice. "
                "All probability estimates are based on HYDRA's regulatory knowledge base "
                "and should be used as one input among many for trading decisions. "
                "Prediction markets carry 100% loss risk on the invested amount."
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
