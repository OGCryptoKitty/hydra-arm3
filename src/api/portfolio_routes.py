"""
portfolio_routes.py — HYDRA Portfolio Intelligence & Orchestration
==================================================================
Premium endpoints combining multiple HYDRA capabilities into
single high-value products that don't exist anywhere else.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("hydra.portfolio")

router = APIRouter(tags=["portfolio"])

_brief_cache: dict[str, Any] = {}
_BRIEF_TTL = 1800  # 30 minutes


class Asset(BaseModel):
    symbol: str = Field(default="", description="Token symbol (e.g., ETH, BTC)")
    name: str = Field(default="", description="Protocol name (e.g., Uniswap, Aave)")
    type: str = Field(default="token", description="'token' or 'protocol'")


class PortfolioScanRequest(BaseModel):
    assets: List[Asset] = Field(..., min_length=1, max_length=20, description="List of tokens/protocols to scan")


class WatchlistRequest(BaseModel):
    assets: List[str] = Field(..., min_length=1, max_length=20, description="Token symbols or protocol names")


class OrchestrationStep(BaseModel):
    path: str = Field(..., description="HYDRA endpoint path (e.g., /v1/intelligence/pulse)")
    params: dict = Field(default_factory=dict, description="Query parameters")


class OrchestrateRequest(BaseModel):
    steps: List[OrchestrationStep] = Field(..., min_length=1, max_length=10, description="Endpoint calls to execute")


@router.post("/v1/portfolio/scan")
async def portfolio_scan(request: PortfolioScanRequest) -> dict:
    """
    Portfolio-level regulatory risk scan.

    Scans up to 20 tokens/protocols and returns individual risk scores
    plus an aggregate portfolio risk with cross-correlation amplification.
    $10.00 USDC — saves vs. calling /v1/intelligence/risk-score 20 times ($40).
    """
    now = datetime.now(timezone.utc)

    from src.services.regulatory import analyze_regulatory_risk
    from src.services.feeds import get_all_agencies_items

    all_feeds = get_all_agencies_items(days=30)

    results = []
    total_risk = 0
    high_risk_count = 0

    for asset in request.assets:
        target = asset.symbol or asset.name
        if not target:
            continue

        biz_type = "cryptocurrency_exchange" if asset.type == "token" else "defi_protocol"
        description = f"{target} {'token trading platform' if asset.type == 'token' else 'decentralized protocol'}"

        try:
            analysis = analyze_regulatory_risk(
                business_type=biz_type,
                description=description,
            )
            risk_pct = analysis.overall_risk_score
            level = analysis.risk_level.value if hasattr(analysis.risk_level, "value") else str(analysis.risk_level)
            regs = [{"name": r.regulation_name, "agency": r.agency} for r in (analysis.applicable_regulations or [])[:5]]
        except Exception:
            risk_pct = 50
            level = "medium"
            regs = []

        mention_count = 0
        for agency_items in all_feeds.values():
            for item in agency_items:
                if target.lower() in (item.title + " " + (item.summary or "")).lower():
                    mention_count += 1

        attention_boost = min(20, mention_count * 3)
        final_score = max(0, min(100, risk_pct + attention_boost))

        if final_score >= 70:
            high_risk_count += 1

        total_risk += final_score
        results.append({
            "asset": target,
            "type": asset.type,
            "risk_score": final_score,
            "risk_level": level,
            "agency_mentions_30d": mention_count,
            "applicable_regulations": regs,
        })

    avg_risk = total_risk / len(results) if results else 0
    correlation_amplifier = 1.0 + (high_risk_count * 0.1)
    portfolio_risk = min(100, int(avg_risk * correlation_amplifier))

    return {
        "portfolio_scan": "HYDRA Portfolio Regulatory Risk Assessment",
        "generated_at": now.isoformat(),
        "assets_scanned": len(results),
        "portfolio_risk_score": portfolio_risk,
        "portfolio_risk_level": "critical" if portfolio_risk >= 80 else "high" if portfolio_risk >= 60 else "medium" if portfolio_risk >= 40 else "low",
        "high_risk_assets": high_risk_count,
        "correlation_amplifier": round(correlation_amplifier, 2),
        "assets": results,
        "sources": ["HYDRA Regulatory Engine", "SEC RSS", "CFTC RSS", "FinCEN RSS", "OCC RSS", "CFPB RSS"],
    }


@router.post("/v1/portfolio/watchlist")
async def portfolio_watchlist(request: WatchlistRequest) -> dict:
    """
    Portfolio regulatory watchlist.

    Returns current regulatory status and recent agency mentions for each asset.
    $2.00 USDC.
    """
    now = datetime.now(timezone.utc)

    from src.services.feeds import get_all_agencies_items
    all_feeds = get_all_agencies_items(days=7)

    watchlist = []
    for asset_name in request.assets:
        mentions = []
        for agency, items in all_feeds.items():
            for item in items:
                text = (item.title + " " + (item.summary or "")).lower()
                if asset_name.lower() in text:
                    mentions.append({
                        "title": item.title,
                        "agency": agency,
                        "type": item.item_type,
                        "published": str(item.published),
                        "url": item.url,
                    })

        watchlist.append({
            "asset": asset_name,
            "mentions_7d": len(mentions),
            "alert_level": "high" if len(mentions) > 3 else "medium" if len(mentions) > 0 else "quiet",
            "recent_mentions": mentions[:5],
        })

    return {
        "watchlist": "HYDRA Portfolio Watchlist",
        "generated_at": now.isoformat(),
        "assets_monitored": len(watchlist),
        "assets": watchlist,
        "sources": list(all_feeds.keys()),
    }


@router.get("/v1/portfolio/market-brief")
async def market_brief() -> dict:
    """
    Executive market brief combining all HYDRA intelligence streams.

    Single endpoint for a complete market picture: top regulatory events,
    Fed signal, prediction market summary, portfolio risk overview.
    $3.00 USDC.
    """
    if "brief" in _brief_cache:
        cached = _brief_cache["brief"]
        if time.time() - cached.get("_ts", 0) < _BRIEF_TTL:
            return cached

    now = datetime.now(timezone.utc)

    from src.services.feeds import get_all_agencies_items

    daily = get_all_agencies_items(days=1)
    weekly = get_all_agencies_items(days=7)

    top_events = []
    for agency, items in daily.items():
        for item in items[:3]:
            top_events.append({
                "title": item.title,
                "agency": agency,
                "type": item.item_type,
                "url": item.url,
            })

    daily_count = sum(len(v) for v in daily.values())
    weekly_count = sum(len(v) for v in weekly.values())
    daily_avg = weekly_count / 7 if weekly_count else 0

    fed_data = {}
    try:
        from src.services.fed_intelligence import FedIntelligenceEngine
        fed = FedIntelligenceEngine()
        fed_data = {
            "next_fomc": fed.get_next_fomc(),
            "rate": fed.get_current_rate(),
            "is_fomc_day": fed.is_fomc_day(),
            "probabilities": fed.calculate_rate_probabilities(),
        }
    except Exception as exc:
        logger.debug("Fed data unavailable for market brief: %s", exc)

    market_data = {"markets_available": 0}
    try:
        from src.services.prediction_markets import PredictionMarketAggregator
        agg = PredictionMarketAggregator()
        markets = await agg.get_all_regulatory_markets()
        market_data = {
            "markets_available": len(markets),
            "top_markets": [
                {"question": m.get("question", "")[:100], "source": m.get("source", "")}
                for m in markets[:5]
            ],
        }
    except Exception as exc:
        logger.debug("Prediction market data unavailable: %s", exc)

    result = {
        "market_brief": "HYDRA Executive Market Brief",
        "generated_at": now.isoformat(),
        "regulatory": {
            "events_today": daily_count,
            "weekly_average": round(daily_avg, 1),
            "momentum": "accelerating" if daily_count > daily_avg * 1.5 else "decelerating" if daily_count < daily_avg * 0.5 else "steady",
            "top_events": top_events[:10],
            "agencies_active": list(daily.keys()),
        },
        "fed": fed_data,
        "prediction_markets": market_data,
        "meta": {
            "product": "HYDRA Executive Market Brief — single endpoint, complete picture",
            "refresh": "30 minutes",
        },
        "_ts": time.time(),
    }

    _brief_cache["brief"] = result
    return result


@router.post("/v1/orchestrate")
async def orchestrate(request: OrchestrateRequest) -> dict:
    """
    Multi-step task orchestration.

    Execute up to 10 HYDRA endpoint calls in one request.
    Cheaper than calling each individually. $0.05 per orchestration call.
    """
    now = datetime.now(timezone.utc)

    results = []
    for step in request.steps:
        step_result: dict[str, Any] = {"path": step.path, "status": "error"}
        try:
            if step.path == "/v1/intelligence/pulse":
                from src.api.intelligence_routes import regulatory_pulse
                hours = step.params.get("hours", 1)
                step_result = {"path": step.path, "status": "ok", "data": await regulatory_pulse(hours=int(hours))}
            elif step.path == "/v1/intelligence/digest":
                from src.api.intelligence_routes import daily_digest
                step_result = {"path": step.path, "status": "ok", "data": await daily_digest()}
            elif step.path == "/v1/x402/directory":
                from src.api.ecosystem_routes import x402_directory
                step_result = {"path": step.path, "status": "ok", "data": await x402_directory()}
            elif step.path == "/v1/x402/stats":
                from src.api.ecosystem_routes import x402_ecosystem_stats
                step_result = {"path": step.path, "status": "ok", "data": await x402_ecosystem_stats()}
            elif step.path.startswith("/v1/data/wikipedia"):
                from src.api.data_routes import data_router
                title = step.params.get("title", step.params.get("q", "Bitcoin"))
                import httpx
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        "https://en.wikipedia.org/api/rest_v1/page/summary/" + title,
                        headers={"User-Agent": "HYDRA/3.0"},
                    )
                    step_result = {"path": step.path, "status": "ok", "data": resp.json() if resp.status_code == 200 else {"error": resp.status_code}}
            else:
                step_result = {"path": step.path, "status": "unsupported", "note": "This endpoint is not yet available for orchestration"}
        except Exception as exc:
            step_result = {"path": step.path, "status": "error", "error": str(exc)[:200]}

        results.append(step_result)

    return {
        "orchestration": "HYDRA Multi-Step Task Result",
        "generated_at": now.isoformat(),
        "steps_requested": len(request.steps),
        "steps_completed": sum(1 for r in results if r.get("status") == "ok"),
        "results": results,
    }
