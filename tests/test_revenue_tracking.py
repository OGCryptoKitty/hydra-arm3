"""Tests for revenue tracking integration."""

import pytest
from decimal import Decimal
from pathlib import Path

from src.runtime.transaction_log import TransactionLog


class TestRevenueTracking:
    def test_log_inbound_creates_record(self, tmp_path: Path) -> None:
        """Verify that log_inbound writes a parseable revenue record."""
        tl = TransactionLog(log_file=tmp_path / "tx.jsonl")
        tl.log_inbound(
            tx_hash="0xabc123",
            amount_usdc=Decimal("2.00"),
            from_address="0x1234567890abcdef1234567890abcdef12345678",
            category="x402-revenue",
            note="x402 payment for /v1/regulatory/scan",
        )
        entries = tl.get_transactions(direction="inbound")
        assert len(entries) == 1
        assert entries[0]["category"] == "x402-revenue"
        assert entries[0]["amount_usdc"] == "2.000000"
        assert entries[0]["note"] == "x402 payment for /v1/regulatory/scan"

    def test_revenue_summary_aggregates(self, tmp_path: Path) -> None:
        """Multiple inbound payments should sum correctly."""
        tl = TransactionLog(log_file=tmp_path / "tx.jsonl")
        for i in range(5):
            tl.log_inbound(
                tx_hash=f"0x{i:064x}",
                amount_usdc=Decimal("10.00"),
                from_address="0x1234567890abcdef1234567890abcdef12345678",
            )
        summary = tl.get_full_summary()
        assert summary["total_revenue_usdc"] == "50.00"
        assert summary["transaction_count"] == 5
