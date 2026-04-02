"""
lifecycle.py — HYDRA Phase Manager
====================================
Manages the five phases of HYDRA's autonomous lifecycle:
BOOT → EARNING → FORMING → OPERATING → REMITTING

Phase transitions are persisted to state.json and logged for audit.
"""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("hydra.lifecycle")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_DIR: Path = Path(os.getenv("HYDRA_STATE_DIR", os.getenv("HYDRA_BOOTSTRAP_DIR", "/app/data")))
STATE_FILE: Path = STATE_DIR / "state.json"

FORMATION_THRESHOLD: Decimal = Decimal("3000")  # VIABLE tier minimum for forming


# ---------------------------------------------------------------------------
# Phase enum
# ---------------------------------------------------------------------------


class Phase(IntEnum):
    """
    HYDRA lifecycle phases.

    IntEnum allows ordered comparison (e.g. phase >= Phase.FORMING).
    """

    BOOT = 0
    EARNING = 1
    FORMING = 2
    OPERATING = 3
    REMITTING = 4


# ---------------------------------------------------------------------------
# LifecycleManager
# ---------------------------------------------------------------------------


class LifecycleManager:
    """
    Manages HYDRA's autonomous lifecycle phases.

    Loads the current phase from state.json on init, evaluates
    transition conditions each heartbeat, and persists changes.

    Phase progression
    -----------------
    BOOT      → Wallet exists, server running.
    EARNING   → First x402 payment received; accumulating balance.
    FORMING   → Balance >= $3,000; entity formation sequence available.
    OPERATING → Entity formed, EIN obtained, CSP engaged (config flag).
    REMITTING → Operating + receiving wallet configured.
    """

    def __init__(self) -> None:
        self._phase: Phase = Phase.BOOT
        self._load_phase()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_phase(self) -> Phase:
        """The current lifecycle phase."""
        return self._phase

    # ------------------------------------------------------------------
    # State I/O
    # ------------------------------------------------------------------

    def _load_phase(self) -> None:
        """Read phase from state.json, defaulting to BOOT if absent."""
        if not STATE_FILE.exists():
            logger.info("state.json not found — defaulting to Phase.BOOT.")
            return

        try:
            with STATE_FILE.open("r", encoding="utf-8") as fh:
                data: Dict[str, Any] = json.load(fh)
            phase_raw = data.get("phase")
            if phase_raw is not None:
                self._phase = Phase(int(phase_raw))
                logger.info("Loaded phase %s from state.json", self._phase.name)
        except (json.JSONDecodeError, OSError, ValueError, KeyError) as exc:
            logger.warning("Could not read phase from state.json (%s) — defaulting to BOOT.", exc)

    def _persist_phase(self) -> None:
        """Merge phase into state.json, preserving all other keys."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {}
        if STATE_FILE.exists():
            try:
                with STATE_FILE.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass  # Start fresh if corrupt

        data["phase"] = self._phase.value
        try:
            with STATE_FILE.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:
            logger.error("Failed to persist phase: %s", exc)

    # ------------------------------------------------------------------
    # Transition logic
    # ------------------------------------------------------------------

    def check_transition(
        self,
        balance: Decimal,
        receiving_wallet_set: bool,
        entity_formed: bool,
    ) -> Optional[Phase]:
        """
        Evaluate whether the phase should advance and do so if warranted.

        Only ever advances — never retreats — phases.

        Parameters
        ----------
        balance : Decimal
            Current USDC balance.
        receiving_wallet_set : bool
            True if a receiving wallet address is configured.
        entity_formed : bool
            True if entity is formed and EIN obtained (set by config flag).

        Returns
        -------
        Phase or None
            The new phase if a transition occurred, else None.
        """
        new_phase: Optional[Phase] = None

        if self._phase == Phase.BOOT:
            # Advance to EARNING once first revenue is detected (balance > 0)
            if balance > Decimal("0"):
                new_phase = Phase.EARNING

        elif self._phase == Phase.EARNING:
            if balance >= FORMATION_THRESHOLD:
                new_phase = Phase.FORMING

        elif self._phase == Phase.FORMING:
            if entity_formed:
                new_phase = Phase.OPERATING

        elif self._phase == Phase.OPERATING:
            if receiving_wallet_set:
                new_phase = Phase.REMITTING

        if new_phase is not None:
            self.advance_phase(new_phase)
            return new_phase
        return None

    def advance_phase(self, new_phase: Phase) -> None:
        """
        Advance to a new phase, persist, and log the transition.

        Parameters
        ----------
        new_phase : Phase
            The phase to advance to. Must be greater than current phase.
        """
        if new_phase <= self._phase:
            logger.warning(
                "Attempted to advance from %s to %s — ignored (must be forward progression).",
                self._phase.name,
                new_phase.name,
            )
            return

        old_phase = self._phase
        self._phase = new_phase
        self._persist_phase()
        logger.info(
            "PHASE TRANSITION: %s → %s",
            old_phase.name,
            new_phase.name,
        )

    # ------------------------------------------------------------------
    # Instructions
    # ------------------------------------------------------------------

    def get_phase_instructions(self, balance: Optional[Decimal] = None) -> str:
        """
        Return human-readable instructions for the current phase.

        Parameters
        ----------
        balance : Decimal, optional
            Current USDC balance used to interpolate EARNING instructions.

        Returns
        -------
        str
            Actionable instructions for the current phase.
        """
        balance_str = f"${balance:.2f}" if balance is not None else "unknown"

        instructions: dict[Phase, str] = {
            Phase.BOOT: (
                "Server running. Awaiting first x402 revenue. "
                "Share API endpoint to generate traffic."
            ),
            Phase.EARNING: (
                f"Revenue accumulating. Current balance: {balance_str}. "
                "Formation threshold: $3,000. Continue operating."
            ),
            Phase.FORMING: (
                "Formation funding reached. Execute: "
                "1) OtoCo ParentCo formation, "
                "2) CSP engagement, "
                "3) Wyoming OpCo filing, "
                "4) SS-4 fax for EIN. "
                "See /hydra-bootstrap/formation/ for all documents."
            ),
            Phase.OPERATING: (
                "Entity active. EIN obtained. CSP managing. Revenue flowing. "
                "Awaiting receiving wallet address for profit remittance."
            ),
            Phase.REMITTING: (
                "Fully operational. Remittance prompts at every $1,000 USDC "
                "to your configured receiving wallet. Execute transfer via "
                "POST /system/remittance/execute when prompted."
            ),
        }

        return instructions.get(self._phase, "Unknown phase.")

    # ------------------------------------------------------------------
    # State introspection
    # ------------------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of the lifecycle state."""
        data: Dict[str, Any] = {
            "phase": self._phase.value,
            "phase_label": self._phase.name,
            "entity_formed": self._phase >= Phase.OPERATING,
            "ein_obtained": self._phase >= Phase.OPERATING,
            "csp_engaged": self._phase >= Phase.OPERATING,
        }
        # Load timestamps from state.json if available
        if STATE_FILE.exists():
            try:
                with STATE_FILE.open("r", encoding="utf-8") as fh:
                    persisted = json.load(fh)
                data["formation_started_at"] = persisted.get("formation_started_at")
                data["operating_since"] = persisted.get("operating_since")
                data["remitting_since"] = persisted.get("remitting_since")
            except (json.JSONDecodeError, OSError):
                pass
        return data

    def on_receiving_wallet_set(self) -> Optional[Phase]:
        """Advance to REMITTING when a receiving wallet is configured (if in OPERATING)."""
        if self._phase == Phase.OPERATING:
            self.advance_phase(Phase.REMITTING)
            return Phase.REMITTING
        return None

    def add_note(self, note: str) -> None:
        """Persist an informational note to state.json."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {}
        if STATE_FILE.exists():
            try:
                with STATE_FILE.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass
        notes = data.get("notes", [])
        notes.append(note)
        data["notes"] = notes[-50:]  # Keep last 50 notes
        try:
            with STATE_FILE.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:
            logger.error("Failed to add note: %s", exc)
