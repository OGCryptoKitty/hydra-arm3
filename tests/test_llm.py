"""Tests for the LLM intelligence layer."""

import pytest
from unittest.mock import patch, MagicMock

from src.services.llm import (
    is_llm_available,
    _call_llm_json,
    _format_dict,
    _format_list,
)


class TestLLMHelpers:
    def test_format_dict(self) -> None:
        result = _format_dict({"rate": "4.5%", "direction": "HOLD"})
        assert "rate: 4.5%" in result
        assert "direction: HOLD" in result

    def test_format_list(self) -> None:
        result = _format_list(["item 1", "item 2"])
        assert "1. item 1" in result
        assert "2. item 2" in result

    def test_format_list_empty(self) -> None:
        result = _format_list([])
        assert "none available" in result

    def test_llm_not_available_without_key(self) -> None:
        with patch("src.services.llm.ANTHROPIC_API_KEY", ""):
            # Reset client
            import src.services.llm as llm_mod
            llm_mod._client = None
            assert is_llm_available() is False

    def test_call_llm_json_returns_none_without_key(self) -> None:
        with patch("src.services.llm.ANTHROPIC_API_KEY", ""):
            import src.services.llm as llm_mod
            llm_mod._client = None
            result = _call_llm_json("system", "user")
            assert result is None


class TestLLMJsonParsing:
    def test_parse_valid_json(self) -> None:
        """Test that _call_llm_json correctly strips markdown fences."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='```json\n{"key": "value"}\n```')]
        mock_client.messages.create.return_value = mock_response

        with patch("src.services.llm._get_client", return_value=mock_client):
            result = _call_llm_json("system", "user")
            assert result == {"key": "value"}

    def test_parse_plain_json(self) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"score": 85}')]
        mock_client.messages.create.return_value = mock_response

        with patch("src.services.llm._get_client", return_value=mock_client):
            result = _call_llm_json("system", "user")
            assert result == {"score": 85}

    def test_parse_invalid_json_returns_none(self) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is not JSON")]
        mock_client.messages.create.return_value = mock_response

        with patch("src.services.llm._get_client", return_value=mock_client):
            result = _call_llm_json("system", "user")
            assert result is None
