"""Tests for the webhook delivery system."""

import pytest
from pathlib import Path

from src.services.webhooks import WebhookManager, WebhookSubscription


class TestWebhookManager:
    def test_register_webhook(self, tmp_path: Path) -> None:
        wm = WebhookManager(webhooks_file=tmp_path / "hooks.jsonl")
        sub = wm.register(
            url="https://example.com/webhook",
            events=["regulatory_change"],
            api_key_hash="abc123",
            label="test-hook",
        )
        assert sub.url == "https://example.com/webhook"
        assert sub.active is True
        assert "regulatory_change" in sub.events

    def test_list_subscriptions(self, tmp_path: Path) -> None:
        wm = WebhookManager(webhooks_file=tmp_path / "hooks.jsonl")
        wm.register(url="https://a.com/hook", events=["fed_signal"], api_key_hash="x")
        wm.register(url="https://b.com/hook", events=["market_alert"], api_key_hash="y")
        subs = wm.list_subscriptions()
        assert len(subs) == 2

    def test_deactivate_webhook(self, tmp_path: Path) -> None:
        wm = WebhookManager(webhooks_file=tmp_path / "hooks.jsonl")
        wm.register(url="https://a.com/hook", events=["fed_signal"], api_key_hash="x")
        assert wm.deactivate("https://a.com/hook") is True
        subs = wm.list_subscriptions()
        assert subs[0]["active"] is False

    def test_deactivate_nonexistent(self, tmp_path: Path) -> None:
        wm = WebhookManager(webhooks_file=tmp_path / "hooks.jsonl")
        assert wm.deactivate("https://nope.com") is False

    def test_persistence(self, tmp_path: Path) -> None:
        f = tmp_path / "hooks.jsonl"
        wm1 = WebhookManager(webhooks_file=f)
        wm1.register(url="https://persist.com/hook", events=["regulatory_change"], api_key_hash="z")
        # New instance should load from file
        wm2 = WebhookManager(webhooks_file=f)
        subs = wm2.list_subscriptions()
        assert len(subs) == 1
        assert subs[0]["url"] == "https://persist.com/hook"
