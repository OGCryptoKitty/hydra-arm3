"""Tests for the HYDRA transaction log."""

from decimal import Decimal
from pathlib import Path

import pytest

from src.runtime.transaction_log import TransactionLog, TxCategory, TxDirection


@pytest.fixture
def tx_log(tmp_path: Path) -> TransactionLog:
    return TransactionLog(log_file=tmp_path / "test_transactions.jsonl")


class TestTransactionLog:
    def test_log_inbound(self, tx_log: TransactionLog) -> None:
        tx_log.log_inbound(
            tx_hash="0xabc123",
            amount_usdc=Decimal("5.00"),
            from_address="0x1234567890abcdef1234567890abcdef12345678",
        )
        records = tx_log.get_transactions()
        assert len(records) == 1
        assert records[0]["direction"] == "inbound"
        assert records[0]["category"] == "x402-revenue"
        assert records[0]["amount_usdc"] == "5.000000"

    def test_log_outbound(self, tx_log: TransactionLog) -> None:
        tx_log.log_outbound(
            tx_hash="0xdef456",
            amount_usdc=Decimal("900.00"),
            to_address="0xabcdef1234567890abcdef1234567890abcdef12",
            category="member-distribution",
        )
        records = tx_log.get_transactions()
        assert len(records) == 1
        assert records[0]["direction"] == "outbound"
        assert records[0]["category"] == "member-distribution"

    def test_invalid_outbound_category_raises(self, tx_log: TransactionLog) -> None:
        with pytest.raises(ValueError, match="Invalid outbound category"):
            tx_log.log_outbound(
                tx_hash="0x000",
                amount_usdc=Decimal("1"),
                to_address="0x000",
                category="invalid-category",
            )

    def test_filter_by_direction(self, tx_log: TransactionLog) -> None:
        tx_log.log_inbound("0xa", Decimal("10"), "0x1111111111111111111111111111111111111111")
        tx_log.log_outbound("0xb", Decimal("5"), "0x2222222222222222222222222222222222222222", "member-distribution")
        inbound = tx_log.get_transactions(direction="inbound")
        assert len(inbound) == 1
        assert inbound[0]["tx_hash"] == "0xa"

    def test_get_entries_with_enums(self, tx_log: TransactionLog) -> None:
        tx_log.log_inbound("0xa", Decimal("10"), "0x1111111111111111111111111111111111111111")
        entries = tx_log.get_entries(direction=TxDirection.INBOUND)
        assert len(entries) == 1

    def test_get_full_summary(self, tx_log: TransactionLog) -> None:
        tx_log.log_inbound("0xa", Decimal("100"), "0x1111111111111111111111111111111111111111")
        tx_log.log_inbound("0xb", Decimal("50"), "0x2222222222222222222222222222222222222222")
        tx_log.log_outbound("0xc", Decimal("30"), "0x3333333333333333333333333333333333333333", "member-distribution")
        summary = tx_log.get_full_summary()
        assert Decimal(summary["total_revenue_usdc"]) == Decimal("150.00")
        assert Decimal(summary["total_distributions_usdc"]) == Decimal("30.00")
        assert summary["transaction_count"] == 3

    def test_log_generic(self, tx_log: TransactionLog) -> None:
        tx_log.log(
            tx_hash="0xgeneric",
            direction=TxDirection.OUTBOUND,
            category=TxCategory.MEMBER_DISTRIBUTION,
            amount_usdc=500.0,
            counterparty_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            note="test remittance",
        )
        records = tx_log.get_transactions()
        assert len(records) == 1
        assert records[0]["note"] == "test remittance"

    def test_empty_log_returns_empty(self, tx_log: TransactionLog) -> None:
        assert tx_log.get_transactions() == []
        summary = tx_log.get_full_summary()
        assert summary["transaction_count"] == 0


class TestTaxSummary:
    def test_generate_for_year(self, tx_log: TransactionLog) -> None:
        tx_log.log_inbound("0xa", Decimal("1000"), "0x1111111111111111111111111111111111111111")
        summary = tx_log.generate_tax_summary(2026)
        assert "total_revenue" in summary
        assert int(summary["transaction_count"]) >= 0
