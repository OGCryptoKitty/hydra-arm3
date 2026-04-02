"""Tests for rate limiting middleware."""

import pytest

from src.middleware.rate_limit import (
    _classify_path,
    _is_rate_limited,
    _rate_windows,
)


class TestPathClassification:
    def test_system_path(self) -> None:
        assert _classify_path("/system/wallet") == "system"

    def test_paid_path(self) -> None:
        assert _classify_path("/v1/regulatory/scan") == "paid"

    def test_free_path(self) -> None:
        assert _classify_path("/health") == "free"
        assert _classify_path("/pricing") == "free"


class TestRateLimiting:
    def test_first_request_not_limited(self) -> None:
        # Use unique IP to avoid interference
        ip = "test_first_request_192.0.2.1"
        _rate_windows.clear()
        assert _is_rate_limited(ip, "free") is False

    def test_exceeds_limit(self) -> None:
        ip = "test_exceed_192.0.2.2"
        _rate_windows.clear()
        # Free limit is 60/min — make 60 requests
        for _ in range(60):
            _is_rate_limited(ip, "free")
        # 61st should be limited
        assert _is_rate_limited(ip, "free") is True

    def test_system_lower_limit(self) -> None:
        ip = "test_system_192.0.2.3"
        _rate_windows.clear()
        for _ in range(10):
            _is_rate_limited(ip, "system")
        assert _is_rate_limited(ip, "system") is True

    def test_different_ips_independent(self) -> None:
        _rate_windows.clear()
        ip1 = "test_indep_192.0.2.4"
        ip2 = "test_indep_192.0.2.5"
        # Exhaust ip1
        for _ in range(10):
            _is_rate_limited(ip1, "system")
        assert _is_rate_limited(ip1, "system") is True
        # ip2 should still be fine
        assert _is_rate_limited(ip2, "system") is False
