"""Tests for the HYDRA lifecycle phase manager."""

from decimal import Decimal

import pytest

from src.runtime.lifecycle import LifecycleManager, Phase


def _fresh_lm() -> LifecycleManager:
    """Create a fresh LifecycleManager that always starts at BOOT."""
    lm = LifecycleManager()
    lm._phase = Phase.BOOT  # Reset regardless of persisted state
    return lm


class TestPhaseTransitions:
    def test_starts_at_boot(self) -> None:
        lm = _fresh_lm()
        assert lm.current_phase == Phase.BOOT

    def test_boot_to_earning(self) -> None:
        lm = _fresh_lm()
        result = lm.check_transition(
            balance=Decimal("1.00"),
            receiving_wallet_set=False,
            entity_formed=False,
        )
        assert result == Phase.EARNING
        assert lm.current_phase == Phase.EARNING

    def test_earning_to_forming(self) -> None:
        lm = _fresh_lm()
        lm._phase = Phase.EARNING
        result = lm.check_transition(
            balance=Decimal("3000"),
            receiving_wallet_set=False,
            entity_formed=False,
        )
        assert result == Phase.FORMING

    def test_forming_to_operating(self) -> None:
        lm = _fresh_lm()
        lm._phase = Phase.FORMING
        result = lm.check_transition(
            balance=Decimal("5000"),
            receiving_wallet_set=False,
            entity_formed=True,
        )
        assert result == Phase.OPERATING

    def test_operating_to_remitting(self) -> None:
        lm = _fresh_lm()
        lm._phase = Phase.OPERATING
        result = lm.check_transition(
            balance=Decimal("5000"),
            receiving_wallet_set=True,
            entity_formed=True,
        )
        assert result == Phase.REMITTING

    def test_no_backward_phase(self) -> None:
        lm = _fresh_lm()
        lm._phase = Phase.FORMING
        lm.advance_phase(Phase.EARNING)  # Should be ignored (backward)
        assert lm.current_phase == Phase.FORMING

    def test_no_transition_returns_none(self) -> None:
        lm = _fresh_lm()
        result = lm.check_transition(
            balance=Decimal("0"),
            receiving_wallet_set=False,
            entity_formed=False,
        )
        assert result is None


class TestGetState:
    def test_returns_dict(self) -> None:
        lm = _fresh_lm()
        state = lm.get_state()
        assert isinstance(state, dict)
        assert state["phase"] == Phase.BOOT.value
        assert state["phase_label"] == "BOOT"
        assert state["entity_formed"] is False

    def test_operating_shows_entity_formed(self) -> None:
        lm = _fresh_lm()
        lm._phase = Phase.OPERATING
        state = lm.get_state()
        assert state["entity_formed"] is True


class TestOnReceivingWalletSet:
    def test_advances_from_operating(self) -> None:
        lm = _fresh_lm()
        lm._phase = Phase.OPERATING
        result = lm.on_receiving_wallet_set()
        assert result == Phase.REMITTING

    def test_no_advance_from_earning(self) -> None:
        lm = _fresh_lm()
        lm._phase = Phase.EARNING
        result = lm.on_receiving_wallet_set()
        assert result is None


class TestPhaseInstructions:
    def test_returns_string(self) -> None:
        lm = _fresh_lm()
        instructions = lm.get_phase_instructions()
        assert isinstance(instructions, str)
        assert len(instructions) > 0


class TestAddNote:
    def test_add_note_does_not_crash(self) -> None:
        lm = _fresh_lm()
        lm.add_note("test note")
