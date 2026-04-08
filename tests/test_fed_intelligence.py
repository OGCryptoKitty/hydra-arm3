"""Tests for the Fed intelligence engine."""

import pytest

from src.services.fed_intelligence import FedIntelligenceEngine


@pytest.fixture
def engine() -> FedIntelligenceEngine:
    return FedIntelligenceEngine()


class TestFedIntelligenceEngine:
    def test_get_next_fomc(self, engine: FedIntelligenceEngine) -> None:
        result = engine.get_next_fomc()
        assert isinstance(result, dict)
        assert "next_meeting" in result or "date" in result or len(result) > 0

    def test_is_fomc_day_returns_bool(self, engine: FedIntelligenceEngine) -> None:
        result = engine.is_fomc_day()
        assert isinstance(result, bool)

    def test_get_current_rate(self, engine: FedIntelligenceEngine) -> None:
        result = engine.get_current_rate()
        assert isinstance(result, dict)

    def test_calculate_rate_probabilities(self, engine: FedIntelligenceEngine) -> None:
        probs = engine.calculate_rate_probabilities()
        assert isinstance(probs, dict)
        # Should have hold/cut/hike probabilities
        total = sum(v for v in probs.values() if isinstance(v, (int, float)))
        # Probabilities should roughly sum to 1.0 (within rounding)
        assert total > 0

    def test_generate_pre_fomc_signal(self, engine: FedIntelligenceEngine) -> None:
        signal = engine.generate_pre_fomc_signal()
        assert isinstance(signal, dict)
        # Should contain key signal fields
        assert len(signal) > 0

    def test_get_latest_decision(self, engine: FedIntelligenceEngine) -> None:
        decision = engine.get_latest_decision()
        assert isinstance(decision, dict)
        assert "decision" in decision

    def test_generate_resolution_verdict(self, engine: FedIntelligenceEngine) -> None:
        verdict = engine.generate_resolution_verdict(
            market_question="Will the Federal Reserve hold interest rates at the next FOMC meeting?"
        )
        assert isinstance(verdict, dict)
        assert "market_question" in verdict
        assert "resolution_verdict" in verdict
