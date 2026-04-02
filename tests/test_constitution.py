"""Tests for the HYDRA constitutional compliance checks."""

from decimal import Decimal

import pytest

from src.runtime.constitution import ConstitutionCheck, ValidationResult


@pytest.fixture
def checker() -> ConstitutionCheck:
    return ConstitutionCheck()


class TestOFACScreening:
    def test_clean_address_passes(self, checker: ConstitutionCheck) -> None:
        ok, reason = checker.check_ofac("0x1234567890abcdef1234567890abcdef12345678")
        assert ok is True
        assert "cleared" in reason.lower()

    def test_sanctioned_address_blocked(self, checker: ConstitutionCheck) -> None:
        sanctioned = "0x8589427373D6D84E98730D7795D8f6f8731FDA16"
        ok, reason = checker.check_ofac(sanctioned)
        assert ok is False
        assert "OFAC" in reason

    def test_empty_address_rejected(self, checker: ConstitutionCheck) -> None:
        ok, reason = checker.check_ofac("")
        assert ok is False

    def test_case_insensitive_match(self, checker: ConstitutionCheck) -> None:
        sanctioned_lower = "0x8589427373d6d84e98730d7795d8f6f8731fda16"
        ok, _ = checker.check_ofac(sanctioned_lower)
        assert ok is False


class TestSolvencyCheck:
    def test_sufficient_balance_passes(self, checker: ConstitutionCheck) -> None:
        ok, reason = checker.check_solvency(Decimal("1000"), Decimal("400"))
        assert ok is True

    def test_insufficient_balance_blocked(self, checker: ConstitutionCheck) -> None:
        # post_balance = 600 - 200 = 400, which is < $500 reserve
        ok, reason = checker.check_solvency(Decimal("600"), Decimal("200"))
        assert ok is False
        assert "SOLVENCY" in reason

    def test_exact_reserve_passes(self, checker: ConstitutionCheck) -> None:
        ok, _ = checker.check_solvency(Decimal("1000"), Decimal("500"))
        assert ok is True  # 1000-500=500 == reserve


class TestValidateRemittance:
    def test_returns_validation_result(self, checker: ConstitutionCheck) -> None:
        result = checker.validate_remittance(
            "0x1234567890abcdef1234567890abcdef12345678",
            Decimal("100"),
            Decimal("1000"),
        )
        assert isinstance(result, ValidationResult)
        assert result.approved is True
        assert isinstance(result.checks, dict)

    def test_sanctioned_address_blocks(self, checker: ConstitutionCheck) -> None:
        result = checker.validate_remittance(
            "0x8589427373D6D84E98730D7795D8f6f8731FDA16",
            Decimal("100"),
            Decimal("1000"),
        )
        assert result.approved is False
        assert "LEGALITY" in result.reason

    def test_accepts_float_args(self, checker: ConstitutionCheck) -> None:
        result = checker.validate_remittance(
            "0x1234567890abcdef1234567890abcdef12345678",
            100.0,
            1000.0,
        )
        assert isinstance(result, ValidationResult)
        assert result.approved is True


class TestComplianceCalendar:
    def test_returns_list(self, checker: ConstitutionCheck) -> None:
        deadlines = checker.check_compliance()
        assert isinstance(deadlines, list)
        for item in deadlines:
            assert "description" in item
            assert "due_date" in item
            assert "days_until" in item
            assert "urgent" in item


class TestCheckLegality:
    def test_clean_address(self, checker: ConstitutionCheck) -> None:
        ok, reason = checker.check_legality("0xabcdef1234567890abcdef1234567890abcdef12", 0)
        assert ok is True

    def test_sanctioned_address(self, checker: ConstitutionCheck) -> None:
        ok, reason = checker.check_legality("0x8589427373D6D84E98730D7795D8f6f8731FDA16", 0)
        assert ok is False
