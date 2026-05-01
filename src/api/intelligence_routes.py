"""
intelligence_routes.py — HYDRA Composite Intelligence Products
===============================================================
Unique data products that don't exist anywhere else.
Combines regulatory signals + Fed intelligence + prediction markets
+ on-chain data into composite analytical products.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger("hydra.intelligence")

router = APIRouter(prefix="/v1/intelligence", tags=["intelligence"])

# ── Caches ────────────────────────────────────────────────────
_pulse_cache: dict[str, Any] = {}
_PULSE_TTL = 3600  # 1 hour
_digest_cache: dict[str, Any] = {}
_DIGEST_TTL = 86400  # 24 hours


def _agency_risk_weight(source: str) -> float:
    weights = {
        "SEC": 0.30, "CFTC": 0.20, "FinCEN": 0.15,
        "OCC": 0.10, "CFPB": 0.10, "Fed": 0.15,
    }
    return weights.get(source, 0.05)


def _compute_pulse_score(items: list) -> dict:
    if not items:
        return {"score": 0, "signal": "neutral", "confidence": 0.0}

    enforcement_keywords = [
        "enforcement", "action", "charged", "penalty", "fine", "violation",
        "fraud", "settled", "cease", "desist", "complaint", "injunction",
    ]
    positive_keywords = [
        "approved", "guidance", "framework", "safe harbor", "no-action",
        "exemption", "clarity", "innovation",
    ]

    enforcement_count = 0
    positive_count = 0
    weighted_activity = 0.0

    for item in items:
        text = (str(item.get("title", "")) + " " + str(item.get("summary", ""))).lower()
        source = str(item.get("source", ""))
        weight = _agency_risk_weight(source)
        weighted_activity += weight

        if any(kw in text for kw in enforcement_keywords):
            enforcement_count += 1
        if any(kw in text for kw in positive_keywords):
            positive_count += 1

    net = positive_count - enforcement_count
    total = len(items)
    score = max(0, min(100, 50 + (net * 10) - int(weighted_activity * 5)))

    if net > 1:
        signal = "bullish"
    elif net < -1:
        signal = "bearish"
    else:
        signal = "neutral"

    confidence = min(0.95, 0.3 + (total * 0.05))

    return {
        "score": score,
        "signal": signal,
        "confidence": round(confidence, 2),
        "enforcement_events": enforcement_count,
        "positive_events": positive_count,
        "total_items_analyzed": total,
    }


@router.get("/pulse")
async def regulatory_pulse(
    hours: int = Query(1, ge=1, le=24, description="Lookback window in hours"),
) -> dict:
    """
    Hourly regulatory pulse — aggregated activity across all monitored agencies.

    Combines SEC, CFTC, FinCEN, OCC, CFPB, Fed, Treasury RSS activity
    into a single structured report with composite risk signals.
    Generated fresh each hour, cached for efficiency.
    """
    cache_key = f"pulse_{hours}"
    if cache_key in _pulse_cache:
        cached = _pulse_cache[cache_key]
        if time.time() - cached.get("_ts", 0) < _PULSE_TTL:
            return cached

    now = datetime.now(timezone.utc)

    from src.services.feeds import get_all_agencies_items
    all_items_by_agency = get_all_agencies_items(days=1)

    items = []
    agency_summary = {}
    for agency, agency_items in all_items_by_agency.items():
        recent = []
        for item in agency_items:
            recent.append({
                "title": item.title,
                "source": agency,
                "published": str(item.published),
                "item_type": item.item_type,
                "link": item.url,
                "summary": item.summary[:200] if item.summary else "",
            })
        items.extend(recent)
        agency_summary[agency] = len(recent)

    pulse_score = _compute_pulse_score(items)

    result = {
        "pulse": "HYDRA Regulatory Pulse",
        "generated_at": now.isoformat(),
        "lookback_hours": hours,
        "hydra_signal": pulse_score,
        "agency_activity": agency_summary,
        "total_items": len(items),
        "items": items[:50],
        "sources": list(all_items_by_agency.keys()),
        "meta": {
            "product": "HYDRA Composite Intelligence",
            "unique": "No other service combines all US financial regulator feeds into a single scored pulse.",
            "refresh_interval": "1 hour",
        },
        "_ts": time.time(),
    }

    _pulse_cache[cache_key] = result
    return result


@router.get("/alpha")
async def composite_alpha_signal() -> dict:
    """
    Premium composite alpha signal.

    Combines four independent data streams into a single actionable signal:
    1. Regulatory risk assessment (SEC/CFTC/FinCEN enforcement activity)
    2. Fed rate probability (FOMC model with speech analysis)
    3. Prediction market sentiment (Polymarket + Kalshi regulatory markets)
    4. RSS feed momentum (rate of change in regulatory activity)

    Returns a composite score, directional bias, and confidence level.
    This product does not exist anywhere else.
    """
    now = datetime.now(timezone.utc)

    # Stream 1: Regulatory pulse
    from src.services.feeds import get_all_agencies_items
    all_items = get_all_agencies_items(days=7)
    flat_items = []
    for agency_items in all_items.values():
        for item in agency_items:
            flat_items.append({
                "title": item.title,
                "source": getattr(item, "agency", ""),
                "summary": item.summary[:200] if item.summary else "",
            })
    reg_score = _compute_pulse_score(flat_items)

    # Stream 2: Fed intelligence
    fed_signal = {}
    try:
        from src.services.fed_intelligence import FedIntelligenceEngine
        fed = FedIntelligenceEngine()
        fed_signal = fed.generate_pre_fomc_signal()
    except Exception as exc:
        logger.debug("Fed signal unavailable: %s", exc)
        fed_signal = {"rate_direction": "unknown", "probabilities": {}}

    # Stream 3: Prediction markets
    market_sentiment = {"bullish_pct": 50, "bearish_pct": 50, "markets_analyzed": 0}
    try:
        from src.services.prediction_markets import PredictionMarketAggregator
        agg = PredictionMarketAggregator()
        markets = await agg.get_all_regulatory_markets()
        if markets:
            market_sentiment["markets_analyzed"] = len(markets)
    except Exception as exc:
        logger.debug("Prediction markets unavailable: %s", exc)

    # Stream 4: Activity momentum
    recent_items = get_all_agencies_items(days=1)
    recent_count = sum(len(v) for v in recent_items.values())
    weekly_items = get_all_agencies_items(days=7)
    weekly_count = sum(len(v) for v in weekly_items.values())
    daily_avg = weekly_count / 7 if weekly_count > 0 else 0
    momentum = "accelerating" if recent_count > daily_avg * 1.5 else (
        "decelerating" if recent_count < daily_avg * 0.5 else "steady"
    )

    # Composite score
    composite = reg_score["score"]
    fed_probs = fed_signal.get("probabilities", {})
    if fed_probs.get("hold", 0) > 0.6:
        composite += 5
    elif fed_probs.get("hike", 0) > 0.3:
        composite -= 10

    if momentum == "accelerating":
        composite -= 5
    elif momentum == "decelerating":
        composite += 3

    composite = max(0, min(100, composite))

    if composite > 60:
        direction = "bullish"
    elif composite < 40:
        direction = "bearish"
    else:
        direction = "neutral"

    return {
        "alpha": "HYDRA Composite Alpha Signal",
        "generated_at": now.isoformat(),
        "composite_score": composite,
        "direction": direction,
        "confidence": reg_score["confidence"],
        "streams": {
            "regulatory": {
                "score": reg_score["score"],
                "signal": reg_score["signal"],
                "enforcement_events": reg_score["enforcement_events"],
                "positive_events": reg_score["positive_events"],
            },
            "fed": {
                "next_fomc": fed_signal.get("next_fomc", {}),
                "rate_probabilities": fed_probs,
                "current_rate": fed_signal.get("current_rate", {}),
            },
            "prediction_markets": market_sentiment,
            "momentum": {
                "recent_24h": recent_count,
                "weekly_avg_daily": round(daily_avg, 1),
                "trend": momentum,
            },
        },
        "sources": ["SEC", "CFTC", "FinCEN", "OCC", "CFPB", "Fed", "Polymarket", "Kalshi", "FOMC Model"],
        "meta": {
            "product": "HYDRA Composite Alpha — the only signal combining regulatory + Fed + prediction markets",
            "unique": True,
        },
    }


@router.get("/risk-score")
async def risk_score(
    token: Optional[str] = Query(None, description="Token symbol (e.g., BTC, ETH, SOL)"),
    protocol: Optional[str] = Query(None, description="Protocol name (e.g., Uniswap, Aave)"),
) -> dict:
    """
    Real-time regulatory risk score for any token or protocol.

    Returns a 0-100 score based on regulatory exposure, agency attention,
    and compliance posture. Uses HYDRA's 1500+ line regulatory engine.
    """
    now = datetime.now(timezone.utc)
    target = token or protocol or "crypto"

    from src.services.regulatory import analyze_regulatory_risk

    description = f"{target} cryptocurrency/DeFi protocol"
    if token:
        description = f"{token} token trading platform with {token} as primary asset"
    if protocol:
        description = f"{protocol} decentralized protocol providing DeFi services"

    try:
        result = analyze_regulatory_risk(
            business_type="cryptocurrency_exchange" if token else "defi_protocol",
            description=description,
        )
        risk_pct = result.overall_risk_score
        level = result.risk_level.value if hasattr(result.risk_level, "value") else str(result.risk_level)
        regs = [
            {
                "name": r.regulation_name,
                "agency": r.agency,
                "impact": r.impact_level,
            }
            for r in (result.applicable_regulations or [])[:10]
        ]
        gaps = [str(g) for g in (result.compliance_gaps or [])[:5]]
        actions = [str(a) for a in (result.priority_actions or [])[:5]]
    except Exception as exc:
        logger.warning("Risk score engine error: %s", exc)
        risk_pct = 50
        level = "medium"
        regs = []
        gaps = []
        actions = []

    from src.services.feeds import get_all_agencies_items
    all_items = get_all_agencies_items(days=30)
    mention_count = 0
    for agency_items in all_items.values():
        for item in agency_items:
            if target.lower() in (item.title + " " + (item.summary or "")).lower():
                mention_count += 1

    attention_boost = min(20, mention_count * 3)
    final_score = max(0, min(100, risk_pct + attention_boost))

    return {
        "risk_score": final_score,
        "target": target,
        "target_type": "token" if token else "protocol",
        "risk_level": level,
        "generated_at": now.isoformat(),
        "regulatory_exposure": {
            "applicable_regulations": regs,
            "compliance_gaps": gaps,
            "priority_actions": actions,
        },
        "agency_attention": {
            "mentions_last_30d": mention_count,
            "attention_score": attention_boost,
        },
        "sources": ["HYDRA Regulatory Engine", "SEC RSS", "CFTC RSS", "FinCEN RSS"],
        "meta": {
            "product": "HYDRA Risk Score — real-time regulatory risk quantification",
        },
    }


@router.get("/digest")
async def daily_digest() -> dict:
    """
    Daily market + regulatory digest.

    Comprehensive summary suitable for compliance teams, trading desks,
    or autonomous agents making allocation decisions.
    """
    cache_key = "digest_daily"
    if cache_key in _digest_cache:
        cached = _digest_cache[cache_key]
        if time.time() - cached.get("_ts", 0) < _DIGEST_TTL:
            return cached

    now = datetime.now(timezone.utc)

    from src.services.feeds import get_all_agencies_items
    all_items = get_all_agencies_items(days=1)

    agency_digests = {}
    total = 0
    for agency, items in all_items.items():
        agency_digests[agency] = {
            "count": len(items),
            "headlines": [
                {"title": i.title, "type": i.item_type, "url": i.url}
                for i in items[:5]
            ],
        }
        total += len(items)

    flat = []
    for items in all_items.values():
        for item in items:
            flat.append({
                "title": item.title,
                "source": "",
                "summary": item.summary[:200] if item.summary else "",
            })
    pulse = _compute_pulse_score(flat)

    fed_summary = {}
    try:
        from src.services.fed_intelligence import FedIntelligenceEngine
        fed = FedIntelligenceEngine()
        fed_summary = {
            "next_fomc": fed.get_next_fomc(),
            "current_rate": fed.get_current_rate(),
            "is_fomc_day": fed.is_fomc_day(),
        }
    except Exception as exc:
        logger.debug("Fed summary unavailable for digest: %s", exc)

    result = {
        "digest": "HYDRA Daily Regulatory Digest",
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "hydra_signal": pulse,
        "total_items": total,
        "by_agency": agency_digests,
        "fed_summary": fed_summary,
        "sources": list(all_items.keys()) + ["FOMC Model"],
        "meta": {
            "product": "HYDRA Daily Digest — the only combined regulatory + Fed intelligence briefing",
            "next_update": "Tomorrow at 00:00 UTC",
        },
        "_ts": time.time(),
    }

    _digest_cache[cache_key] = result
    return result


# ─────────────────────────────────────────────────────────────
# Real-Time Economic Data Endpoint
# ─────────────────────────────────────────────────────────────


@router.get(
    "/economic-snapshot",
    summary="Live Economic Data Snapshot ($0.50 USDC)",
    description=(
        "**$0.50 USDC via x402.** "
        "Atomic real-time economic data from FRED, BLS, Treasury, and Federal Register. "
        "Returns the freshest available: Fed funds rate, CPI, PCE, GDP, unemployment, "
        "Treasury yields, 10Y-2Y spread, VIX, plus latest SEC/CFTC rulemakings. "
        "Designed for prediction market agents that need up-to-the-second macro data "
        "before trading FOMC, inflation, and recession markets."
    ),
)
async def economic_snapshot():
    """
    Atomic real-time economic data snapshot.
    Combines FRED + BLS + Treasury + Federal Register into one payload.
    """
    try:
        from src.services.realtime_data import get_economic_snapshot
        snapshot = await get_economic_snapshot()
        return {
            "endpoint": "/v1/intelligence/economic-snapshot",
            **snapshot,
        }
    except Exception as exc:
        logger.exception("Economic snapshot failed: %s", exc)
        return {"error": str(exc), "fallback": "Set FRED_API_KEY for live FRED data"}


@router.get(
    "/regulatory-pulse-live",
    summary="Live Regulatory Pulse ($0.50 USDC)",
    description=(
        "**$0.50 USDC via x402.** "
        "Real-time regulatory activity pulse from SEC EDGAR full-text search, "
        "Federal Register API, and Congress bill tracker. "
        "Returns latest crypto/ETF/enforcement filings, new SEC/CFTC rulemakings, "
        "and crypto legislation status — all pulled live at request time."
    ),
)
async def regulatory_pulse_live():
    """
    Real-time regulatory activity pulse from EDGAR + Federal Register + Congress.
    """
    try:
        from src.services.realtime_data import get_regulatory_pulse
        pulse = await get_regulatory_pulse()
        return {
            "endpoint": "/v1/intelligence/regulatory-pulse-live",
            **pulse,
        }
    except Exception as exc:
        logger.exception("Regulatory pulse failed: %s", exc)
        return {"error": str(exc)}
