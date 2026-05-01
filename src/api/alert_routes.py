"""
HYDRA — Push-Based Alert Subscription Endpoints

Recurring revenue stream: agents pay $0.10 to subscribe and receive up to
100 webhook-delivered regulatory alerts. Poll endpoint at $0.05 per call
for agents that prefer pull-based access.

Endpoints:
  POST   /v1/alerts/subscribe       — $0.10 USDC (register webhook + conditions)
  GET    /v1/alerts/status           — FREE (check subscription status)
  DELETE /v1/alerts/{subscription_id} — FREE (cancel subscription)
  GET    /v1/alerts/feed             — $0.05 USDC (last 24h alert feed)
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.runtime.alert_engine import get_alert_engine

logger = logging.getLogger(__name__)

alert_router = APIRouter(prefix="/v1/alerts", tags=["alerts"])


# ─────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────


class AlertConditions(BaseModel):
    type: str = Field(default="all", description="Alert type filter: 'regulatory', 'fed', or 'all'")
    keywords: List[str] = Field(default_factory=list, description="Keywords to match in alert title/summary")


class SubscribeRequest(BaseModel):
    webhook_url: str = Field(..., description="URL to receive POST webhook alerts")
    conditions: AlertConditions = Field(default_factory=AlertConditions, description="Alert filter conditions")
    max_alerts: int = Field(default=100, ge=1, le=10000, description="Maximum alerts before subscription expires")


# ─────────────────────────────────────────────────────────────
# Paid Endpoints
# ─────────────────────────────────────────────────────────────


@alert_router.post("/subscribe", tags=["alerts"])
async def subscribe_alerts(request: SubscribeRequest):
    """
    Register a webhook URL to receive push-based regulatory alerts.
    $0.10 USDC — buys up to 100 alert deliveries (configurable via max_alerts).

    Conditions allow filtering by type ('regulatory', 'fed', 'all') and keywords.
    Alerts are delivered as POST requests to webhook_url with structured JSON payloads.
    """
    engine = get_alert_engine()
    try:
        sub = engine.subscribe(
            webhook_url=request.webhook_url,
            conditions=request.conditions.model_dump(),
            max_alerts=request.max_alerts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(content={
        "subscription_id": sub.subscription_id,
        "webhook_url": sub.webhook_url,
        "conditions": sub.conditions,
        "max_alerts": sub.max_alerts,
        "alerts_sent": 0,
        "remaining": sub.remaining(),
        "created_at": sub.created_at,
        "active": sub.active,
        "message": f"Subscribed. You will receive up to {sub.max_alerts} alerts at {sub.webhook_url}.",
    })


@alert_router.get("/feed", tags=["alerts"])
async def alert_feed(hours: int = Query(default=24, ge=1, le=168, description="Hours of history (max 168 = 7 days)")):
    """
    Real-time regulatory alert feed — last 24 hours (configurable).
    $0.05 USDC per call. No webhook needed — poll this endpoint for recent alerts.

    Returns structured alerts from all monitored regulatory sources (SEC, CFTC,
    FinCEN, OCC, CFPB, Fed, Treasury).
    """
    engine = get_alert_engine()
    alerts = engine.get_recent_alerts(hours=hours)

    # Strip internal _ts field from response
    cleaned = []
    for alert in alerts:
        cleaned.append({k: v for k, v in alert.items() if not k.startswith("_")})

    return JSONResponse(content={
        "alerts": cleaned,
        "count": len(cleaned),
        "hours": hours,
        "sources": ["SEC", "CFTC", "FinCEN", "OCC", "CFPB", "Fed", "Treasury"],
        "note": "Subscribe via POST /v1/alerts/subscribe for push-based delivery at $0.10/100 alerts.",
    })


# ─────────────────────────────────────────────────────────────
# Free Endpoints
# ─────────────────────────────────────────────────────────────


@alert_router.get("/status", tags=["alerts"])
async def alert_status(subscription_id: str = Query(..., description="Subscription ID to check")):
    """
    Check alert subscription status. FREE — no payment required.
    Returns remaining alerts, last triggered time, and active conditions.
    """
    engine = get_alert_engine()
    sub = engine.get_subscription(subscription_id)

    if sub is None:
        raise HTTPException(status_code=404, detail=f"Subscription '{subscription_id}' not found.")

    return JSONResponse(content={
        "subscription_id": sub.subscription_id,
        "active": sub.active,
        "webhook_url": sub.webhook_url,
        "conditions": sub.conditions,
        "max_alerts": sub.max_alerts,
        "alerts_sent": sub.alerts_sent,
        "remaining": sub.remaining(),
        "last_triggered": sub.last_triggered,
        "created_at": sub.created_at,
    })


@alert_router.delete("/{subscription_id}", tags=["alerts"])
async def cancel_alert(subscription_id: str):
    """
    Cancel an alert subscription. FREE — no payment required.
    Stops all future webhook deliveries for this subscription.
    """
    engine = get_alert_engine()
    cancelled = engine.cancel(subscription_id)

    if not cancelled:
        raise HTTPException(status_code=404, detail=f"Subscription '{subscription_id}' not found.")

    return JSONResponse(content={
        "subscription_id": subscription_id,
        "active": False,
        "message": "Subscription cancelled. No further alerts will be delivered.",
    })
