"""
HYDRA Fed Decision Package
===========================
Dedicated endpoints for Federal Reserve / FOMC intelligence.
The Fed decision market averages $80M+ volume per meeting with 41,000+ unique wallets.
This is HYDRA's highest-value recurring revenue category.

Endpoints:
  POST /v1/fed/signal     — $5.00 USDC  Pre-FOMC signal
  POST /v1/fed/decision   — $25.00 USDC Real-time FOMC decision classification
  POST /v1/fed/resolution — $50.00 USDC Resolution verdict for prediction markets

All endpoints are protected by X402PaymentMiddleware — payment is verified before
these handlers are invoked. USDC on Base, chain ID 8453.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.services.fed_intelligence import FedIntelligenceEngine

logger = logging.getLogger(__name__)

# Single shared engine instance (stateless — safe to share)
_engine = FedIntelligenceEngine()

fed_router = APIRouter(tags=["Fed Decision Package"])


# ─────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────


class FedSignalRequest(BaseModel):
    """Request body for /v1/fed/signal. All fields optional — engine uses current data."""

    include_speech_analysis: bool = Field(
        default=True,
        description="Include analysis of recent Fed governor speeches.",
    )
    include_indicators: bool = Field(
        default=True,
        description="Include detailed economic indicator breakdowns.",
    )


class FedDecisionRequest(BaseModel):
    """
    Request body for /v1/fed/decision.

    On FOMC days, the engine attempts to fetch live data from federalreserve.gov.
    On non-FOMC days, the most recent known decision is returned.
    """

    include_market_impact: bool = Field(
        default=True,
        description="Include expected impact assessment on prediction markets.",
    )


class FedResolutionRequest(BaseModel):
    """Request body for /v1/fed/resolution."""

    market_question: str = Field(
        default="Will the Federal Reserve hold interest rates at the next FOMC meeting?",
        description=(
            "Natural-language prediction market question to resolve. "
            "Example: 'Will the Fed cut rates by 25 bp at the May 2026 FOMC meeting?'"
        ),
        min_length=10,
        max_length=500,
    )
    include_uma_data: bool = Field(
        default=True,
        description="Include UMA Optimistic Oracle formatted assertion data.",
    )
    include_kalshi_format: bool = Field(
        default=True,
        description="Include Kalshi KXFED series resolution format.",
    )
    include_polymarket_format: bool = Field(
        default=True,
        description="Include Polymarket FOMC market resolution format.",
    )


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@fed_router.post(
    "/v1/fed/signal",
    summary="Pre-FOMC Signal ($5.00 USDC)",
    description=(
        "Pre-FOMC analysis signal — rate probability model, speech tone analysis, "
        "dot plot tracking, and key economic indicators. "
        "**Requires x402 payment of $5.00 USDC on Base.**"
    ),
    response_class=JSONResponse,
)
async def fed_signal(
    request_body: FedSignalRequest,
    request: Request,
) -> JSONResponse:
    """
    Generate a pre-FOMC intelligence signal.

    Combines:
    - Rule-based rate probability model (HOLD / CUT / HIKE with basis point estimate)
    - Recent Fed governor speech analysis and overall tone
    - Key economic indicators (CPI, core PCE, unemployment, GDP, payrolls)
    - Dot plot median projection
    - Market consensus estimate
    - HYDRA signal direction and confidence score

    Payment: $5.00 USDC via X-Payment-Proof header.
    """
    logger.info(
        "Fed signal request: include_speech=%s include_indicators=%s",
        request_body.include_speech_analysis,
        request_body.include_indicators,
    )

    try:
        # Refresh engine with live data before generating signal
        try:
            live_status = await _engine.refresh_from_live_data()
            logger.info("Live data refresh: %s", live_status)
        except Exception as live_exc:
            logger.debug("Live data refresh skipped: %s", live_exc)

        signal = _engine.generate_pre_fomc_signal()

        # ── Also attach raw live data for transparency ──
        try:
            from src.services.live_data import fetch_fed_funds_rate, fetch_latest_fed_statement
            live_rate = await fetch_fed_funds_rate()
            live_statement = await fetch_latest_fed_statement()
            if live_rate:
                signal["live_fed_funds_rate"] = live_rate
            if live_statement:
                signal["latest_fed_statement"] = {
                    "title": live_statement.get("title", ""),
                    "published": live_statement.get("published", ""),
                    "link": live_statement.get("link", ""),
                    "is_live": True,
                }
        except Exception as live_exc:
            logger.debug("Live data enrichment skipped: %s", live_exc)

        # Optionally strip verbose fields if caller doesn't want them
        if not request_body.include_speech_analysis:
            signal.pop("fed_speech_analysis", None)
        if not request_body.include_indicators:
            signal.pop("key_indicators", None)

        return JSONResponse(
            status_code=200,
            content={
                "endpoint": "/v1/fed/signal",
                "price_paid_usdc": "5.00",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                **signal,
            },
        )

    except Exception as exc:
        logger.exception("Error generating Fed signal: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Fed signal generation failed: {exc}",
        ) from exc


@fed_router.post(
    "/v1/fed/decision",
    summary="FOMC Decision Classification ($25.00 USDC)",
    description=(
        "Real-time FOMC decision endpoint. On FOMC announcement days, attempts to fetch "
        "the live statement from federalreserve.gov and classify the decision within "
        "30 seconds of release. On non-FOMC days, returns the most recent known decision "
        "with a note. Includes vote breakdown, statement summary, dot plot shift, "
        "and market impact assessment. "
        "**Requires x402 payment of $25.00 USDC on Base.**"
    ),
    response_class=JSONResponse,
)
async def fed_decision(
    request_body: FedDecisionRequest,
    request: Request,
) -> JSONResponse:
    """
    Classify an FOMC rate decision.

    On FOMC announcement days (Jan 29, Mar 19, May 7, Jun 18, Jul 30,
    Sep 17, Oct 29, Dec 10, 2026): attempts live data from Federal Reserve.

    On all other days: returns the most recent known decision.

    Includes cryptographic timestamp for auditability.

    Payment: $25.00 USDC via X-Payment-Proof header.
    """
    logger.info(
        "Fed decision request: include_market_impact=%s",
        request_body.include_market_impact,
    )

    try:
        try:
            await _engine.refresh_from_live_data()
        except Exception:
            pass

        is_fomc_day = _engine.is_fomc_day()
        decision_data = _engine.get_latest_decision()
        probs = _engine.calculate_rate_probabilities()

        # Market impact assessment
        market_impact: dict[str, Any] = {}
        if request_body.include_market_impact:
            decision_outcome = decision_data.get("decision", "HOLD")
            dominant_prob = probs.get("hold", 0.8)

            if decision_outcome == "HOLD" and dominant_prob >= 0.75:
                impact_label = "Low volatility expected — decision in line with consensus"
                impact_detail = (
                    "A HOLD decision at this meeting is broadly anticipated by prediction markets. "
                    "Kalshi KXFED HOLD contracts should resolve YES. Polymarket FOMC markets "
                    "priced for hold should settle at ~$1.00. Limited price movement expected "
                    "unless statement language signals a hawkish or dovish shift."
                )
            elif decision_outcome == "CUT":
                impact_label = "Moderate-to-high volatility — cut may be partially priced in"
                impact_detail = (
                    f"A {decision_data.get('basis_points', 25)} bp cut resolves CUT-side contracts YES. "
                    "Rate-sensitive prediction markets (KXFED CUT, Polymarket 'Fed cuts in 2026') "
                    "should rally. Treasury markets expected to respond within minutes."
                )
            else:
                impact_label = "Assess market-specific pricing"
                impact_detail = (
                    "Decision classification confirmed. Check individual market pricing to "
                    "determine resolution direction for specific prediction market positions."
                )

            market_impact = {
                "impact_label": impact_label,
                "impact_detail": impact_detail,
                "kalshi_note": "KXFED series resolves based on official Fed announcement.",
                "polymarket_note": "Polymarket FOMC markets typically resolve within 30 minutes.",
                "uma_note": "For UMA asserters: use /v1/fed/resolution to get formatted assertion data.",
            }

        cryptographic_timestamp = _engine._generate_decision_timestamp()

        return JSONResponse(
            status_code=200,
            content={
                "endpoint": "/v1/fed/decision",
                "price_paid_usdc": "25.00",
                "is_fomc_day": is_fomc_day,
                "decision": decision_data.get("decision"),
                "basis_points": decision_data.get("basis_points"),
                "new_rate_range": decision_data.get("new_rate_range"),
                "previous_rate_range": decision_data.get("previous_rate_range"),
                "vote_breakdown": decision_data.get("vote_breakdown"),
                "statement_summary": decision_data.get("statement_summary"),
                "dot_plot_shift": decision_data.get("dot_plot_shift"),
                "market_impact_assessment": market_impact if request_body.include_market_impact else None,
                "timestamp": cryptographic_timestamp,
                "source": decision_data.get("source"),
                "source_url": decision_data.get("source_url"),
                "is_live": decision_data.get("is_live", False),
                "note": decision_data.get("note"),
                "meeting_dates": decision_data.get("meeting_dates"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as exc:
        logger.exception("Error generating Fed decision: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Fed decision classification failed: {exc}",
        ) from exc


@fed_router.post(
    "/v1/fed/resolution",
    summary="FOMC Resolution Verdict ($50.00 USDC)",
    description=(
        "Resolution verdict for FOMC prediction markets. Returns all FOMC decision data "
        "plus UMA Optimistic Oracle assertion data, Kalshi KXFED resolution format, "
        "Polymarket resolution format, and a full evidence chain with source URLs and timestamps. "
        "Designed for UMA bond asserters, Kalshi resolvers, and automated oracle systems. "
        "**Requires x402 payment of $50.00 USDC on Base.**"
    ),
    response_class=JSONResponse,
)
async def fed_resolution(
    request_body: FedResolutionRequest,
    request: Request,
) -> JSONResponse:
    """
    Generate a complete FOMC market resolution verdict.

    Includes:
    - Full FOMC decision data (same as /v1/fed/decision)
    - Resolution verdict with confidence score and evidence narrative
    - UMA Optimistic Oracle assertion data (ancillary_data, proposed_price, bond_amount)
    - Kalshi KXFED resolution format
    - Polymarket FOMC market resolution format
    - Evidence chain: list of sources with URLs and timestamps

    For UMA bond asserters: this endpoint determines whether posting a $750 USDC bond
    is safe and provides the exact assertion parameters to submit.

    Payment: $50.00 USDC via X-Payment-Proof header.
    """
    logger.info(
        "Fed resolution request: market_question=%r include_uma=%s include_kalshi=%s include_poly=%s",
        request_body.market_question[:80],
        request_body.include_uma_data,
        request_body.include_kalshi_format,
        request_body.include_polymarket_format,
    )

    try:
        # Refresh engine with live data before generating verdict
        try:
            await _engine.refresh_from_live_data()
        except Exception:
            pass

        verdict_data = _engine.generate_resolution_verdict(
            market_question=request_body.market_question
        )

        # Selectively include oracle format sections
        response_payload: dict[str, Any] = {
            "endpoint": "/v1/fed/resolution",
            "price_paid_usdc": "50.00",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "market_question": verdict_data["market_question"],
            "resolution_verdict": verdict_data["resolution_verdict"],
            "evidence_chain": verdict_data["evidence_chain"],
            "decision_data": verdict_data["decision_data"],
        }

        if request_body.include_uma_data:
            response_payload["uma_assertion_data"] = verdict_data["uma_assertion_data"]

        if request_body.include_kalshi_format:
            response_payload["kalshi_resolution"] = verdict_data["kalshi_resolution"]

        if request_body.include_polymarket_format:
            response_payload["polymarket_resolution"] = verdict_data["polymarket_resolution"]

        return JSONResponse(status_code=200, content=response_payload)

    except Exception as exc:
        logger.exception("Error generating Fed resolution verdict: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Fed resolution generation failed: {exc}",
        ) from exc
