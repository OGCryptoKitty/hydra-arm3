"""
HYDRA Arm 3 — Webhook Delivery System
=======================================
Delivers event notifications to subscriber webhook URLs.
Used for subscription alerts (regulatory events, Fed signals, market triggers).

Events:
  - regulatory_change: New SEC/CFTC/FinCEN announcement
  - fed_signal: Pre-FOMC signal generated
  - market_alert: Prediction market crosses threshold
  - remittance_ready: Treasury balance hit $1,000

Security:
  - Each delivery includes HMAC-SHA256 signature in X-Hydra-Signature header
  - Subscribers verify signature using their API key as the secret
  - Failed deliveries retry 3 times with exponential backoff
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("hydra.webhooks")

STATE_DIR: Path = Path(os.getenv("HYDRA_STATE_DIR", os.getenv("HYDRA_BOOTSTRAP_DIR", "/app/data")))
WEBHOOKS_FILE: Path = STATE_DIR / "webhooks.jsonl"

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_RETRIES = 3


@dataclass
class WebhookSubscription:
    """A registered webhook endpoint."""
    url: str
    events: list[str]  # e.g. ["regulatory_change", "fed_signal"]
    api_key_hash: str  # SHA-256 of the API key (for signature verification)
    label: str = ""
    active: bool = True
    created_at: str = ""
    last_delivery_at: str = ""
    delivery_count: int = 0
    failure_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "events": self.events,
            "api_key_hash": self.api_key_hash,
            "label": self.label,
            "active": self.active,
            "created_at": self.created_at,
            "last_delivery_at": self.last_delivery_at,
            "delivery_count": self.delivery_count,
            "failure_count": self.failure_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebhookSubscription":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _sign_payload(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for a webhook payload."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


class WebhookManager:
    """Manages webhook subscriptions and event delivery."""

    def __init__(self, webhooks_file: Optional[Path] = None) -> None:
        self._file = webhooks_file or WEBHOOKS_FILE
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._subscriptions: List[WebhookSubscription] = []
        self._load()

    def _load(self) -> None:
        if not self._file.exists():
            return
        try:
            with self._file.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._subscriptions.append(
                            WebhookSubscription.from_dict(json.loads(line))
                        )
                    except (json.JSONDecodeError, TypeError) as exc:
                        logger.warning("Skipping malformed webhook record: %s", exc)
        except OSError as exc:
            logger.error("Failed to load webhooks: %s", exc)

    def _save(self) -> None:
        try:
            with self._file.open("w", encoding="utf-8") as fh:
                for sub in self._subscriptions:
                    fh.write(json.dumps(sub.to_dict(), ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("Failed to save webhooks: %s", exc)

    @staticmethod
    def _validate_webhook_url(url: str) -> None:
        """
        Validate webhook URL to prevent SSRF attacks.
        Rejects private/internal IPs, localhost, and non-HTTPS URLs.
        """
        import ipaddress
        from urllib.parse import urlparse

        parsed = urlparse(url)

        # Must be HTTPS
        if parsed.scheme != "https":
            raise ValueError(f"Webhook URL must use HTTPS (got {parsed.scheme}://)")

        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Webhook URL has no hostname")

        # Block obvious internal hostnames
        _blocked = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]", "metadata.google.internal"}
        if hostname.lower() in _blocked:
            raise ValueError(f"Webhook URL cannot target internal host: {hostname}")

        # Resolve and block private/reserved IPs (best-effort — DNS failure is not fatal
        # since delivery will simply fail later if the host is unreachable)
        import socket
        try:
            resolved = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
            for _, _, _, _, sockaddr in resolved:
                ip = ipaddress.ip_address(sockaddr[0])
                if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                    raise ValueError(f"Webhook URL resolves to non-public IP: {ip}")
        except socket.gaierror:
            logger.warning("Cannot resolve webhook hostname %s — will allow registration", hostname)

    def register(
        self,
        url: str,
        events: list[str],
        api_key_hash: str,
        label: str = "",
    ) -> WebhookSubscription:
        """Register a new webhook subscription."""
        self._validate_webhook_url(url)
        sub = WebhookSubscription(
            url=url,
            events=events,
            api_key_hash=api_key_hash,
            label=label,
            active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._subscriptions.append(sub)
        self._save()
        logger.info("Webhook registered: %s for events %s", url, events)
        return sub

    def list_subscriptions(self) -> List[Dict[str, Any]]:
        """List all webhook subscriptions."""
        return [s.to_dict() for s in self._subscriptions]

    def deactivate(self, url: str) -> bool:
        """Deactivate a webhook by URL."""
        for sub in self._subscriptions:
            if sub.url == url:
                sub.active = False
                self._save()
                return True
        return False

    async def deliver(self, event_type: str, payload: Dict[str, Any]) -> int:
        """
        Deliver an event to all matching active subscribers.
        Returns number of successful deliveries.
        """
        matching = [
            s for s in self._subscriptions
            if s.active and event_type in s.events
        ]

        if not matching:
            return 0

        delivered = 0
        body = json.dumps({
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }, ensure_ascii=False)

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for sub in matching:
                signature = _sign_payload(body, sub.api_key_hash)
                headers = {
                    "Content-Type": "application/json",
                    "X-Hydra-Event": event_type,
                    "X-Hydra-Signature": f"sha256={signature}",
                    "User-Agent": "HYDRA-Arm3-Webhook/1.0",
                }

                success = False
                for attempt in range(_MAX_RETRIES):
                    try:
                        resp = await client.post(sub.url, content=body, headers=headers)
                        if resp.status_code < 300:
                            success = True
                            break
                        logger.warning(
                            "Webhook delivery failed (attempt %d): %s → %d",
                            attempt + 1, sub.url, resp.status_code,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Webhook delivery error (attempt %d): %s → %s",
                            attempt + 1, sub.url, exc,
                        )

                    # Exponential backoff
                    if attempt < _MAX_RETRIES - 1:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)

                if success:
                    sub.delivery_count += 1
                    sub.last_delivery_at = datetime.now(timezone.utc).isoformat()
                    delivered += 1
                else:
                    sub.failure_count += 1
                    if sub.failure_count >= 10:
                        sub.active = False
                        logger.warning(
                            "Webhook auto-deactivated after 10 failures: %s", sub.url
                        )

        self._save()
        logger.info(
            "Webhook delivery: event=%s subscribers=%d delivered=%d",
            event_type, len(matching), delivered,
        )
        return delivered
