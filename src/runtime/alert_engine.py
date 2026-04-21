"""
alert_engine.py — Push-Based Alert System
==========================================
Monitors regulatory RSS feeds, Fed signals, and on-chain events.
Pushes alerts to registered webhook subscribers.
Revenue: $0.10 per 100 alerts (recurring as subscriptions renew).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("hydra.alerts")

STATE_DIR = Path(os.getenv("HYDRA_STATE_DIR", os.getenv("HYDRA_BOOTSTRAP_DIR", "/tmp/hydra-data")))
SUBSCRIPTIONS_FILE = STATE_DIR / "alert_subscriptions.json"
ALERT_HISTORY_FILE = STATE_DIR / "alert_history.json"


@dataclass
class AlertSubscription:
    subscription_id: str
    webhook_url: str
    conditions: dict
    max_alerts: int = 100
    alerts_sent: int = 0
    created_at: str = ""
    last_triggered: Optional[str] = None
    active: bool = True

    def remaining(self) -> int:
        return max(0, self.max_alerts - self.alerts_sent)

    def is_exhausted(self) -> bool:
        return self.alerts_sent >= self.max_alerts


class AlertEngine:
    """Manages alert subscriptions and delivery."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, AlertSubscription] = {}
        self._alert_history: list[dict] = []
        self._last_check: float = 0
        self._last_feed_items: list[dict] = []
        self._load_state()

    def _load_state(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if SUBSCRIPTIONS_FILE.exists():
            try:
                data = json.loads(SUBSCRIPTIONS_FILE.read_text())
                for sub_id, sub_data in data.items():
                    self._subscriptions[sub_id] = AlertSubscription(**sub_data)
            except Exception as exc:
                logger.warning("Failed to load subscriptions: %s", exc)
        if ALERT_HISTORY_FILE.exists():
            try:
                self._alert_history = json.loads(ALERT_HISTORY_FILE.read_text())[-500:]
            except Exception:
                pass

    def _save_state(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            SUBSCRIPTIONS_FILE.write_text(json.dumps(
                {sid: asdict(sub) for sid, sub in self._subscriptions.items()},
                indent=2
            ))
        except Exception as exc:
            logger.warning("Failed to save subscriptions: %s", exc)
        try:
            ALERT_HISTORY_FILE.write_text(json.dumps(self._alert_history[-500:], indent=2))
        except Exception:
            pass

    def subscribe(self, webhook_url: str, conditions: dict, max_alerts: int = 100) -> AlertSubscription:
        sub_id = str(uuid.uuid4())[:12]
        sub = AlertSubscription(
            subscription_id=sub_id,
            webhook_url=webhook_url,
            conditions=conditions,
            max_alerts=max_alerts,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._subscriptions[sub_id] = sub
        self._save_state()
        return sub

    def get_subscription(self, sub_id: str) -> Optional[AlertSubscription]:
        return self._subscriptions.get(sub_id)

    def cancel(self, sub_id: str) -> bool:
        if sub_id in self._subscriptions:
            self._subscriptions[sub_id].active = False
            self._save_state()
            return True
        return False

    def get_recent_alerts(self, hours: int = 24) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return [a for a in self._alert_history if a.get("_ts", 0) > cutoff]

    async def check_and_deliver(self, feed_items: list[dict]) -> int:
        """Check feed items against subscriptions and deliver alerts."""
        delivered = 0
        now = datetime.now(timezone.utc)

        # Detect new items since last check
        new_items = []
        old_titles = {item.get("title", "") for item in self._last_feed_items}
        for item in feed_items:
            if item.get("title", "") not in old_titles:
                new_items.append(item)
        self._last_feed_items = feed_items[-100:]

        if not new_items:
            return 0

        # Add to alert history
        for item in new_items:
            alert_record = {
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "url": item.get("link", ""),
                "published": item.get("published", ""),
                "summary": item.get("summary", "")[:300],
                "detected_at": now.isoformat(),
                "_ts": time.time(),
            }
            self._alert_history.append(alert_record)

        # Deliver to matching subscriptions
        async with httpx.AsyncClient(timeout=5.0) as client:
            for sub in list(self._subscriptions.values()):
                if not sub.active or sub.is_exhausted():
                    continue

                for item in new_items:
                    if self._matches(item, sub.conditions):
                        try:
                            await client.post(sub.webhook_url, json={
                                "alert": "HYDRA Regulatory Alert",
                                "subscription_id": sub.subscription_id,
                                "item": {
                                    "title": item.get("title", ""),
                                    "source": item.get("source", ""),
                                    "url": item.get("link", ""),
                                    "summary": item.get("summary", "")[:300],
                                },
                                "remaining_alerts": sub.remaining() - 1,
                                "timestamp": now.isoformat(),
                            })
                            sub.alerts_sent += 1
                            sub.last_triggered = now.isoformat()
                            delivered += 1
                            if sub.is_exhausted():
                                sub.active = False
                                break
                        except Exception as exc:
                            logger.debug("Alert delivery to %s failed: %s", sub.webhook_url, exc)

        if delivered > 0:
            self._save_state()
            logger.info("Delivered %d alerts to subscribers", delivered)

        return delivered

    @staticmethod
    def _matches(item: dict, conditions: dict) -> bool:
        alert_type = conditions.get("type", "all")
        keywords = [k.lower() for k in conditions.get("keywords", [])]

        if alert_type != "all":
            source = item.get("source", "").lower()
            if alert_type == "regulatory" and source not in ("sec", "cftc", "fincen", "occ", "cfpb"):
                return False
            if alert_type == "fed" and "fed" not in source:
                return False

        if keywords:
            text = (item.get("title", "") + " " + item.get("summary", "")).lower()
            return any(kw in text for kw in keywords)

        return True


# Singleton
_engine: Optional[AlertEngine] = None


def get_alert_engine() -> AlertEngine:
    global _engine
    if _engine is None:
        _engine = AlertEngine()
    return _engine
