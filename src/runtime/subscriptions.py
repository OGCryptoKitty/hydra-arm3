"""
HYDRA Arm 3 — API Key & Subscription Tier System
==================================================
Manages API keys with tiered access levels for recurring revenue.

Tiers:
  FREE        — No API key required. Rate-limited to 10 paid calls/day.
                Discovery endpoints always free.
  STANDARD    — $99/month. 500 paid calls/month, 10% discount on endpoint prices.
  PROFESSIONAL— $499/month. 5,000 paid calls/month, 20% discount on endpoint prices.
  ENTERPRISE  — Custom pricing. Unlimited calls, 30% discount, dedicated support.

API keys are passed via X-API-Key header. Keys are stored in a JSONL file
alongside the transaction log for persistence.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hydra.subscriptions")

STATE_DIR: Path = Path(os.getenv("HYDRA_STATE_DIR", os.getenv("HYDRA_BOOTSTRAP_DIR", "/app/data")))
KEYS_FILE: Path = STATE_DIR / "api_keys.jsonl"


class SubscriptionTier(str, Enum):
    FREE = "free"
    STANDARD = "standard"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# Tier configuration
TIER_CONFIG: Dict[str, Dict[str, Any]] = {
    SubscriptionTier.FREE: {
        "monthly_price_usdc": Decimal("0"),
        "monthly_call_limit": 10,
        "price_discount_pct": 0,
        "description": "Free tier — 10 paid calls/day, no discount",
    },
    SubscriptionTier.STANDARD: {
        "monthly_price_usdc": Decimal("99"),
        "monthly_call_limit": 500,
        "price_discount_pct": 10,
        "description": "Standard — 500 calls/month, 10% endpoint discount",
    },
    SubscriptionTier.PROFESSIONAL: {
        "monthly_price_usdc": Decimal("499"),
        "monthly_call_limit": 5000,
        "price_discount_pct": 20,
        "description": "Professional — 5,000 calls/month, 20% endpoint discount",
    },
    SubscriptionTier.ENTERPRISE: {
        "monthly_price_usdc": Decimal("0"),  # Custom pricing
        "monthly_call_limit": -1,  # Unlimited
        "price_discount_pct": 30,
        "description": "Enterprise — unlimited calls, 30% discount, custom pricing",
    },
}


@dataclass
class APIKey:
    """Represents a registered API key with tier and usage tracking."""
    key_hash: str  # SHA-256 hash of the actual key (never store plaintext)
    tier: SubscriptionTier
    created_at: str
    label: str = ""  # Human-readable label (e.g., "Trading Bot Alpha")
    calls_this_month: int = 0
    month_reset: str = ""  # ISO month string, e.g. "2026-04"
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_hash": self.key_hash,
            "tier": self.tier.value if isinstance(self.tier, SubscriptionTier) else self.tier,
            "created_at": self.created_at,
            "label": self.label,
            "calls_this_month": self.calls_this_month,
            "month_reset": self.month_reset,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APIKey":
        return cls(
            key_hash=data["key_hash"],
            tier=SubscriptionTier(data.get("tier", "free")),
            created_at=data.get("created_at", ""),
            label=data.get("label", ""),
            calls_this_month=data.get("calls_this_month", 0),
            month_reset=data.get("month_reset", ""),
            active=data.get("active", True),
        )


def _hash_key(raw_key: str) -> str:
    """Hash an API key for storage. Never store raw keys."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


class SubscriptionManager:
    """
    Manages API keys, subscription tiers, and usage tracking.

    Keys are stored as SHA-256 hashes in a JSONL file.
    Usage counters reset monthly.
    """

    def __init__(self, keys_file: Optional[Path] = None) -> None:
        self._keys_file = keys_file or KEYS_FILE
        self._keys_file.parent.mkdir(parents=True, exist_ok=True)
        self._keys: Dict[str, APIKey] = {}
        self._load()

    def _load(self) -> None:
        """Load API keys from JSONL file."""
        if not self._keys_file.exists():
            return
        try:
            with self._keys_file.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        key = APIKey.from_dict(data)
                        self._keys[key.key_hash] = key
                    except (json.JSONDecodeError, KeyError) as exc:
                        logger.warning("Skipping malformed API key record: %s", exc)
        except OSError as exc:
            logger.error("Failed to load API keys: %s", exc)

    def _save(self) -> None:
        """Rewrite the keys file with current state."""
        try:
            with self._keys_file.open("w", encoding="utf-8") as fh:
                for key in self._keys.values():
                    fh.write(json.dumps(key.to_dict(), ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("Failed to save API keys: %s", exc)

    def create_key(
        self,
        tier: SubscriptionTier = SubscriptionTier.FREE,
        label: str = "",
    ) -> str:
        """
        Generate a new API key and register it.

        Returns the raw API key (only shown once — not stored).
        """
        raw_key = f"hydra_{secrets.token_urlsafe(32)}"
        key_hash = _hash_key(raw_key)
        api_key = APIKey(
            key_hash=key_hash,
            tier=tier,
            created_at=datetime.now(timezone.utc).isoformat(),
            label=label,
            calls_this_month=0,
            month_reset=_current_month(),
            active=True,
        )
        self._keys[key_hash] = api_key
        self._save()
        logger.info("API key created: tier=%s label=%s hash=%s...", tier.value, label, key_hash[:12])
        return raw_key

    def validate_key(self, raw_key: str) -> Optional[APIKey]:
        """
        Validate an API key and return its record, or None if invalid.
        Resets monthly counter if needed.
        """
        key_hash = _hash_key(raw_key)
        api_key = self._keys.get(key_hash)
        if api_key is None or not api_key.active:
            return None

        # Reset monthly counter if month has changed
        current = _current_month()
        if api_key.month_reset != current:
            api_key.calls_this_month = 0
            api_key.month_reset = current
            self._save()

        return api_key

    def record_usage(self, raw_key: str) -> bool:
        """
        Record a paid API call. Returns True if within limits, False if over quota.
        """
        api_key = self.validate_key(raw_key)
        if api_key is None:
            return False

        config = TIER_CONFIG[api_key.tier]
        limit = config["monthly_call_limit"]

        # -1 means unlimited
        if limit != -1 and api_key.calls_this_month >= limit:
            return False

        api_key.calls_this_month += 1
        self._save()
        return True

    def get_discount(self, raw_key: str) -> int:
        """Get the discount percentage for this API key's tier."""
        api_key = self.validate_key(raw_key)
        if api_key is None:
            return 0
        return TIER_CONFIG[api_key.tier]["price_discount_pct"]

    def get_discounted_price(self, raw_key: str, base_price: Decimal) -> Decimal:
        """Apply tier discount to a base price."""
        discount_pct = self.get_discount(raw_key)
        if discount_pct == 0:
            return base_price
        discount = base_price * Decimal(discount_pct) / Decimal(100)
        return (base_price - discount).quantize(Decimal("0.01"))

    def list_keys(self) -> List[Dict[str, Any]]:
        """List all API keys (hashed, never raw)."""
        return [
            {
                "key_hash_prefix": k.key_hash[:12] + "...",
                "tier": k.tier.value if isinstance(k.tier, SubscriptionTier) else k.tier,
                "label": k.label,
                "calls_this_month": k.calls_this_month,
                "active": k.active,
                "created_at": k.created_at,
            }
            for k in self._keys.values()
        ]

    def deactivate_key(self, key_hash_prefix: str) -> bool:
        """Deactivate an API key by hash prefix (first 12 chars)."""
        for kh, key in self._keys.items():
            if kh.startswith(key_hash_prefix):
                key.active = False
                self._save()
                logger.info("API key deactivated: %s...", key_hash_prefix)
                return True
        return False

    def get_tier_pricing(self) -> List[Dict[str, Any]]:
        """Return tier pricing for display."""
        return [
            {
                "tier": tier.value,
                "monthly_price_usdc": str(config["monthly_price_usdc"]),
                "monthly_call_limit": config["monthly_call_limit"],
                "price_discount_pct": config["price_discount_pct"],
                "description": config["description"],
            }
            for tier, config in TIER_CONFIG.items()
        ]
