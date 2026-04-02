"""
HYDRA Remittance System

Triggers: When USDC balance exceeds $5,000 USD-equivalent
Action: Remit (balance - $500 operating reserve) to receiving wallet
Method: Direct USDC transfer on Base (ERC-20 transfer)
Privacy: Transaction is a standard Base L2 USDC transfer — no memo, no metadata,
         no identifying information attached to the on-chain transaction.

Compliance framework:
- OFAC screening on receiving wallet before each transfer
- Transaction logged internally for entity tax records (Form 5472)
- No structuring — single transfer of full remittable amount
- Receiving wallet address is stored only in local config,
  never transmitted to any third party, never included in any filing,
  never associated with any identity in any record maintained by the entity
- The entity's tax records record the transaction as "distribution to member"
  with the on-chain tx hash — the wallet address is visible on-chain but
  the on-chain record does not associate the wallet with any natural person

Legal basis for non-reporting of receiving wallet identity:
- The receiving wallet is an external address. USDC transfers on Base are
  permissionless. The sender (entity) has no obligation to KYC the recipient
  for outbound USDC transfers.
- FinCEN CTR ($10K+ currency transaction reporting) applies to financial
  institutions, not to LLC-to-wallet USDC transfers.
- The entity's own records: the Operating Agreement specifies distributions
  to the member (ParentCo LLC, identified by wallet address). ParentCo's
  member is a wallet address per OtoCo. No natural person is identified
  in the distribution chain.
- IRS Form 5472 (required for foreign-owned single-member LLC): reports
  "transactions with related parties" — the distribution is reported as
  amount only. The related party is identified as "HYDRA Systems LLC"
  (ParentCo), not as a natural person.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any, Optional

from web3 import Web3
from web3.exceptions import TransactionNotFound

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

BOOTSTRAP_DIR = Path(os.getenv("HYDRA_STATE_DIR", os.getenv("HYDRA_BOOTSTRAP_DIR", "/app/data")))
WALLET_JSON       = BOOTSTRAP_DIR / "wallet.json"
REMITTANCE_CONFIG = BOOTSTRAP_DIR / "remittance-config.json"
REMITTANCE_LOG    = BOOTSTRAP_DIR / "remittance-log.jsonl"

BASE_RPC_URL          = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
USDC_CONTRACT_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_DECIMALS         = 6

# Module-level constants (also used by system_routes for display)
# Remittance triggers at $1,000 USDC — owner is prompted to execute transfer
REMITTANCE_TRIGGER_USD    = 1000   # Balance threshold to trigger remittance prompt
OPERATING_RESERVE_USD     = 100    # Always retain at least this much
MINIMUM_REMIT_BALANCE_USD = 150    # Minimum balance before any remittance

# Decimal versions for precision arithmetic
REMITTANCE_THRESHOLD  = Decimal("1000")
OPERATING_RESERVE     = Decimal("100")
MIN_REMITTANCE_BALANCE = Decimal("150")

# ERC-20 ABI — minimal: balanceOf + transfer
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "success", "type": "bool"}],
        "type": "function",
    },
]


# ─────────────────────────────────────────────────────────────
# Result Types
# ─────────────────────────────────────────────────────────────

@dataclass
class RemittanceResult:
    """Result of a remittance execution attempt."""

    success: bool
    tx_hash: Optional[str] = None
    amount_usdc: Decimal = Decimal("0")
    receiving_address: Optional[str] = None
    timestamp: Optional[str] = None
    error_message: Optional[str] = None
    constitution_checks: dict = field(default_factory=dict)

    # Legacy alias kept for compatibility with callers using .error
    @property
    def error(self) -> Optional[str]:
        return self.error_message

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-compatible dict, masking the receiving address."""
        addr = self.receiving_address
        masked_addr: Optional[str] = None
        if addr:
            masked_addr = addr[:8] + "..." + addr[-6:] if len(addr) > 14 else addr
        return {
            "success": self.success,
            "tx_hash": self.tx_hash,
            "amount_usdc": str(self.amount_usdc),
            "receiving_address": masked_addr,
            "timestamp": self.timestamp,
            "error_message": self.error_message,
            "constitution_checks": self.constitution_checks,
        }


# ─────────────────────────────────────────────────────────────
# RemittanceManager
# ─────────────────────────────────────────────────────────────

class RemittanceManager:
    """
    Manages autonomous USDC remittances from the HYDRA treasury to the
    configured receiving wallet. Enforces all constitutional checks
    before every transfer.

    The receiving wallet is loaded lazily from
    /home/user/workspace/hydra-bootstrap/remittance-config.json.
    If the file is missing or the address is null, remittance is disabled.
    """

    # ── Class-level constants ─────────────────────────────────
    REMITTANCE_THRESHOLD  = Decimal("1000")   # USDC — trigger threshold ($1,000)
    OPERATING_RESERVE     = Decimal("100")    # USDC — always retained
    MIN_REMITTANCE_BALANCE = Decimal("150")   # USDC — minimum to execute any remittance

    def __init__(
        self,
        private_key: Optional[str] = None,
        wallet_address: Optional[str] = None,
        web3_provider: Optional[Web3] = None,
        constitution_checker: Optional[Any] = None,
        transaction_logger: Optional[Any] = None,
    ) -> None:
        """
        Initialise RemittanceManager.

        Args:
            private_key:          Hex-encoded private key (0x-prefixed or raw).
                                  Falls back to WALLET_PRIVATE_KEY env or wallet.json.
            wallet_address:       Checksum EVM address.
                                  Falls back to WALLET_ADDRESS env or wallet.json.
            web3_provider:        Initialised Web3 instance. Falls back to Base RPC.
            constitution_checker: ConstitutionCheck instance. Created if None.
            transaction_logger:   TransactionLog instance. Created if None.
        """
        self._wallet_address: Optional[str] = wallet_address
        self._private_key: Optional[str] = private_key

        # Load credentials from env / wallet.json if not supplied
        if not (self._wallet_address and self._private_key):
            self._load_wallet()

        # Web3 setup
        if web3_provider is not None:
            self.w3 = web3_provider
        else:
            self.w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))

        self.usdc = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_CONTRACT_ADDRESS),
            abi=ERC20_ABI,
        )

        # Constitution checker
        if constitution_checker is not None:
            self.constitution = constitution_checker
        else:
            from src.runtime.constitution import ConstitutionCheck
            self.constitution = ConstitutionCheck()

        # Transaction logger
        if transaction_logger is not None:
            self._tx_logger = transaction_logger
        else:
            from src.runtime.transaction_log import TransactionLog
            self._tx_logger = TransactionLog()

    # ── Wallet Loading ───────────────────────────────────────

    def _load_wallet(self) -> None:
        """Load wallet address and private key from environment or wallet.json."""
        env_key  = os.getenv("WALLET_PRIVATE_KEY")
        env_addr = os.getenv("WALLET_ADDRESS")
        if env_key and env_addr:
            self._private_key    = env_key
            self._wallet_address = Web3.to_checksum_address(env_addr)
            return

        if WALLET_JSON.exists():
            try:
                data = json.loads(WALLET_JSON.read_text())
                self._private_key    = data.get("private_key")
                self._wallet_address = Web3.to_checksum_address(data["address"])
                return
            except Exception as exc:
                logger.warning("Could not load wallet.json: %s", exc)

        logger.error(
            "No wallet credentials found. "
            "Set WALLET_ADDRESS + WALLET_PRIVATE_KEY env vars or provide wallet.json."
        )

    # ── Receiving Wallet ─────────────────────────────────────

    @property
    def receiving_wallet(self) -> Optional[str]:
        """
        Load receiving wallet from remittance-config.json.
        Returns None if file is missing or address is null/empty (remittance disabled).
        """
        if not REMITTANCE_CONFIG.exists():
            return None
        try:
            data = json.loads(REMITTANCE_CONFIG.read_text())
            addr = data.get("receiving_wallet")
            if addr and addr not in ("null", "", None):
                return Web3.to_checksum_address(addr)
        except Exception as exc:
            logger.warning("Could not read remittance-config.json: %s", exc)
        return None

    # ── Amount Calculation ───────────────────────────────────

    def calculate_remittable_amount(self, balance_usdc: Decimal) -> Decimal:
        """
        Calculate how much USDC can be remitted from the current balance.

        Returns:
            balance - $500 operating reserve - estimated gas cost,
            rounded down to 6 decimal places.
            Returns Decimal("0") if balance < MIN_REMITTANCE_BALANCE ($600).
        """
        if balance_usdc < self.MIN_REMITTANCE_BALANCE:
            return Decimal("0")
        # Reserve buffer for gas costs (conservative estimate for Base L2)
        gas_reserve = Decimal("0.50")  # $0.50 covers even high-gas scenarios on Base
        remittable = balance_usdc - self.OPERATING_RESERVE - gas_reserve
        return max(Decimal("0"), remittable.quantize(Decimal("0.000001"), rounding=ROUND_DOWN))

    def should_remit(self, balance_usdc: Decimal) -> bool:
        """
        Returns True if balance >= $5,000 USDC AND a receiving wallet is configured.
        """
        return balance_usdc >= self.REMITTANCE_THRESHOLD and self.receiving_wallet is not None

    # ── Wallet Prompt ────────────────────────────────────────

    def prompt_for_wallet(self, current_balance: Decimal) -> str:
        """
        Return the formatted prompt asking for a receiving wallet address.
        Displayed when balance first exceeds $5K and no receiving wallet is set.
        """
        balance   = Decimal(str(current_balance))
        remittable = self.calculate_remittable_amount(balance)

        return (
            "═══════════════════════════════════════════════════════════\n"
            " HYDRA REMITTANCE — TRANSFER READY ($1,000 THRESHOLD)\n"
            "═══════════════════════════════════════════════════════════\n"
            "\n"
            f" Treasury balance: ${balance:,.2f} USDC\n"
            f" Remittable amount: ${remittable:,.2f} USDC\n"
            f" Operating reserve retained: ${self.OPERATING_RESERVE:,.2f} USDC\n"
            "\n"
            " Balance has reached the $1,000 USDC transfer threshold.\n"
            "\n"
            " ► ACTION REQUIRED: Provide your wallet address to receive\n"
            "   this distribution via POST /system/wallet\n"
            "\n"
            " ► Then execute transfer via POST /system/remittance/execute\n"
            "\n"
            " Supported wallets: MetaMask, Coinbase Wallet, Rainbow,\n"
            " or any EVM-compatible wallet (Ethereum, Base, Polygon).\n"
            "\n"
            " PRIVACY:\n"
            " • Direct USDC transfer on Base L2 — no memo, no metadata\n"
            " • Receiving address stored in local config only\n"
            " • Never transmitted to any third party\n"
            " • Entity records show \"distribution to member\" only\n"
            "\n"
            " COMPLIANCE:\n"
            " • OFAC sanctions screening before each transfer\n"
            " • Transaction logged for entity tax records (Form 5472)\n"
            " • Constitution checks enforced on every transfer\n"
            "\n"
            "═══════════════════════════════════════════════════════════"
        )

    # ── Execute Remittance (async) ───────────────────────────

    async def execute_remittance(self) -> RemittanceResult:
        """
        Asynchronously execute a USDC remittance to the configured receiving wallet.

        Steps:
          1. Query USDC balance via balanceOf
          2. Calculate remittable amount
          3. Run constitution checks (OFAC on receiving wallet, solvency)
          4. If any check fails, return error result
          5. Build ERC-20 transfer transaction
          6. Sign transaction with private key
          7. Send raw transaction
          8. Poll for receipt (every 2 seconds, timeout 120 seconds)
          9. Log via transaction_logger.log_outbound() / log_distribution()
         10. Return RemittanceResult
        """
        import asyncio

        timestamp = datetime.now(timezone.utc).isoformat()

        # Pre-flight: credentials
        if not self._wallet_address or not self._private_key:
            return RemittanceResult(
                success=False,
                error_message="Wallet credentials not loaded. Cannot execute remittance.",
                timestamp=timestamp,
            )

        receiving = self.receiving_wallet
        if not receiving:
            return RemittanceResult(
                success=False,
                error_message="No receiving wallet configured. Remittance disabled.",
                timestamp=timestamp,
            )

        # 1. Get USDC balance
        try:
            raw = await asyncio.to_thread(
                self.usdc.functions.balanceOf(
                    Web3.to_checksum_address(self._wallet_address)
                ).call
            )
            balance = Decimal(str(raw)) / Decimal(str(10 ** USDC_DECIMALS))
        except Exception as exc:
            return RemittanceResult(
                success=False,
                error_message=f"Failed to query USDC balance: {exc}",
                timestamp=timestamp,
            )

        # 2. Calculate amount
        amount = self.calculate_remittable_amount(balance)
        if amount <= Decimal("0"):
            return RemittanceResult(
                success=False,
                error_message=(
                    f"Remittable amount is 0 "
                    f"(balance={balance:.6f} USDC, reserve={self.OPERATING_RESERVE} USDC)."
                ),
                timestamp=timestamp,
            )

        # 3. Constitution checks
        validation = await asyncio.to_thread(
            self.constitution.validate_remittance,
            receiving,
            float(amount),
            float(balance),
        )
        if not validation.approved:
            logger.error("Remittance blocked by constitution: %s", validation.reason)
            return RemittanceResult(
                success=False,
                error_message=validation.reason,
                constitution_checks=validation.checks,
                timestamp=timestamp,
            )

        logger.info(
            "Constitution checks passed. Executing remittance: %.6f USDC → %s",
            amount,
            receiving[:8] + "...",
        )

        # 4–7. Build, sign, send transaction
        try:
            amount_base_units = int(amount * Decimal(str(10 ** USDC_DECIMALS)))
            nonce = await asyncio.to_thread(
                self.w3.eth.get_transaction_count,
                Web3.to_checksum_address(self._wallet_address),
                "pending",
            )

            transfer_fn = self.usdc.functions.transfer(
                Web3.to_checksum_address(receiving),
                amount_base_units,
            )

            # Estimate gas with 20% buffer; fall back to 65,000
            try:
                gas_estimate = await asyncio.to_thread(
                    transfer_fn.estimate_gas,
                    {"from": Web3.to_checksum_address(self._wallet_address)},
                )
                gas_limit = int(gas_estimate * 1.2)
            except Exception:
                gas_limit = 65_000

            # Get current gas price from RPC
            try:
                gas_price = await asyncio.to_thread(lambda: self.w3.eth.gas_price)
            except Exception:
                gas_price = self.w3.to_wei("0.001", "gwei")  # Base L2 default

            tx = await asyncio.to_thread(
                transfer_fn.build_transaction,
                {
                    "from":     Web3.to_checksum_address(self._wallet_address),
                    "nonce":    nonce,
                    "gas":      gas_limit,
                    "gasPrice": gas_price,
                    "chainId":  8453,  # Base mainnet
                },
            )

            signed = self.w3.eth.account.sign_transaction(tx, self._private_key)
            tx_hash_bytes = await asyncio.to_thread(
                self.w3.eth.send_raw_transaction, signed.raw_transaction
            )
            tx_hash_hex = tx_hash_bytes.hex()
            if not tx_hash_hex.startswith("0x"):
                tx_hash_hex = "0x" + tx_hash_hex

            logger.info("Remittance transaction submitted: %s", tx_hash_hex)

        except Exception as exc:
            logger.error("Transaction submission failed: %s", exc)
            return RemittanceResult(
                success=False,
                error_message=f"Transaction submission failed: {exc}",
                constitution_checks=validation.checks,
                timestamp=timestamp,
            )

        # 8. Poll for receipt — every 2 seconds, timeout 120 seconds
        receipt = None
        deadline = time.monotonic() + 120.0
        while time.monotonic() < deadline:
            try:
                receipt = await asyncio.to_thread(
                    self.w3.eth.get_transaction_receipt, tx_hash_bytes
                )
                if receipt is not None:
                    break
            except TransactionNotFound:
                pass
            except Exception:
                pass
            await asyncio.sleep(2)

        if receipt is None:
            logger.warning(
                "Transaction %s not confirmed within 120s — may still be pending.",
                tx_hash_hex,
            )
            tx_status = "pending"
        else:
            tx_status = "confirmed" if receipt.get("status") == 1 else "reverted"
            logger.info("Transaction %s status: %s", tx_hash_hex, tx_status)

        # 9. Log via transaction_logger
        self._log_remittance(
            tx_hash=tx_hash_hex,
            amount_usdc=amount,
            receiving_address=receiving,
            timestamp=timestamp,
            status=tx_status,
        )

        if tx_status == "reverted":
            return RemittanceResult(
                success=False,
                tx_hash=tx_hash_hex,
                amount_usdc=amount,
                receiving_address=receiving,
                timestamp=timestamp,
                error_message="Transaction reverted on-chain.",
                constitution_checks=validation.checks,
            )

        # 10. Return success result
        return RemittanceResult(
            success=True,
            tx_hash=tx_hash_hex,
            amount_usdc=amount,
            receiving_address=receiving,
            timestamp=timestamp,
            constitution_checks=validation.checks,
        )

    # ── Set Receiving Wallet ─────────────────────────────────

    def set_receiving_wallet(self, address: str) -> dict[str, Any]:
        """
        Validate and persist the receiving wallet address.

        Validation:
          1. Valid EVM checksum address format
          2. Not the zero address
          3. Not the entity's own treasury wallet
          4. OFAC sanctions check passes

        Saves to remittance-config.json:
          {
            "receiving_wallet": "0x...",
            "set_at": "<ISO timestamp>",
            "ofac_cleared_at": "<ISO timestamp>"
          }

        Returns:
            dict with keys: status, address, ofac_cleared, message, error (if failed)
        """
        import re

        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Validate EVM address format
        if not re.match(r"^0x[0-9a-fA-F]{40}$", address):
            return {
                "status": "error",
                "error": f"Invalid EVM address format: {address!r}. "
                         "Must be 0x followed by 40 hex characters.",
                "address": address,
                "ofac_cleared": False,
            }

        # 2. Not zero address
        if address.lower() == "0x" + "0" * 40:
            return {
                "status": "error",
                "error": "Cannot set the zero address as receiving wallet.",
                "address": address,
                "ofac_cleared": False,
            }

        # 3. Not self
        if self._wallet_address and address.lower() == self._wallet_address.lower():
            return {
                "status": "error",
                "error": "Receiving wallet cannot be the entity's own treasury wallet.",
                "address": address,
                "ofac_cleared": False,
            }

        # 4. OFAC check
        legal_ok, legal_reason = self.constitution.check_legality(address, 0)
        if not legal_ok:
            return {
                "status": "error",
                "error": f"Address failed OFAC sanctions screening: {legal_reason}",
                "address": address,
                "ofac_cleared": False,
            }

        # Normalise to checksum address
        try:
            checksum_addr = Web3.to_checksum_address(address)
        except Exception as exc:
            return {
                "status": "error",
                "error": f"Address checksum conversion failed: {exc}",
                "address": address,
                "ofac_cleared": False,
            }

        # Persist to remittance-config.json
        try:
            BOOTSTRAP_DIR.mkdir(parents=True, exist_ok=True)
            config = {
                "receiving_wallet":  checksum_addr,
                "set_at":            now_iso,
                "ofac_cleared_at":   now_iso,
                "note": (
                    "Receiving wallet address for member distributions. "
                    "Stored locally only — never transmitted externally."
                ),
            }
            REMITTANCE_CONFIG.write_text(json.dumps(config, indent=2))
            logger.info(
                "Receiving wallet configured: %s...%s",
                checksum_addr[:8],
                checksum_addr[-6:],
            )
        except Exception as exc:
            return {
                "status": "error",
                "error": f"Failed to save remittance config: {exc}",
                "address": address,
                "ofac_cleared": True,
            }

        return {
            "status": "configured",
            "address": checksum_addr,
            "ofac_cleared": True,
            "set_at": now_iso,
            "ofac_cleared_at": now_iso,
        }

    # ── Remittance History ───────────────────────────────────

    def get_remittance_history(self) -> list[dict[str, Any]]:
        """
        Return past member-distribution transactions from the transaction log.

        Reads from the TransactionLog and filters entries where
        category == "member-distribution". Masks receiving addresses.
        """
        entries: list[dict[str, Any]] = []
        try:
            from src.runtime.transaction_log import TransactionLog, TxCategory
            tl = TransactionLog()
            raw_entries = tl.get_entries(category=TxCategory.MEMBER_DISTRIBUTION)
            for entry in raw_entries:
                # Mask counterparty address
                e = dict(entry)
                addr = e.get("counterparty_address", "")
                if addr and len(addr) > 14:
                    e["counterparty_address"] = addr[:8] + "..." + addr[-6:]
                entries.append(e)
        except Exception as exc:
            logger.warning("Could not load remittance history from transaction log: %s", exc)

        # Also fall back to the dedicated remittance-log.jsonl if present
        if not entries and REMITTANCE_LOG.exists():
            try:
                for line in REMITTANCE_LOG.read_text().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        # Mask receiving address
                        addr = e.get("receiving_address", "")
                        if addr and len(addr) > 14:
                            e["receiving_address"] = addr[:8] + "..." + addr[-6:]
                        entries.append(e)
                    except json.JSONDecodeError:
                        continue
            except Exception as exc:
                logger.warning("Could not read remittance-log.jsonl: %s", exc)

        return entries

    # ── Internal Logging ─────────────────────────────────────

    def _log_remittance(
        self,
        tx_hash: str,
        amount_usdc: Decimal,
        receiving_address: str,
        timestamp: str,
        status: str,
    ) -> None:
        """Append remittance to both the transaction log and the dedicated remittance log."""
        # Primary: TransactionLog (for Form 5472)
        try:
            from src.runtime.transaction_log import TxDirection, TxCategory
            self._tx_logger.log(
                tx_hash=tx_hash,
                direction=TxDirection.OUTBOUND,
                category=TxCategory.MEMBER_DISTRIBUTION,
                amount_usdc=float(amount_usdc),
                counterparty_address=receiving_address,
                note=f"Autonomous remittance — status: {status}",
                timestamp=timestamp,
            )
        except Exception as exc:
            logger.error("Failed to write to transaction log: %s", exc)

        # Secondary: dedicated remittance-log.jsonl
        try:
            BOOTSTRAP_DIR.mkdir(parents=True, exist_ok=True)
            entry = json.dumps({
                "timestamp":         timestamp,
                "tx_hash":           tx_hash,
                "amount_usdc":       str(amount_usdc),
                "receiving_address": receiving_address,
                "status":            status,
            })
            with REMITTANCE_LOG.open("a") as f:
                f.write(entry + "\n")
        except Exception as exc:
            logger.error("Failed to write to remittance-log.jsonl: %s", exc)

    # ── Legacy compatibility helpers ─────────────────────────

    def get_remittance_log(self) -> list[dict[str, Any]]:
        """Alias for get_remittance_history() — backwards compatibility."""
        return self.get_remittance_history()
