"""Tests for the regulatory intelligence service."""

import pytest

from src.services.regulatory import (
    analyze_regulatory_risk,
    answer_regulatory_query,
    compare_jurisdictions,
)
from src.models.schemas import BusinessType


class TestAnalyzeRegulatoryRisk:
    def test_crypto_exchange_high_risk(self) -> None:
        result = analyze_regulatory_risk(
            business_description=(
                "A platform allowing US retail investors to trade tokenized equities "
                "and cryptocurrency via a mobile app with wallet integration"
            ),
            jurisdiction="US",
        )
        assert result.overall_risk_score > 0
        assert len(result.applicable_regulations) > 0
        assert result.overall_risk_level is not None

    def test_low_risk_business(self) -> None:
        result = analyze_regulatory_risk(
            business_description=(
                "A software consulting firm providing cloud migration services "
                "to enterprise clients with no financial transactions"
            ),
            jurisdiction="US",
        )
        assert result.overall_risk_score < 50

    def test_returns_compliance_gaps(self) -> None:
        result = analyze_regulatory_risk(
            business_description=(
                "A DeFi protocol offering lending and borrowing of crypto assets "
                "with yield farming and staking to US and EU users"
            ),
            jurisdiction="US",
        )
        assert isinstance(result.key_compliance_gaps, list)
        assert isinstance(result.priority_actions, list)

    def test_eu_jurisdiction(self) -> None:
        result = analyze_regulatory_risk(
            business_description="A crypto exchange serving European Union customers with fiat onramp",
            jurisdiction="EU",
        )
        assert result.jurisdiction == "EU"

    def test_disclaimer_present(self) -> None:
        result = analyze_regulatory_risk(
            business_description="A fintech company offering payment processing for small businesses",
            jurisdiction="US",
        )
        assert "not constitute legal advice" in result.disclaimer


class TestCompareJurisdictions:
    def test_compare_us_states(self) -> None:
        result = compare_jurisdictions(
            jurisdictions=["WY", "DE", "NV"],
            business_type=BusinessType.CRYPTO,
        )
        assert len(result.profiles) > 0
        assert result.business_type == "crypto"

    def test_returns_recommendation(self) -> None:
        result = compare_jurisdictions(
            jurisdictions=["WY", "NY"],
            business_type=BusinessType.FINTECH,
        )
        assert isinstance(result.recommendation, str)
        assert len(result.recommendation) > 0


class TestAnswerRegulatoryQuery:
    def test_money_transmitter_question(self) -> None:
        result = answer_regulatory_query(
            question="Do I need a money transmitter license to operate a crypto exchange in Wyoming?"
        )
        assert isinstance(result.answer, str)
        assert len(result.answer) > 0
        assert result.confidence in ("high", "medium", "low")

    def test_returns_relevant_regulations(self) -> None:
        result = answer_regulatory_query(
            question="What are the SEC requirements for issuing a security token?"
        )
        assert isinstance(result.relevant_regulations, list)
        assert isinstance(result.relevant_agencies, list)

    def test_follow_up_questions(self) -> None:
        result = answer_regulatory_query(
            question="What is the Bank Secrecy Act and how does it apply to crypto?"
        )
        assert isinstance(result.follow_up_questions, list)
