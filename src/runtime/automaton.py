"""
automaton.py — HYDRA Self-Sustaining Autonomous Heartbeat Loop
==============================================================
Runs as an asyncio background task alongside FastAPI.
Monitors USDC balance, manages survival tiers, and drives
lifecycle phase transitions.

Bootstrap wallet : 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141
USDC on Base     : 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
Base RPC         : https://mainnet.base.org
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Optional

from web3 import Web3
from web3.exceptions import ContractLogicError

from .lifecycle import LifecycleManager, Phase

logger = logging.getLogger("hydra.automaton")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_DIR: Path = Path(os.getenv("HYDRA_STATE_DIR", os.getenv("HYDRA_BOOTSTRAP_DIR", "/app/data")))
STATE_FILE: Path = STATE_DIR / "state.json"
USDC_DECIMALS: int = 6
HEARTBEAT_INTERVAL: int = 60  # seconds

# Minimal ERC-20 ABI — only balanceOf is required
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SurvivalTier(Enum):
    """USDC balance tiers that govern spending behaviour."""

    CRITICAL = auto()   # < $100
    MINIMAL = auto()    # $100 – $499.99
    VIABLE = auto()     # $500 – $2,999.99
    FUNDED = auto()     # $3,000 – $4,999.99
    SURPLUS = auto()    # $5,000+


class AutomatonState(Enum):
    """High-level FSM states for the automaton."""

    BOOT = "BOOT"
    EARNING = "EARNING"
    FORMING = "FORMING"
    OPERATING = "OPERATING"
    REMITTING = "REMITTING"


# ---------------------------------------------------------------------------
# Tier thresholds (Decimal for exact arithmetic)
# ---------------------------------------------------------------------------

TIER_THRESHOLDS: list[tuple[Decimal, SurvivalTier]] = [
    (Decimal("5000"), SurvivalTier.SURPLUS),
    (Decimal("3000"), SurvivalTier.FUNDED),
    (Decimal("500"),  SurvivalTier.VIABLE),
    (Decimal("100"),  SurvivalTier.MINIMAL),
]


# ---------------------------------------------------------------------------
# HydraAutomaton
# ---------------------------------------------------------------------------


class HydraAutomaton:
    """
    Self-sustaining autonomous loop for HYDRA.

    Monitors USDC balance on Base, determines survival tier,
    manages lifecycle phase transitions, and persists state.

    Parameters
    ----------
    wallet_address : str
        Checksummed Ethereum wallet address to monitor.
    private_key : str
        Private key for the wallet (stored in memory only, never logged).
    base_rpc_url : str
        JSON-RPC endpoint for Base mainnet.
    usdc_address : str, optional
        USDC contract address on Base.
    receiving_wallet : str, optional
        Beneficiary wallet for profit remittances.
    """

    USDC_ADDRESS: str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

    def __init__(
        self,
        wallet_address: str,
        private_key: str,
        base_rpc_url: str,
        usdc_address: Optional[str] = None,
        receiving_wallet: Optional[str] = None,
    ) -> None:
        self.wallet_address: str = Web3.to_checksum_address(wallet_address)
        self._private_key: str = private_key  # never logged
        self.base_rpc_url: str = base_rpc_url
        self.usdc_address: str = Web3.to_checksum_address(
            usdc_address or self.USDC_ADDRESS
        )
        self.receiving_wallet: Optional[str] = (
            Web3.to_checksum_address(receiving_wallet) if receiving_wallet else None
        )

        # Web3 connection
        self.w3: Web3 = Web3(Web3.HTTPProvider(base_rpc_url))
        self.usdc_contract = self.w3.eth.contract(
            address=self.usdc_address, abi=ERC20_ABI
        )

        # Runtime state
        self._start_time: datetime = datetime.now(timezone.utc)
        self._last_heartbeat: Optional[datetime] = None
        self._cached_balance: Decimal = Decimal("0")
        self._automaton_state: AutomatonState = AutomatonState.BOOT
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

        # Lifecycle manager (loads phase from state.json)
        self.lifecycle: LifecycleManager = LifecycleManager()

        # Load persisted state
        self._load_state()

        logger.info(
            "HydraAutomaton initialised. Wallet=%s Phase=%s",
            self.wallet_address,
            self.lifecycle.current_phase.name,
        )

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """Load previously persisted automaton state from state.json."""
        if not STATE_FILE.exists():
            logger.info("No existing state.json — starting fresh.")
            return

        try:
            with STATE_FILE.open("r", encoding="utf-8") as fh:
                data: Dict[str, Any] = json.load(fh)

            cached_raw = data.get("cached_balance_usdc")
            if cached_raw is not None:
                self._cached_balance = Decimal(str(cached_raw))

            state_raw = data.get("automaton_state")
            if state_raw:
                try:
                    self._automaton_state = AutomatonState(state_raw)
                except ValueError:
                    logger.warning("Unknown automaton_state '%s' in state.json — using BOOT.", state_raw)

            receiving_raw = data.get("receiving_wallet")
            if receiving_raw and not self.receiving_wallet:
                self.receiving_wallet = Web3.to_checksum_address(receiving_raw)

            logger.info("State loaded from %s", STATE_FILE)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Could not load state.json (%s) — continuing with defaults.", exc)

    def _save_state(self) -> None:
        """Persist current automaton state to state.json."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {
            "wallet_address": self.wallet_address,
            "usdc_address": self.usdc_address,
            "cached_balance_usdc": str(self._cached_balance),
            "automaton_state": self._automaton_state.value,
            "phase": self.lifecycle.current_phase.value,
            "last_heartbeat": (
                self._last_heartbeat.isoformat() if self._last_heartbeat else None
            ),
            "receiving_wallet": self.receiving_wallet,
            "uptime_seconds": self._uptime_seconds(),
        }
        try:
            with STATE_FILE.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:
            logger.error("Failed to save state.json: %s", exc)

    # ------------------------------------------------------------------
    # Balance
    # ------------------------------------------------------------------

    async def get_usdc_balance(self) -> Decimal:
        """
        Query the USDC ERC-20 contract for the wallet balance.

        Returns Decimal denominated in USDC (6 decimals normalised).
        On RPC failure, returns the last cached balance and logs a warning.
        """
        try:
            raw: int = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.usdc_contract.functions.balanceOf(
                    self.wallet_address
                ).call(),
            )
            balance = Decimal(raw) / Decimal(10 ** USDC_DECIMALS)
            self._cached_balance = balance
            return balance
        except (ContractLogicError, Exception) as exc:  # noqa: BLE001
            logger.warning(
                "RPC failure querying USDC balance (%s). Using cached value: %s USDC",
                exc,
                self._cached_balance,
            )
            return self._cached_balance

    # ------------------------------------------------------------------
    # Tier logic
    # ------------------------------------------------------------------

    @staticmethod
    def get_survival_tier(balance: Decimal) -> SurvivalTier:
        """
        Map a USDC balance to its SurvivalTier.

        Parameters
        ----------
        balance : Decimal
            Current USDC balance.

        Returns
        -------
        SurvivalTier
        """
        for threshold, tier in TIER_THRESHOLDS:
            if balance >= threshold:
                return tier
        return SurvivalTier.CRITICAL

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def heartbeat(self) -> None:
        """
        Single heartbeat iteration.

        Executed every 60 seconds by :py:meth:`run`.

        Actions
        -------
        1. Query USDC balance.
        2. Determine SurvivalTier.
        3. Log timestamp, balance, tier, and phase.
        4. Fire remittance check when SURPLUS + receiving wallet configured.
        5. Log formation-ready notice when VIABLE+ and still in EARNING.
        6. Log CRITICAL warning when below $100.
        7. Evaluate lifecycle phase transition.
        8. Persist state.
        """
        now = datetime.now(timezone.utc)
        balance = await self.get_usdc_balance()
        tier = self.get_survival_tier(balance)
        phase = self.lifecycle.current_phase

        # ---- Core log ------------------------------------------------
        logger.info(
            "[HEARTBEAT] %s | Balance: $%s USDC | Tier: %s | Phase: %s",
            now.isoformat(),
            f"{balance:.2f}",
            tier.name,
            phase.name,
        )

        # ---- Tier-specific actions -----------------------------------
        if tier == SurvivalTier.CRITICAL:
            logger.warning(
                "CRITICAL: Balance below $100. Survival mode. "
                "All revenue retained. No outbound spending."
            )

        if tier >= SurvivalTier.VIABLE and phase == Phase.EARNING:
            logger.info(
                "Formation funding reached. Ready for entity formation sequence."
            )

        # Remittance check triggers at $1,000 USDC (VIABLE+)
        if balance >= Decimal("1000") and self.receiving_wallet:
            await self._remittance_check(balance)

        # ---- Lifecycle transition check ------------------------------
        entity_formed: bool = self.lifecycle.current_phase >= Phase.OPERATING
        self.lifecycle.check_transition(
            balance=balance,
            receiving_wallet_set=bool(self.receiving_wallet),
            entity_formed=entity_formed,
        )

        # ---- Update automaton FSM state ------------------------------
        self._automaton_state = self._derive_automaton_state(tier, phase)

        # ---- Persist -------------------------------------------------
        self._last_heartbeat = now
        self._save_state()

    def _derive_automaton_state(
        self, tier: SurvivalTier, phase: Phase
    ) -> AutomatonState:
        """Derive the AutomatonState from tier + lifecycle phase."""
        if phase == Phase.REMITTING:
            return AutomatonState.REMITTING
        if phase == Phase.OPERATING:
            return AutomatonState.OPERATING
        if phase == Phase.FORMING:
            return AutomatonState.FORMING
        if tier == SurvivalTier.CRITICAL and phase == Phase.BOOT:
            return AutomatonState.BOOT
        return AutomatonState.EARNING

    async def _remittance_check(self, balance: Decimal) -> None:
        """
        Log a remittance trigger event.

        Actual on-chain transfer is handled by a separate remittance
        module; this method records the trigger and updates state.
        """
        logger.info(
            "REMITTANCE TRIGGER: Balance $%s exceeds $1,000 threshold. "
            "Receiving wallet: %s. Awaiting owner confirmation to execute transfer.",
            f"{balance:.2f}",
            self.receiving_wallet,
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """
        Infinite heartbeat loop.

        Catches all exceptions so the automaton never crashes.
        Designed to run as an asyncio background task alongside FastAPI.

        Example
        -------
        ::

            automaton = HydraAutomaton(wallet, key, rpc_url)
            asyncio.create_task(automaton.run())
        """
        logger.info("HydraAutomaton run loop started.")
        self._running = True
        while self._running:
            try:
                await self.heartbeat()
            except asyncio.CancelledError:
                logger.info("HydraAutomaton heartbeat cancelled.")
                break
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Heartbeat exception (non-fatal, loop continues): %s", exc,
                    exc_info=True,
                )
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """
        Return a serialisable status snapshot.

        Returns
        -------
        dict
            Keys: balance, tier, phase, uptime_seconds, last_heartbeat,
            automaton_state, wallet_address, receiving_wallet.
        """
        tier = self.get_survival_tier(self._cached_balance)
        return {
            "wallet_address": self.wallet_address,
            "balance_usdc": str(self._cached_balance),
            "tier": tier.name,
            "phase": self.lifecycle.current_phase.name,
            "automaton_state": self._automaton_state.value,
            "uptime_seconds": self._uptime_seconds(),
            "last_heartbeat": (
                self._last_heartbeat.isoformat() if self._last_heartbeat else None
            ),
            "receiving_wallet": self.receiving_wallet,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        """Stop the automaton heartbeat loop gracefully."""
        self._running = False
        if hasattr(self, "_task") and self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("HydraAutomaton stopped.")

    def _uptime_seconds(self) -> float:
        """Return seconds since the automaton was initialised."""
        return (datetime.now(timezone.utc) - self._start_time).total_seconds()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_automaton_instance: Optional[HydraAutomaton] = None


def get_automaton() -> HydraAutomaton:
    """
    Return the module-level singleton HydraAutomaton instance.

    Creates a new instance with env-var defaults if none exists.
    Used by system_routes and main to share a single automaton.
    """
    global _automaton_instance
    if _automaton_instance is None:
        import config.settings as settings
        pk = os.getenv("WALLET_PRIVATE_KEY", "")
        _automaton_instance = HydraAutomaton(
            wallet_address=settings.WALLET_ADDRESS,
            private_key=pk,
            base_rpc_url=settings.BASE_RPC_URL,
        )
    return _automaton_instance


def set_automaton(instance: HydraAutomaton) -> None:
    """Set the module-level singleton (called from lifespan startup)."""
    global _automaton_instance
    _automaton_instance = instance
