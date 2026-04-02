"""Shared fixtures for HYDRA Arm 3 test suite."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect all state files to a temporary directory for test isolation."""
    state_dir = str(tmp_path / "hydra-state")
    os.makedirs(state_dir, exist_ok=True)
    monkeypatch.setenv("HYDRA_STATE_DIR", state_dir)
    monkeypatch.setenv("HYDRA_BOOTSTRAP_DIR", state_dir)


@pytest.fixture
def mock_web3():
    """Return a mocked Web3 instance."""
    with patch("web3.Web3") as mock:
        instance = MagicMock()
        mock.return_value = instance
        mock.to_checksum_address = lambda addr: addr
        mock.HTTPProvider = MagicMock()
        yield mock
