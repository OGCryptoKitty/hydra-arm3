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

import base64
import json
import logging
import time
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
    USDC_CONTRACT_ADDRESS,
    USDC_DECIMALS,
    WALLET_ADDRESS,
    CHAIN_ID,
)
from src.x402.verify import is_valid_tx_hash, verify_usdc_payment

logger = logging.getLogger(__name__)


def _get_sample_response(path: str) -> dict | None:
    """Return a truncated sample of what a paid response looks like."""
    samples = {
        "/v1/util/gas": {
            "_note": "SAMPLE — pay to get live data",
            "gas_price_gwei": "0.005",
            "base_fee_gwei": "0.004",
            "estimated_costs": {"transfer": "$0.001", "swap": "$0.003", "mint": "$0.005"},
        },
        "/v1/util/crypto/price": {
            "_note": "SAMPLE — pay to get live data",
            "token": "ETH",
            "price_usd": "3,450.00",
            "change_24h": "+2.1%",
        },
        "/v1/markets/feed": {
            "_note": "SAMPLE — pay to get full feed",
            "events": [{"title": "SEC Commissioner speech on crypto ETFs", "agency": "SEC", "matched_markets": 3}],
            "total_events": "10 (truncated)",
        },
        "/v1/regulatory/scan": {
            "_note": "SAMPLE — pay to get full scan",
            "overall_risk_level": "HIGH",
            "applicable_regulations": ["Securities Act 1933", "Howey Test", "FinCEN MSB Registration"],
            "total_regulations": "12 (truncated)",
        },
        "/v1/fed/signal": {
            "_note": "SAMPLE — pay to get full signal",
            "rate_probability": {"hold": 0.87, "cut": 0.11, "hike": 0.02},
            "next_fomc": "2026-05-07",
        },
        "/v1/extract/url": {
            "_note": "SAMPLE — pay to get full extraction",
            "title": "Example Page Title",
            "headings": [{"level": 1, "text": "Main Heading"}],
            "text": "Clean extracted text (truncated)...",
            "links": [{"text": "Link text", "href": "https://example.com"}],
        },
        "/v1/extract/search": {
            "_note": "SAMPLE — pay to get full results",
            "query": "example query",
            "results": [{"title": "Result 1", "snippet": "Preview...", "url": "https://example.com"}],
            "result_count": 8,
        },
    }
    if path in samples:
        return samples[path]
    for prefix in ("/v1/util/", "/v1/markets/signal"):
        if path.startswith(prefix) and prefix.rstrip("/") in samples:
            return samples[prefix.rstrip("/")]
    return {"_note": "Pay to access this endpoint", "description": "Full response available after x402 payment"}

# ─────────────────────────────────────────────────────────────
# Replay-prevention cache (in-memory + file-backed persistence)
# Stores: tx_hash → unix timestamp of first verification
# File persistence survives Render restarts.
# ─────────────────────────────────────────────────────────────

_REPLAY_CACHE_FILE = "/tmp/hydra_used_txhashes.json"

_used_tx_cache: TTLCache = TTLCache(maxsize=10_000, ttl=PAYMENT_CACHE_TTL)


def _load_replay_cache() -> None:
    """Load persisted tx hashes from disk into memory on startup."""
    try:
        import os
        if not os.path.exists(_REPLAY_CACHE_FILE):
            return
        with open(_REPLAY_CACHE_FILE, "r") as f:
            data = json.load(f)
        now = time.time()
        loaded = 0
        for tx_hash, ts in data.items():
            if now - ts < PAYMENT_CACHE_TTL:
                _used_tx_cache[tx_hash] = ts
                loaded += 1
        if loaded:
            logger.info("Loaded %d tx hashes from replay cache", loaded)
    except Exception as exc:
        logger.warning("Could not load replay cache: %s", exc)


def _save_replay_cache() -> None:
    """Persist current cache to disk."""
    try:
        with open(_REPLAY_CACHE_FILE, "w") as f:
            json.dump(dict(_used_tx_cache), f)
    except Exception as exc:
        logger.debug("Could not save replay cache: %s", exc)


_load_replay_cache()


def _mark_tx_used(tx_hash: str) -> None:
    _used_tx_cache[tx_hash.lower()] = time.time()
    _save_replay_cache()


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
        "/v1/markets",
        "/v1/markets/discovery",
        "/v1/markets/pricing",
        "/v1/util",
    })

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # ── Free endpoints pass through immediately ──────────
        if path in self._FREE_PATHS or not path.startswith("/v1/"):
            return await call_next(request)

        # ── Determine pricing for this endpoint ──────────────
        pricing = PRICING.get(path)

        # Handle parameterized routes (e.g., /v1/markets/signal/{market_id})
        # Strip the last path segment and check for a parent match
        if pricing is None and path.startswith("/v1/"):
            parent_path = "/".join(path.rstrip("/").split("/")[:-1])
            pricing = PRICING.get(parent_path)
        if pricing is None:
            # Unknown paid path — pass through (let route handler return 404)
            return await call_next(request)

        required_amount = pricing["amount_base_units"]

        # ── If standard x402 X-PAYMENT header is present, defer to CDP middleware ──
        if request.headers.get("X-PAYMENT") or request.headers.get("x-payment"):
            return await call_next(request)

        # ── Check for legacy payment proof header ────────────
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

        # ── Execute the actual request handler ────────────────
        response = await call_next(request)

        # Attach verification metadata to response headers
        response.headers["X-Payment-Verified"] = "true"
        response.headers["X-Payment-Tx"] = tx_hash
        response.headers["X-Payment-Amount-Received"] = str(result.amount_received_base_units)
        # Prevent proxies/CDNs from caching paid content (each response is unique per payment)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Vary"] = "X-Payment-Proof"

        # ── Log payment-consumed delivery failures for operational awareness ──
        # All payments are FINAL — no refunds are issued. USDC on Base L2 is
        # a permissionless transfer; once confirmed, the payment is complete.
        # This log entry is for operational monitoring only (to fix recurring
        # endpoint failures that degrade service quality).
        if response.status_code >= 500:
            logger.error(
                "DELIVERY ISSUE: tx=%s path=%s status=%d — "
                "payment of %s USDC consumed, endpoint returned server error. "
                "All payments are final. Investigate endpoint stability.",
                tx_hash, path, response.status_code, pricing["amount_usdc"],
            )

        return response

    @staticmethod
    def _build_x402_payment_required_header(path: str, pricing: dict) -> str:
        """
        Build the standard x402 PAYMENT-REQUIRED header value.

        This is a base64-encoded JSON object following the x402 protocol spec
        (coinbase/x402). Including this header makes HYDRA discoverable by:
          - x402 Bazaar (Coinbase AI agent discovery)
          - x402scan.com (open x402 registry)
          - x402-index (autonomous x402 crawler)
          - Any x402-compliant client or AI agent
        """
        payment_requirements = {
            "x402Version": 1,
            "scheme": "exact",
            "network": f"eip155:{CHAIN_ID}",
            "maxAmountRequired": str(pricing["amount_base_units"]),
            "resource": path,
            "description": pricing["description"],
            "mimeType": "application/json",
            "payTo": WALLET_ADDRESS,
            "maxTimeoutSeconds": 900,
            "asset": USDC_CONTRACT_ADDRESS,
            "extra": {
                "name": "HYDRA Regulatory Intelligence",
                "pricing_usdc": str(pricing["amount_usdc"]),
                "accepts": ["X-Payment-Proof"],
            },
        }
        return base64.b64encode(
            json.dumps(payment_requirements, separators=(",", ":")).encode()
        ).decode()

    @staticmethod
    def _payment_required_response(path: str, pricing: dict) -> JSONResponse:
        """Return a standards-compliant 402 Payment Required response."""
        sample = _get_sample_response(path)
        body = {
            "error": "Payment Required",
            "message": (
                f"This endpoint requires a payment of {pricing['amount_usdc']} USDC on Base. "
                f"Send exactly {pricing['amount_base_units']} USDC base units (6 decimals) "
                f"to the wallet address, then retry with your transaction hash in the "
                f"X-Payment-Proof header."
            ),
            "sample_response": sample,
            "payment": {
                "amount_usdc": str(pricing["amount_usdc"]),
                "amount_base_units": pricing["amount_base_units"],
                "wallet_address": WALLET_ADDRESS,
                "network": PAYMENT_NETWORK,
                "token": PAYMENT_TOKEN,
                "token_contract": USDC_CONTRACT_ADDRESS,
                "chain_id": CHAIN_ID,
                "endpoint": path,
                "description": pricing["description"],
            },
            "x402": {
                "version": "1.0",
                "scheme": "exact",
                "facilitator": "https://x402.org/facilitator",
                "pay": {
                    "to": WALLET_ADDRESS,
                    "amount": str(pricing["amount_base_units"]),
                    "token": USDC_CONTRACT_ADDRESS,
                    "chain_id": CHAIN_ID,
                    "network": "base",
                },
                "proof": {
                    "header": "X-Payment-Proof",
                    "type": "tx_hash",
                    "format": "0x-prefixed 32-byte hex",
                },
            },
            "retry_instructions": {
                "step_1": f"Send {pricing['amount_usdc']} USDC to {WALLET_ADDRESS} on Base (chain ID {CHAIN_ID})",
                "step_2": "Copy the transaction hash from your wallet or block explorer",
                "step_3": "Resend this request with header: X-Payment-Proof: <0x_tx_hash>",
            },
        }

        # Standard x402 protocol header (base64-encoded JSON) — enables
        # discovery by x402 Bazaar, x402scan, and x402-index crawlers
        x402_header = X402PaymentMiddleware._build_x402_payment_required_header(path, pricing)

        headers = {
            # ── Standard x402 protocol header ────────────────────
            "PAYMENT-REQUIRED": x402_header,
            # ── Multi-protocol payment discovery ─────────────────
            "WWW-Authenticate": 'Payment realm="HYDRA Regulatory Intelligence", charset="UTF-8"',
            "Accept-Payment": "x402, mpp, x-payment-proof",
            # ── HYDRA custom headers (backward compatibility) ────
            "X-Payment-Required": "true",
            "X-Payment-Amount": str(pricing["amount_base_units"]),
            "X-Payment-Address": WALLET_ADDRESS,
            "X-Payment-Network": PAYMENT_NETWORK,
            "X-Payment-Token": PAYMENT_TOKEN,
            "X-Payment-Chain-Id": str(CHAIN_ID),
            "X-Payment-Endpoint": path,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": (
                "PAYMENT-REQUIRED, WWW-Authenticate, Accept-Payment, "
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
