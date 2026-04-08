"""Tests for HTTPS redirect middleware."""

import pytest

from src.middleware.https_redirect import HTTPSRedirectMiddleware, ENFORCE_HTTPS


class TestHTTPSRedirectConfig:
    def test_enforce_https_defaults_false(self) -> None:
        """HTTPS enforcement should be disabled by default."""
        # The env var is not set in test, so it should be False
        assert ENFORCE_HTTPS is False
