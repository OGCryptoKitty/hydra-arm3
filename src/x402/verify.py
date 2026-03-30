"""
HYDRA Arm 3 — x402 Payment Verification
Verifies USDC transfer transactions on Base (L2) mainnet.

Flow:
  1. Receive tx_hash from client's X-Payment-Proof header
  2. Fetch transaction receipt from Base RPC
  3. Parse ERC-20 Transfer event logs from the USDC contract
  4. Confirm: recipient matches our wallet, amount >= required amount
  5. Return PaymentVerificationResult
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from web3 import Web3
from web3.exceptions import TransactionNotFound

from config.settings import (
    BASE_RPC_URL,
    ERC20_TRANSFER_TOPIC,
    USDC_CONTRACT_ADDRESS,
    WALLET_ADDRESS,
)
from src.models.schemas import PaymentVerificationResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# ERC-20 Transfer ABI (minimal — only Transfer event)
# ─────────────────────────────────────────────────────────────

ERC20_MINIMAL_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    }
]

# Normalise our wallet to checksummed form once
_WALLET_CHECKSUMMED: str = Web3.to_checksum_address(WALLET_ADDRESS)
_USDC_CHECKSUMMED: str = Web3.to_checksum_address(USDC_CONTRACT_ADDRESS)


def _get_web3() -> Web3:
    """Return a Web3 instance connected to Base mainnet."""
    w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL, request_kwargs={"timeout": 30}))
    return w3


def verify_usdc_payment(
    tx_hash: str,
    required_amount_base_units: int,
) -> PaymentVerificationResult:
    """
    Verify a USDC payment on Base mainnet.

    Parameters
    ----------
    tx_hash : str
        The transaction hash provided by the client.
    required_amount_base_units : int
        Expected minimum USDC amount in base units (6 decimals).
        Example: 1_000_000 = 1.00 USDC

    Returns
    -------
    PaymentVerificationResult
        .verified=True if the tx is valid, confirmed, and sent the correct amount.
    """
    # Sanitise input
    tx_hash = tx_hash.strip()
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash

    try:
        w3 = _get_web3()

        if not w3.is_connected():
            logger.error("Cannot connect to Base RPC: %s", BASE_RPC_URL)
            return PaymentVerificationResult(
                verified=False,
                tx_hash=tx_hash,
                error="Unable to connect to Base RPC endpoint",
            )

        # Fetch the receipt; raises TransactionNotFound if not mined yet
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
        except TransactionNotFound:
            return PaymentVerificationResult(
                verified=False,
                tx_hash=tx_hash,
                error="Transaction not found on Base. It may not have been mined yet.",
            )

        if receipt is None:
            return PaymentVerificationResult(
                verified=False,
                tx_hash=tx_hash,
                error="Transaction receipt is None. Transaction may be pending.",
            )

        # Must be a successful transaction
        if receipt.get("status") != 1:
            return PaymentVerificationResult(
                verified=False,
                tx_hash=tx_hash,
                error="Transaction reverted (status=0). Payment not accepted.",
            )

        # Instantiate USDC contract to decode logs
        usdc_contract = w3.eth.contract(address=_USDC_CHECKSUMMED, abi=ERC20_MINIMAL_ABI)

        # Parse Transfer events from the receipt
        transfer_events = usdc_contract.events.Transfer().process_receipt(receipt)

        for event in transfer_events:
            to_address: str = Web3.to_checksum_address(event["args"]["to"])
            from_address: str = Web3.to_checksum_address(event["args"]["from"])
            value: int = event["args"]["value"]

            # Check recipient matches our wallet
            if to_address.lower() != _WALLET_CHECKSUMMED.lower():
                continue

            # Check amount is sufficient
            if value >= required_amount_base_units:
                logger.info(
                    "Payment verified: tx=%s from=%s amount=%d (required=%d)",
                    tx_hash,
                    from_address,
                    value,
                    required_amount_base_units,
                )
                return PaymentVerificationResult(
                    verified=True,
                    tx_hash=tx_hash,
                    amount_received_base_units=value,
                    amount_required_base_units=required_amount_base_units,
                    from_address=from_address,
                    to_address=to_address,
                )
            else:
                logger.warning(
                    "Insufficient payment: tx=%s amount=%d required=%d",
                    tx_hash,
                    value,
                    required_amount_base_units,
                )
                return PaymentVerificationResult(
                    verified=False,
                    tx_hash=tx_hash,
                    amount_received_base_units=value,
                    amount_required_base_units=required_amount_base_units,
                    to_address=to_address,
                    error=(
                        f"Insufficient payment: received {value} base units, "
                        f"required {required_amount_base_units} base units."
                    ),
                )

        # No matching Transfer to our wallet found
        logger.warning("No USDC Transfer to %s found in tx %s", _WALLET_CHECKSUMMED, tx_hash)
        return PaymentVerificationResult(
            verified=False,
            tx_hash=tx_hash,
            error=(
                f"No USDC Transfer event to {_WALLET_CHECKSUMMED} found in transaction. "
                "Ensure you sent USDC on Base to the correct address."
            ),
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during payment verification: %s", exc)
        return PaymentVerificationResult(
            verified=False,
            tx_hash=tx_hash,
            error=f"Verification error: {exc}",
        )


def is_valid_tx_hash(tx_hash: str) -> bool:
    """Quick format validation for a 0x-prefixed 32-byte hex tx hash."""
    tx = tx_hash.strip()
    if not tx.startswith("0x"):
        tx = "0x" + tx
    return len(tx) == 66 and all(c in "0123456789abcdefABCDEF" for c in tx[2:])
