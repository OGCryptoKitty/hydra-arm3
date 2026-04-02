"""Tests for x402 payment verification utilities."""

import pytest

from src.x402.verify import is_valid_tx_hash


class TestTxHashValidation:
    def test_valid_hash(self) -> None:
        valid = "0x" + "a" * 64
        assert is_valid_tx_hash(valid) is True

    def test_valid_hash_mixed_case(self) -> None:
        valid = "0x" + "aAbBcCdD" * 8
        assert is_valid_tx_hash(valid) is True

    def test_short_hash_rejected(self) -> None:
        assert is_valid_tx_hash("0xabc") is False

    def test_long_hash_rejected(self) -> None:
        assert is_valid_tx_hash("0x" + "a" * 65) is False

    def test_non_hex_rejected(self) -> None:
        assert is_valid_tx_hash("0x" + "g" * 64) is False

    def test_without_prefix(self) -> None:
        # Should auto-prepend 0x
        assert is_valid_tx_hash("a" * 64) is True

    def test_empty_rejected(self) -> None:
        assert is_valid_tx_hash("") is False

    def test_whitespace_stripped(self) -> None:
        assert is_valid_tx_hash("  0x" + "a" * 64 + "  ") is True
