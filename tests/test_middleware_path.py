"""Tests for x402 middleware path matching with parameters."""

import pytest

from config.settings import PRICING


class TestPricingPathCoverage:
    """Ensure all declared paid endpoints have pricing entries."""

    def test_regulatory_endpoints_priced(self) -> None:
        assert "/v1/regulatory/scan" in PRICING
        assert "/v1/regulatory/changes" in PRICING
        assert "/v1/regulatory/jurisdiction" in PRICING
        assert "/v1/regulatory/query" in PRICING

    def test_fed_endpoints_priced(self) -> None:
        assert "/v1/fed/signal" in PRICING
        assert "/v1/fed/decision" in PRICING
        assert "/v1/fed/resolution" in PRICING

    def test_market_endpoints_priced(self) -> None:
        assert "/v1/markets/feed" in PRICING
        assert "/v1/markets/events" in PRICING
        assert "/v1/markets/signal" in PRICING
        assert "/v1/markets/signals" in PRICING
        assert "/v1/markets/alpha" in PRICING

    def test_oracle_endpoints_priced(self) -> None:
        assert "/v1/oracle/uma" in PRICING
        assert "/v1/oracle/chainlink" in PRICING

    def test_all_prices_have_required_fields(self) -> None:
        for path, pricing in PRICING.items():
            assert "amount_usdc" in pricing, f"Missing amount_usdc for {path}"
            assert "amount_base_units" in pricing, f"Missing amount_base_units for {path}"
            assert "description" in pricing, f"Missing description for {path}"
            assert pricing["amount_base_units"] > 0, f"Invalid price for {path}"


class TestPathParameterMatching:
    """Test that path-parameter endpoints are correctly matched by middleware prefix logic."""

    def test_signal_with_market_id_matches(self) -> None:
        """Middleware should match /v1/markets/signal/abc123 to /v1/markets/signal."""
        path = "/v1/markets/signal/polymarket-12345"
        # Simulate middleware prefix matching logic
        matched = None
        for pricing_path in PRICING:
            if path.startswith(pricing_path + "/") or path == pricing_path:
                matched = pricing_path
                break
        assert matched == "/v1/markets/signal"

    def test_exact_path_still_matches(self) -> None:
        path = "/v1/regulatory/scan"
        assert path in PRICING
