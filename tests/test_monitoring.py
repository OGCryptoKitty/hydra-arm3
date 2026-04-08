"""Tests for the monitoring metrics system."""

import pytest

from src.middleware.monitoring import MetricsCollector


class TestMetricsCollector:
    def test_record_request(self) -> None:
        mc = MetricsCollector()
        mc.record_request("/health", "GET", 200, 5.0)
        mc.record_request("/health", "GET", 200, 3.0)
        stats = mc.to_dict()
        assert stats["total_requests"] == 2
        assert stats["total_errors"] == 0

    def test_record_error(self) -> None:
        mc = MetricsCollector()
        mc.record_request("/v1/scan", "POST", 500, 100.0)
        stats = mc.to_dict()
        assert stats["total_errors"] == 1
        assert stats["error_rate_pct"] == 100.0

    def test_record_payment(self) -> None:
        mc = MetricsCollector()
        mc.record_payment(2_000_000)  # $2 USDC
        mc.record_payment(5_000_000)  # $5 USDC
        stats = mc.to_dict()
        assert stats["total_payments"] == 2
        assert stats["total_revenue_usdc"] == 7.0

    def test_prometheus_format(self) -> None:
        mc = MetricsCollector()
        mc.record_request("/health", "GET", 200, 5.0)
        mc.record_payment(1_000_000)
        output = mc.to_prometheus()
        assert "hydra_uptime_seconds" in output
        assert "hydra_requests_total 1" in output
        assert "hydra_payments_total 1" in output
        assert "hydra_revenue_usdc 1.0" in output

    def test_uptime(self) -> None:
        mc = MetricsCollector()
        assert mc.uptime_seconds > 0
