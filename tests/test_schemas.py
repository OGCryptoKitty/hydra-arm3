"""Tests for Pydantic request/response schemas."""

import pytest
from pydantic import ValidationError

from src.models.schemas import (
    JurisdictionRequest,
    PaymentVerificationResult,
    RegulatoryChangesRequest,
    RegulatoryQueryRequest,
    RegulatoryScenRequest,
)


class TestRegulatoryScenRequest:
    def test_valid_request(self) -> None:
        req = RegulatoryScenRequest(
            business_description="A platform allowing US retail investors to trade tokenized equities via a mobile app",
        )
        assert req.jurisdiction == "US"

    def test_too_short_description_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RegulatoryScenRequest(business_description="short")

    def test_custom_jurisdiction(self) -> None:
        req = RegulatoryScenRequest(
            business_description="A platform allowing US retail investors to trade tokenized equities via a mobile app",
            jurisdiction="EU",
        )
        assert req.jurisdiction == "EU"


class TestJurisdictionRequest:
    def test_normalizes_to_uppercase(self) -> None:
        req = JurisdictionRequest(
            jurisdictions=["wy", "de"],
            business_type="crypto",
        )
        assert req.jurisdictions == ["WY", "DE"]

    def test_empty_jurisdictions_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JurisdictionRequest(jurisdictions=[], business_type="crypto")


class TestRegulatoryChangesRequest:
    def test_defaults(self) -> None:
        req = RegulatoryChangesRequest()
        assert req.agency.value == "all"
        assert req.days == 30

    def test_days_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            RegulatoryChangesRequest(days=200)


class TestRegulatoryQueryRequest:
    def test_valid(self) -> None:
        req = RegulatoryQueryRequest(
            question="Do I need a money transmitter license in Wyoming?"
        )
        assert "money transmitter" in req.question

    def test_too_short(self) -> None:
        with pytest.raises(ValidationError):
            RegulatoryQueryRequest(question="help?")


class TestPaymentVerificationResult:
    def test_verified(self) -> None:
        result = PaymentVerificationResult(
            verified=True,
            tx_hash="0x123",
            amount_received_base_units=1000000,
            amount_required_base_units=1000000,
        )
        assert result.verified is True

    def test_failed(self) -> None:
        result = PaymentVerificationResult(
            verified=False,
            tx_hash="0x456",
            error="Insufficient payment",
        )
        assert result.verified is False
        assert result.error is not None
