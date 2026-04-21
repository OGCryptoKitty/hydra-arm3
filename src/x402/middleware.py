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

from decimal import Decimal

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
        "/v1/check/url": {
            "_note": "SAMPLE — pay to get live check",
            "url": "https://example.com",
            "status_code": 200,
            "ok": True,
            "content_type": "text/html",
            "elapsed_ms": 145,
        },
        "/v1/check/dns": {
            "_note": "SAMPLE — pay to get live DNS",
            "domain": "example.com",
            "record_type": "A",
            "records": [{"data": "93.184.216.34", "ttl": 3600}],
        },
        "/v1/check/ssl": {
            "_note": "SAMPLE — pay to get live SSL info",
            "domain": "example.com",
            "valid": True,
            "issuer": {"organizationName": "DigiCert Inc"},
            "days_remaining": 247,
        },
        "/v1/convert/html2md": {
            "_note": "SAMPLE — pay to convert",
            "markdown": "# Example Heading\n\nConverted text...",
            "length": 42,
        },
        "/v1/tools/hash": {
            "_note": "SAMPLE — pay to hash",
            "algorithm": "sha256",
            "hex": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        },
        "/v1/tools/diff": {
            "_note": "SAMPLE — pay to diff",
            "stats": {"lines_added": 3, "lines_removed": 1, "similarity": 0.85},
        },
        "/v1/data/wikipedia": {
            "_note": "SAMPLE — pay to get full article",
            "title": "Bitcoin",
            "description": "Cryptocurrency",
            "extract": "Bitcoin is a decentralized digital currency...",
        },
        "/v1/data/arxiv": {
            "_note": "SAMPLE — pay to get full results",
            "results": [{"title": "Attention Is All You Need", "authors": ["Vaswani et al."], "categories": ["cs.CL"]}],
            "result_count": 10,
        },
        "/v1/data/edgar": {
            "_note": "SAMPLE — pay to get SEC filings",
            "results": [{"filing_type": "10-K", "entity": "Apple Inc", "filed": "2025-10-31"}],
            "result_count": 10,
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

import os as _os
_STATE_DIR = _os.getenv("HYDRA_STATE_DIR", _os.getenv("HYDRA_BOOTSTRAP_DIR", "/tmp/hydra-data"))
_REPLAY_CACHE_FILE = _os.path.join(_STATE_DIR, "used_txhashes.json")

import asyncio as _asyncio
import threading as _threading

_used_tx_cache: TTLCache = TTLCache(maxsize=10_000, ttl=PAYMENT_CACHE_TTL)
_tx_lock = _threading.Lock()


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
    with _tx_lock:
        _used_tx_cache[tx_hash.lower()] = time.time()
    _save_replay_cache()


def _is_tx_used(tx_hash: str) -> bool:
    with _tx_lock:
        return tx_hash.lower() in _used_tx_cache


def _try_claim_tx(tx_hash: str) -> bool:
    """Atomically check-and-claim a tx hash. Returns True if newly claimed."""
    key = tx_hash.lower()
    with _tx_lock:
        if key in _used_tx_cache:
            return False
        _used_tx_cache[key] = time.time()
    _save_replay_cache()
    return True


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
        "/v1/mpp/manifest",
        "/v1/mpp/status",
        "/v1/x402/directory",
        "/v1/x402/stats",
        "/v1/alerts/status",
    })

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # ── Free endpoints pass through with cross-promotion headers ──
        if path in self._FREE_PATHS or not path.startswith("/v1/"):
            response = await call_next(request)
            response.headers["X-HYDRA-Paid-Endpoints"] = (
                "https://hydra-api-nlnj.onrender.com/.well-known/x402.json"
            )
            response.headers["X-HYDRA-Intelligence"] = (
                "https://hydra-api-nlnj.onrender.com/v1/intelligence/alpha ($5 composite signal)"
            )
            return response

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
        # Only pass through if CDP middleware is actually registered
        if request.headers.get("X-PAYMENT") or request.headers.get("x-payment"):
            cdp_active = getattr(request.app.state, "cdp_middleware_active", False)
            if cdp_active:
                return await call_next(request)
            # CDP middleware not active — fall through to X-Payment-Proof check or 402

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

        # ── Replay prevention (atomic claim) ──────────────────
        if not _try_claim_tx(tx_hash):
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
            # Release the claim so the tx can be retried
            with _tx_lock:
                _used_tx_cache.pop(tx_hash.lower(), None)
            return self._error_response(
                402,
                f"Payment verification failed: {result.error}",
                path,
                pricing,
            )
        logger.info("Payment verified and consumed: tx=%s path=%s", tx_hash, path)

        # ── Log to persistent TransactionLog for revenue tracking ─
        try:
            tx_log = getattr(request.app.state, "transaction_log", None)
            if tx_log is not None:
                amount_usdc = Decimal(str(result.amount_received_base_units)) / Decimal("1000000")
                tx_log.log_inbound(
                    tx_hash=tx_hash,
                    amount_usdc=amount_usdc,
                    from_address=result.from_address or "unknown",
                    category="x402-revenue",
                    note=path,
                )
        except Exception as log_exc:
            logger.error("Failed to log payment to TransactionLog: %s", log_exc)

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
            "status": 402,
            "message": "Payment Required",
            "endpoint": path,
            "description": pricing["description"],
            "price": {
                "amount": str(pricing["amount_usdc"]),
                "currency": "USDC",
                "chain": "base",
                "chain_id": CHAIN_ID,
                "decimals": USDC_DECIMALS,
                "amount_base_units": pricing["amount_base_units"],
            },
            "payment_methods": {
                "x402": {
                    "wallet": WALLET_ADDRESS,
                    "token_address": USDC_CONTRACT_ADDRESS,
                    "facilitator": "https://x402.org/facilitator",
                    "protocol_version": 1,
                    "scheme": "exact",
                    "network": f"eip155:{CHAIN_ID}",
                    "proof_header": "X-PAYMENT",
                    "instructions": (
                        "Use any x402-compatible client. The PAYMENT-REQUIRED response header "
                        "contains a base64-encoded JSON payment requirement object."
                    ),
                },
                "direct": {
                    "instruction": (
                        "Send exact USDC amount to wallet address, then retry with "
                        "X-Payment-Proof header containing the transaction hash"
                    ),
                    "wallet": WALLET_ADDRESS,
                    "token_address": USDC_CONTRACT_ADDRESS,
                    "chain": "base",
                    "chain_id": CHAIN_ID,
                    "header": f"X-Payment-Proof: 0x_your_transaction_hash",
                    "steps": [
                        f"Send {pricing['amount_usdc']} USDC to {WALLET_ADDRESS} on Base (chain ID {CHAIN_ID})",
                        "Copy the transaction hash from your wallet or block explorer",
                        "Resend this request with header: X-Payment-Proof: <0x_tx_hash>",
                    ],
                },
                "mpp": {
                    "manifest": "https://hydra-api-nlnj.onrender.com/v1/mpp/manifest",
                    "instruction": "Use Machine Payments Protocol session-based micropayments",
                },
            },
            "sample_response": sample,
            "docs": "https://hydra-api-nlnj.onrender.com/docs",
            "client_sdk": "https://github.com/OGCryptoKitty/hydra-arm3/tree/master/examples",
            "discovery": {
                "x402_manifest": "https://hydra-api-nlnj.onrender.com/.well-known/x402.json",
                "mcp_manifest": "https://hydra-api-nlnj.onrender.com/.well-known/mcp.json",
                "openapi": "https://hydra-api-nlnj.onrender.com/openapi.json",
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
