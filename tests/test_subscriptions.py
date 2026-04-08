"""Tests for the API key and subscription tier system."""

import pytest
from decimal import Decimal
from pathlib import Path

from src.runtime.subscriptions import (
    SubscriptionManager,
    SubscriptionTier,
    TIER_CONFIG,
    _hash_key,
)


class TestSubscriptionManager:
    def test_create_key_returns_raw_key(self, tmp_path: Path) -> None:
        sm = SubscriptionManager(keys_file=tmp_path / "keys.jsonl")
        raw = sm.create_key(tier=SubscriptionTier.FREE, label="test-bot")
        assert raw.startswith("hydra_")
        assert len(raw) > 20

    def test_validate_key_success(self, tmp_path: Path) -> None:
        sm = SubscriptionManager(keys_file=tmp_path / "keys.jsonl")
        raw = sm.create_key(tier=SubscriptionTier.STANDARD, label="bot-1")
        api_key = sm.validate_key(raw)
        assert api_key is not None
        assert api_key.tier == SubscriptionTier.STANDARD
        assert api_key.label == "bot-1"

    def test_validate_invalid_key_returns_none(self, tmp_path: Path) -> None:
        sm = SubscriptionManager(keys_file=tmp_path / "keys.jsonl")
        assert sm.validate_key("hydra_bogus_key") is None

    def test_record_usage_increments(self, tmp_path: Path) -> None:
        sm = SubscriptionManager(keys_file=tmp_path / "keys.jsonl")
        raw = sm.create_key(tier=SubscriptionTier.STANDARD)
        assert sm.record_usage(raw) is True
        api_key = sm.validate_key(raw)
        assert api_key.calls_this_month == 1

    def test_free_tier_limit(self, tmp_path: Path) -> None:
        sm = SubscriptionManager(keys_file=tmp_path / "keys.jsonl")
        raw = sm.create_key(tier=SubscriptionTier.FREE)
        # Free tier allows 10 calls
        for _ in range(10):
            assert sm.record_usage(raw) is True
        # 11th should fail
        assert sm.record_usage(raw) is False

    def test_discount_calculation(self, tmp_path: Path) -> None:
        sm = SubscriptionManager(keys_file=tmp_path / "keys.jsonl")
        raw_std = sm.create_key(tier=SubscriptionTier.STANDARD)
        raw_pro = sm.create_key(tier=SubscriptionTier.PROFESSIONAL)

        base = Decimal("10.00")
        assert sm.get_discounted_price(raw_std, base) == Decimal("9.00")   # 10% off
        assert sm.get_discounted_price(raw_pro, base) == Decimal("8.00")   # 20% off

    def test_deactivate_key(self, tmp_path: Path) -> None:
        sm = SubscriptionManager(keys_file=tmp_path / "keys.jsonl")
        raw = sm.create_key(tier=SubscriptionTier.FREE)
        key_hash = _hash_key(raw)
        prefix = key_hash[:12]
        assert sm.deactivate_key(prefix) is True
        assert sm.validate_key(raw) is None  # Deactivated

    def test_list_keys(self, tmp_path: Path) -> None:
        sm = SubscriptionManager(keys_file=tmp_path / "keys.jsonl")
        sm.create_key(tier=SubscriptionTier.FREE, label="bot-a")
        sm.create_key(tier=SubscriptionTier.STANDARD, label="bot-b")
        keys = sm.list_keys()
        assert len(keys) == 2
        labels = {k["label"] for k in keys}
        assert labels == {"bot-a", "bot-b"}

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        kf = tmp_path / "keys.jsonl"
        sm1 = SubscriptionManager(keys_file=kf)
        raw = sm1.create_key(tier=SubscriptionTier.PROFESSIONAL, label="persistent")
        # New instance should load the key
        sm2 = SubscriptionManager(keys_file=kf)
        api_key = sm2.validate_key(raw)
        assert api_key is not None
        assert api_key.tier == SubscriptionTier.PROFESSIONAL

    def test_tier_pricing(self, tmp_path: Path) -> None:
        sm = SubscriptionManager(keys_file=tmp_path / "keys.jsonl")
        tiers = sm.get_tier_pricing()
        assert len(tiers) == 4
        tier_names = {t["tier"] for t in tiers}
        assert tier_names == {"free", "standard", "professional", "enterprise"}
