"""Tests for retry utilities."""

import pytest

from src.utils.retry import retry_sync


class TestRetrySync:
    def test_succeeds_first_try(self) -> None:
        call_count = 0

        @retry_sync(max_retries=3, base_delay=0.01)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count == 1

    def test_retries_on_failure(self) -> None:
        call_count = 0

        @retry_sync(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient")
            return "ok"

        assert fail_then_succeed() == "ok"
        assert call_count == 3

    def test_exhausts_retries(self) -> None:
        @retry_sync(max_retries=2, base_delay=0.01, exceptions=(ValueError,))
        def always_fail():
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            always_fail()

    def test_does_not_catch_unspecified_exceptions(self) -> None:
        @retry_sync(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        def raise_type_error():
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            raise_type_error()
