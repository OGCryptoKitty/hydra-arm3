"""
HYDRA Arm 3 — Stripe MPP (Machine Payments Protocol) Integration

Adds MPP as a third payment protocol alongside x402 (CDP) and
X-Payment-Proof (custom on-chain). All three coexist on the same
endpoints — the middleware stack routes based on HTTP headers.

MPP advantages over x402 for micropayments:
  - Session-based: client deposits once, spends against balance
  - Sub-100ms latency (off-chain vouchers vs on-chain verification)
  - Near-zero per-request fees (batch settlement)
  - mpp.dev directory for agent discovery

Protocol flow:
  1. Client GET without auth → 402 + WWW-Authenticate: Payment header
  2. Client creates MPP session, deposits funds
  3. Client retries with Authorization: Payment <credential>
  4. Server validates voucher → 200

Graceful degradation:
  If pympp is not installed, MPP is silently disabled and x402/custom
  middleware handles all payments. No configuration required.

Settlement:
  MPP supports USDC via Tempo stablecoin rail + fiat via Stripe.
  HYDRA accepts both. Funds settle to the same wallet/account.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from config.settings import PRICING, WALLET_ADDRESS, CHAIN_ID

logger = logging.getLogger(__name__)


def build_mpp_routes() -> dict[str, Any]:
    """
    Build MPP route configuration from HYDRA's PRICING dict.

    Maps each endpoint to an MPP charge configuration with
    amount, currency, and description.
    """
    try:
        from pympp import ChargeIntent
    except ImportError:
        logger.info("pympp not installed — MPP protocol disabled")
        return {}

    routes: dict[str, Any] = {}

    method_map = {
        "/v1/markets/feed": "GET",
        "/v1/util/crypto/price": "GET",
        "/v1/util/crypto/balance": "GET",
        "/v1/util/gas": "GET",
        "/v1/util/tx": "GET",
    }

    for path, pricing_info in PRICING.items():
        method = method_map.get(path, "POST")
        amount_usdc = str(pricing_info["amount_usdc"])
        description = pricing_info["description"]

        route_key = f"{method} {path}"
        if path == "/v1/markets/signal":
            route_key = f"{method} {path}/*"

        try:
            routes[route_key] = ChargeIntent(
                amount=amount_usdc,
                currency="USD",
                description=f"HYDRA — {description}",
            )
        except Exception as exc:
            logger.debug("Failed to create ChargeIntent for %s: %s", path, exc)

    logger.info("Built %d MPP route configs", len(routes))
    return routes


def create_mpp_server() -> Any | None:
    """
    Create and configure an MPP server instance.

    Returns None if pympp is not installed (graceful degradation).
    """
    try:
        from pympp import Mpp
    except ImportError:
        logger.info("pympp not available — MPP disabled")
        return None

    try:
        server = Mpp.create(
            name="HYDRA Regulatory Intelligence",
            description=(
                "Real-time regulatory intelligence for prediction markets. "
                "SEC, CFTC, Fed, FinCEN monitoring. Oracle data for UMA and Chainlink. "
                "19 paid endpoints from $0.001 USDC."
            ),
            wallet=WALLET_ADDRESS,
        )
        logger.info("MPP server created: wallet=%s", WALLET_ADDRESS)
        return server
    except TypeError:
        try:
            server = Mpp.create()
            logger.info("MPP server created (basic config)")
            return server
        except Exception as exc:
            logger.warning("MPP server creation failed: %s", exc)
            return None
    except Exception as exc:
        logger.warning("MPP server creation failed: %s", exc)
        return None


def add_mpp_middleware(app: Any) -> bool:
    """
    Add MPP middleware to a FastAPI app.

    Returns True if successfully added, False if pympp not available.
    Coexists with x402 CDP middleware and custom X-Payment-Proof middleware.
    """
    try:
        from pympp.integrations.fastapi import MppMiddleware
    except ImportError:
        try:
            from pympp.fastapi import MppMiddleware
        except ImportError:
            logger.info("pympp FastAPI integration not available — MPP middleware not added")
            return False

    server = create_mpp_server()
    if server is None:
        return False

    routes = build_mpp_routes()
    if not routes:
        logger.info("No MPP routes configured — MPP middleware not added")
        return False

    try:
        app.add_middleware(MppMiddleware, server=server, routes=routes)
        logger.info(
            "MPP middleware added with %d routes — "
            "HYDRA discoverable via mpp.dev directory",
            len(routes),
        )
        return True
    except Exception as exc:
        logger.warning("MPP middleware add failed: %s — trying alternative integration", exc)

    try:
        for route_key, charge in routes.items():
            parts = route_key.split(" ", 1)
            if len(parts) == 2:
                method, path = parts
                server.pay(path=path, amount=str(charge.amount) if hasattr(charge, 'amount') else "0.01")
        logger.info("MPP server configured with %d routes (decorator mode)", len(routes))
        return True
    except Exception as exc:
        logger.warning("MPP alternative integration failed: %s", exc)
        return False


def get_mpp_status() -> dict[str, Any]:
    """Return MPP integration status for monitoring endpoints."""
    try:
        import pympp
        version = getattr(pympp, "__version__", "unknown")
        return {
            "enabled": True,
            "sdk_version": version,
            "protocol": "MPP (Machine Payments Protocol)",
            "settlement": ["USDC (Tempo)", "Fiat (Stripe)"],
            "directory": "https://mpp.dev",
            "endpoints_configured": len(PRICING),
        }
    except ImportError:
        return {
            "enabled": False,
            "reason": "pympp not installed",
            "install": "pip install pympp>=0.6.0",
        }
