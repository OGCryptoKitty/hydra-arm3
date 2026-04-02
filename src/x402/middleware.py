"""
HYDRA Arm 3 — x402 Payment Middleware

Implements the x402 HTTP payment protocol as a FastAPI middleware.

Protocol flow:
  Request without proof  → 402 + payment instructions in headers + JSON body
  Request with proof     → verify tx on Base → 200 or 402 (bad proof)

Headers used:
  Request:
    X-Payment-Proof: <0x tx_hash>

  Response (402):
    X-Payment-Required: true
    X-Payment-Amount: <base units>
    X-Payment-Address: <wallet address>
    X-Payment-Network: base
    X-Payment-Token: USDC
    X-Payment-Chain-Id: 8453
    X-Payment-Endpoint: <path>
    Content-Type: application/json

  Response (200 after payment):
    X-Payment-Verified: true
    X-Payment-Tx: <tx_hash>

Replay prevention:
  A verified tx hash is stored in an in-memory TTLCache. If the same hash
  is presented again, the server returns 402 (already used).
"""

from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from typing import Callable

from cachetools import TTLCache
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config.settings import (
    PAYMENT_CACHE_TTL,
    PAYMENT_NETWORK,
    PAYMENT_TOKEN,
    PRICING,
    USDC_DECIMALS,
    WALLET_ADDRESS,
    CHAIN_ID,
)
from src.x402.verify import is_valid_tx_hash, verify_usdc_payment

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# In-memory replay-prevention cache
# Stores: tx_hash → unix timestamp of first verification
# ─────────────────────────────────────────────────────────────

_used_tx_cache: TTLCache = TTLCache(maxsize=10_000, ttl=PAYMENT_CACHE_TTL)


def _mark_tx_used(tx_hash: str) -> None:
    _used_tx_cache[tx_hash.lower()] = time.time()


def _is_tx_used(tx_hash: str) -> bool:
    return tx_hash.lower() in _used_tx_cache


# ─────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────

class X402PaymentMiddleware(BaseHTTPMiddleware):
    """
    Intercepts requests to paid endpoints.
    - No proof header  → 402 with payment details
    - Proof present    → verify on-chain → pass through or 402
    """

    # Paths that bypass payment checks (free endpoints)
    _FREE_PATHS: frozenset[str] = frozenset({
        "/health",
        "/pricing",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/favicon.ico",
    })

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # ── Free endpoints pass through immediately ──────────
        if path in self._FREE_PATHS or not path.startswith("/v1/"):
            return await call_next(request)

        # ── Determine pricing for this endpoint ──────────────
        # Exact match first, then prefix match for path-parameter endpoints
        # (e.g. /v1/markets/signal/{market_id} → /v1/markets/signal)
        pricing = PRICING.get(path)
        if pricing is None:
            for pricing_path, pricing_info in PRICING.items():
                if path.startswith(pricing_path + "/") or path == pricing_path:
                    pricing = pricing_info
                    break
        if pricing is None:
            # Unknown paid path — pass through (let route handler return 404)
            return await call_next(request)

        required_amount = pricing["amount_base_units"]

        # ── Check for payment proof header ───────────────────
        proof_header = request.headers.get("X-Payment-Proof") or request.headers.get("x-payment-proof")

        if not proof_header:
            return self._payment_required_response(path, pricing)

        # ── Validate tx hash format ───────────────────────────
        tx_hash = proof_header.strip()
        if not is_valid_tx_hash(tx_hash):
            return self._error_response(
                402,
                "Invalid payment proof format. X-Payment-Proof must be a 0x-prefixed 32-byte hex transaction hash.",
                path,
                pricing,
            )

        # ── Replay prevention ─────────────────────────────────
        if _is_tx_used(tx_hash):
            return self._error_response(
                402,
                f"Transaction {tx_hash} has already been used for a previous request. Each payment can only be used once.",
                path,
                pricing,
            )

        # ── Verify on-chain ───────────────────────────────────
        logger.info("Verifying payment tx=%s for path=%s amount=%d", tx_hash, path, required_amount)
        result = verify_usdc_payment(tx_hash, required_amount)

        if not result.verified:
            logger.warning("Payment verification failed: tx=%s error=%s", tx_hash, result.error)
            return self._error_response(
                402,
                f"Payment verification failed: {result.error}",
                path,
                pricing,
            )

        # ── Mark tx as used before passing through ────────────
        _mark_tx_used(tx_hash)
        logger.info("Payment verified and consumed: tx=%s path=%s", tx_hash, path)

        # ── Log revenue to transaction log ────────────────────
        try:
            from src.runtime.transaction_log import TransactionLog, TxDirection, TxCategory
            tl = getattr(request.app.state, "transaction_log", None)
            if tl is None:
                tl = TransactionLog()
            amount_usdc = Decimal(str(result.amount_received_base_units)) / Decimal(10 ** USDC_DECIMALS)
            tl.log_inbound(
                tx_hash=tx_hash,
                amount_usdc=amount_usdc,
                from_address=result.from_address if hasattr(result, "from_address") else "unknown",
                category="x402-revenue",
                note=f"x402 payment for {path}",
            )
        except Exception as log_exc:
            logger.warning("Failed to log revenue for tx=%s: %s", tx_hash, log_exc)

        # ── Execute the actual request handler ────────────────
        response = await call_next(request)

        # Attach verification metadata to response headers
        response.headers["X-Payment-Verified"] = "true"
        response.headers["X-Payment-Tx"] = tx_hash
        response.headers["X-Payment-Amount-Received"] = str(result.amount_received_base_units)

        # ── Track payment failures (payment consumed but endpoint errored) ──
        if response.status_code >= 500:
            logger.error(
                "PAYMENT CONSUMED BUT ENDPOINT FAILED: tx=%s path=%s status=%d — "
                "customer paid %s USDC but received a server error",
                tx_hash, path, response.status_code, pricing["amount_usdc"],
            )

        return response

    @staticmethod
    def _payment_required_response(path: str, pricing: dict) -> JSONResponse:
        """Return a standards-compliant 402 Payment Required response."""
        body = {
            "error": "Payment Required",
            "message": (
                f"This endpoint requires a payment of {pricing['amount_usdc']} USDC on Base. "
                f"Send exactly {pricing['amount_base_units']} USDC base units (6 decimals) "
                f"to the wallet address, then retry with your transaction hash in the "
                f"X-Payment-Proof header."
            ),
            "payment": {
                "amount_usdc": str(pricing["amount_usdc"]),
                "amount_base_units": pricing["amount_base_units"],
                "wallet_address": WALLET_ADDRESS,
                "network": PAYMENT_NETWORK,
                "token": PAYMENT_TOKEN,
                "chain_id": CHAIN_ID,
                "endpoint": path,
                "description": pricing["description"],
            },
            "retry_instructions": {
                "step_1": f"Send {pricing['amount_usdc']} USDC to {WALLET_ADDRESS} on Base (chain ID {CHAIN_ID})",
                "step_2": "Copy the transaction hash from your wallet or block explorer",
                "step_3": "Resend this request with header: X-Payment-Proof: <0x_tx_hash>",
            },
        }

        headers = {
            "X-Payment-Required": "true",
            "X-Payment-Amount": str(pricing["amount_base_units"]),
            "X-Payment-Address": WALLET_ADDRESS,
            "X-Payment-Network": PAYMENT_NETWORK,
            "X-Payment-Token": PAYMENT_TOKEN,
            "X-Payment-Chain-Id": str(CHAIN_ID),
            "X-Payment-Endpoint": path,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": (
                "X-Payment-Required, X-Payment-Amount, X-Payment-Address, "
                "X-Payment-Network, X-Payment-Token, X-Payment-Chain-Id, "
                "X-Payment-Endpoint, X-Payment-Verified, X-Payment-Tx"
            ),
        }

        return JSONResponse(status_code=402, content=body, headers=headers)

    @staticmethod
    def _error_response(status_code: int, message: str, path: str, pricing: dict) -> JSONResponse:
        """Return a 402 with an error message and payment details."""
        body = {
            "error": "Payment Error",
            "message": message,
            "payment": {
                "amount_usdc": str(pricing["amount_usdc"]),
                "amount_base_units": pricing["amount_base_units"],
                "wallet_address": WALLET_ADDRESS,
                "network": PAYMENT_NETWORK,
                "token": PAYMENT_TOKEN,
                "chain_id": CHAIN_ID,
                "endpoint": path,
            },
        }
        headers = {
            "X-Payment-Required": "true",
            "X-Payment-Amount": str(pricing["amount_base_units"]),
            "X-Payment-Address": WALLET_ADDRESS,
            "X-Payment-Network": PAYMENT_NETWORK,
            "X-Payment-Token": PAYMENT_TOKEN,
            "X-Payment-Chain-Id": str(CHAIN_ID),
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": (
                "X-Payment-Required, X-Payment-Amount, X-Payment-Address, "
                "X-Payment-Network, X-Payment-Token, X-Payment-Chain-Id, "
                "X-Payment-Verified, X-Payment-Tx"
            ),
        }
        return JSONResponse(status_code=status_code, content=body, headers=headers)
