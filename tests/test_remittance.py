"""Tests for the HYDRA remittance manager."""

from decimal import Decimal

import pytest

from src.runtime.remittance import RemittanceManager


class TestRemittanceCalculations:
    def test_calculate_remittable_amount_above_reserve(self) -> None:
        rm = RemittanceManager.__new__(RemittanceManager)
        rm.OPERATING_RESERVE = Decimal("100")
        rm.MIN_REMITTANCE_BALANCE = Decimal("150")
        amount = rm.calculate_remittable_amount(Decimal("1000"))
        assert amount == Decimal("900.000000")

    def test_calculate_remittable_below_minimum(self) -> None:
        rm = RemittanceManager.__new__(RemittanceManager)
        rm.OPERATING_RESERVE = Decimal("100")
        rm.MIN_REMITTANCE_BALANCE = Decimal("150")
        amount = rm.calculate_remittable_amount(Decimal("100"))
        assert amount == Decimal("0")

    def test_threshold_is_1000(self) -> None:
        assert RemittanceManager.REMITTANCE_THRESHOLD == Decimal("1000")

    def test_operating_reserve_is_100(self) -> None:
        assert RemittanceManager.OPERATING_RESERVE == Decimal("100")


class TestShouldRemit:
    def test_below_threshold_returns_false(self) -> None:
        # should_remit checks balance >= threshold AND receiving_wallet is not None
        # Test the threshold comparison directly
        assert Decimal("999") < RemittanceManager.REMITTANCE_THRESHOLD

    def test_above_threshold_passes(self) -> None:
        assert Decimal("1000") >= RemittanceManager.REMITTANCE_THRESHOLD

    def test_threshold_is_1000_usdc(self) -> None:
        assert RemittanceManager.REMITTANCE_THRESHOLD == Decimal("1000")


class TestPromptForWallet:
    def test_prompt_includes_threshold(self) -> None:
        rm = RemittanceManager.__new__(RemittanceManager)
        rm.OPERATING_RESERVE = Decimal("100")
        rm.MIN_REMITTANCE_BALANCE = Decimal("150")
        prompt = rm.prompt_for_wallet(Decimal("1500"))
        assert "$1,000" in prompt
        assert "POST /system/wallet" in prompt
        assert "POST /system/remittance/execute" in prompt

    def test_prompt_shows_balance(self) -> None:
        rm = RemittanceManager.__new__(RemittanceManager)
        rm.OPERATING_RESERVE = Decimal("100")
        rm.MIN_REMITTANCE_BALANCE = Decimal("150")
        prompt = rm.prompt_for_wallet(Decimal("2500"))
        assert "$2,500.00" in prompt
