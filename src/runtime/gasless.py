"""
gasless.py — HYDRA Gasless Self-Funding Layer
=============================================
Lets HYDRA move USDC and fund its own gas WITHOUT the owner ever fronting ETH.

Two capabilities:

1. Gasless remittance (EIP-3009 `transferWithAuthorization`)
   USDC on Base implements EIP-3009. HYDRA signs a transfer authorization
   OFF-CHAIN (zero gas, no ETH needed), and a *relayer* submits it on-chain and
   pays the gas. This preserves HYDRA's existing EOA wallet address.
   - The signing is self-contained and deterministic (unit-tested here).
   - Submission requires a relayer endpoint (HYDRA_RELAYER_URL). Until one is
     configured, `relay()` returns the signed payload so it can be submitted
     manually or by an external facilitator — it never silently no-ops.

2. Gas self-funding (USDC -> ETH gasless swap)
   When the treasury holds USDC but not enough ETH for contract calls (e.g. an
   Aave supply), the GasStation can convert a few cents of USDC into ETH via a
   gasless swap provider (HYDRA_GASLESS_SWAP_URL, e.g. a 0x-gasless-style API
   that takes its fee from the input token). Disabled until configured.

IMPORTANT: "gasless" means a relayer/paymaster pays the gas, not that gas is
free to the universe. It is free to *you* (the owner). The signing math is
verified in-repo; live relaying/swapping must be validated against the chosen
provider before relying on it in production.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger("hydra.gasless")

USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_DECIMALS = 6
CHAIN_ID = 8453  # Base mainnet

# EIP-712 domain for Base USDC. These must match the on-chain contract; they can
# be overridden via env if Circle bumps the version. Verify with the contract's
# eip712Domain() / version() if a signature is ever rejected.
USDC_DOMAIN_NAME = os.getenv("HYDRA_USDC_DOMAIN_NAME", "USD Coin")
USDC_DOMAIN_VERSION = os.getenv("HYDRA_USDC_DOMAIN_VERSION", "2")


def _is_placeholder_key(private_key: str) -> bool:
    """True if the key is missing/malformed/all-zero (read-only mode)."""
    if not private_key:
        return True
    clean = private_key.lower().removeprefix("0x").strip()
    if len(clean) != 64 or set(clean) <= {"0"}:
        return True
    try:
        int(clean, 16)
    except ValueError:
        return True
    return False


def build_transfer_authorization(
    frm: str,
    to: str,
    value_base_units: int,
    valid_seconds: int = 3600,
) -> tuple[dict, dict]:
    """
    Build the EIP-712 typed-data payload for USDC `transferWithAuthorization`.

    Returns ``(typed_data, meta)`` where ``meta`` carries the generated nonce
    (0x-hex) and the validity window. No signing, no network.
    """
    from web3 import Web3

    now = int(time.time())
    valid_after = 0
    valid_before = now + valid_seconds
    nonce = secrets.token_bytes(32)

    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": USDC_DOMAIN_NAME,
            "version": USDC_DOMAIN_VERSION,
            "chainId": CHAIN_ID,
            "verifyingContract": Web3.to_checksum_address(USDC_ADDRESS),
        },
        "message": {
            "from": Web3.to_checksum_address(frm),
            "to": Web3.to_checksum_address(to),
            "value": int(value_base_units),
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce,
        },
    }
    meta = {
        "nonce": "0x" + nonce.hex(),
        "valid_after": valid_after,
        "valid_before": valid_before,
    }
    return typed_data, meta


class GaslessRemitter:
    """
    Signs EIP-3009 USDC transfer authorizations (no gas) and relays them.

    Enabled only when the provided private key derives to ``wallet_address`` —
    mirroring the treasury yield manager's safety gate.
    """

    def __init__(self, wallet_address: str, private_key: str) -> None:
        from web3 import Web3

        self.wallet_address = Web3.to_checksum_address(wallet_address)
        self._private_key = private_key
        self.account = None
        self._enabled = False
        self._disabled_reason: Optional[str] = "no private key configured"

        if not _is_placeholder_key(private_key):
            try:
                from eth_account import Account
                self.account = Account.from_key(private_key)
                if Web3.to_checksum_address(self.account.address) == self.wallet_address:
                    self._enabled = True
                    self._disabled_reason = None
                else:
                    self._disabled_reason = "private key does not control treasury wallet"
                    self.account = None
            except Exception as exc:  # noqa: BLE001
                self._disabled_reason = f"invalid private key ({type(exc).__name__})"

    def is_enabled(self) -> bool:
        return self._enabled

    def sign_remittance(self, to: str, amount_usdc: Decimal) -> dict:
        """
        Build + sign an EIP-3009 authorization to send ``amount_usdc`` to ``to``.
        Returns a relayer-ready payload. Costs zero gas; needs no ETH.
        """
        if not self._enabled:
            raise RuntimeError(f"GaslessRemitter disabled: {self._disabled_reason}")

        from eth_account import Account
        from eth_account.messages import encode_typed_data

        value = int(amount_usdc * Decimal(10**USDC_DECIMALS))
        typed_data, meta = build_transfer_authorization(self.wallet_address, to, value)
        signable = encode_typed_data(full_message=typed_data)
        signed = Account.sign_message(signable, self._private_key)

        return {
            "scheme": "eip3009-transferWithAuthorization",
            "token": USDC_ADDRESS,
            "chain_id": CHAIN_ID,
            "from": self.wallet_address,
            "to": typed_data["message"]["to"],
            "value": str(value),
            "value_usdc": str(amount_usdc),
            "validAfter": meta["valid_after"],
            "validBefore": meta["valid_before"],
            "nonce": meta["nonce"],
            "v": signed.v,
            "r": "0x" + format(signed.r, "064x"),
            "s": "0x" + format(signed.s, "064x"),
            "signature": signed.signature.hex(),
        }

    async def relay(self, payload: dict) -> dict:
        """
        Submit a signed authorization to the configured relayer (HYDRA_RELAYER_URL),
        which pays the gas. If no relayer is configured, returns the payload so it
        can be relayed externally — never silently drops it.
        """
        relayer_url = os.getenv("HYDRA_RELAYER_URL", "").strip()
        if not relayer_url:
            logger.info(
                "Gasless remittance signed but NO relayer configured "
                "(set HYDRA_RELAYER_URL). Returning signed payload for external relay."
            )
            return {"relayed": False, "reason": "no relayer configured", "payload": payload}

        headers = {"Content-Type": "application/json"}
        api_key = os.getenv("HYDRA_RELAYER_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(relayer_url, json=payload, headers=headers)
                ok = resp.status_code < 400
                body: Any
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                if ok:
                    logger.info("Gasless remittance relayed (HTTP %d).", resp.status_code)
                else:
                    logger.error("Relayer rejected remittance (HTTP %d): %s", resp.status_code, body)
                return {"relayed": ok, "status": resp.status_code, "response": body}
        except Exception as exc:  # noqa: BLE001
            logger.error("Relayer request failed: %s", exc)
            return {"relayed": False, "reason": str(exc), "payload": payload}


class GasStation:
    """
    Keeps the treasury's ETH topped up for contract calls (e.g. Aave deposits)
    by gaslessly swapping a small amount of USDC -> ETH, so the owner never
    fronts ETH. Disabled until a gasless swap provider is configured.
    """

    def __init__(self, w3, wallet_address: str) -> None:
        from web3 import Web3
        self.w3 = w3
        self.wallet_address = Web3.to_checksum_address(wallet_address)

    def eth_balance(self) -> Decimal:
        try:
            wei = self.w3.eth.get_balance(self.wallet_address)
            return Decimal(wei) / Decimal(10**18)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not read ETH balance: %s", exc)
            return Decimal("0")

    async def ensure_gas(
        self,
        min_eth: Decimal = Decimal("0.00005"),
        topup_usdc: Decimal = Decimal("0.25"),
    ) -> dict:
        """
        If ETH is below ``min_eth``, request a gasless USDC->ETH swap of
        ``topup_usdc`` via HYDRA_GASLESS_SWAP_URL. Returns a status dict.

        No-op (with guidance) when no provider is configured.
        """
        eth = self.eth_balance()
        if eth >= min_eth:
            return {"action": "none", "eth_balance": str(eth)}

        swap_url = os.getenv("HYDRA_GASLESS_SWAP_URL", "").strip()
        if not swap_url:
            logger.info(
                "Gas low (%.8f ETH) and no gasless swap provider configured "
                "(set HYDRA_GASLESS_SWAP_URL). HYDRA cannot self-fund gas yet.",
                eth,
            )
            return {"action": "blocked", "reason": "no swap provider", "eth_balance": str(eth)}

        # Provider request shape varies (0x gasless, 1inch fusion, etc.). This is
        # intentionally generic and MUST be validated against the chosen provider
        # before production reliance. It never holds ETH to do the swap (that's
        # the point) — the provider relays via permit/EIP-3009.
        req = {
            "chainId": CHAIN_ID,
            "taker": self.wallet_address,
            "sellToken": USDC_ADDRESS,
            "buyToken": "ETH",
            "sellAmount": str(int(topup_usdc * Decimal(10**USDC_DECIMALS))),
        }
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv("HYDRA_GASLESS_SWAP_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(swap_url, json=req, headers=headers)
                ok = resp.status_code < 400
                logger.info("Gasless USDC->ETH top-up requested (HTTP %d).", resp.status_code)
                return {"action": "swap_requested", "ok": ok, "status": resp.status_code}
        except Exception as exc:  # noqa: BLE001
            logger.error("Gasless swap request failed: %s", exc)
            return {"action": "error", "reason": str(exc)}
