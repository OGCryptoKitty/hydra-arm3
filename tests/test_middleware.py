"""Tests for x402 payment middleware replay prevention."""

import time

from src.x402.middleware import _is_tx_used, _mark_tx_used


class TestReplayPrevention:
    def test_unused_tx_returns_false(self) -> None:
        assert _is_tx_used("0x_fresh_hash_" + str(time.time())) is False

    def test_used_tx_returns_true(self) -> None:
        tx = "0x_test_used_" + str(time.time())
        _mark_tx_used(tx)
        assert _is_tx_used(tx) is True

    def test_case_insensitive(self) -> None:
        tx = "0xABCDEF" + str(time.time())
        _mark_tx_used(tx)
        assert _is_tx_used(tx.lower()) is True
