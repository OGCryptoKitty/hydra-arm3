"""
HYDRA Arm 3 — CDP Facilitator Integration

Configures the official x402 Python SDK with Coinbase's CDP facilitator
for automatic Bazaar discovery. This runs alongside HYDRA's custom
X-Payment-Proof middleware — both payment flows are supported.

Standard x402 flow (CDP):
  Client sends X-PAYMENT header → CDP facilitator verifies+settles → 200
  No X-PAYMENT header → 402 with payment requirements (auto-indexed by Bazaar)

Custom flow (legacy, still supported):
  Client sends X-Payment-Proof: <tx_hash> → HYDRA verifies on-chain → 200
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import (
    CHAIN_ID,
    PRICING,
    USDC_CONTRACT_ADDRESS,
    WALLET_ADDRESS,
)

logger = logging.getLogger(__name__)

BASE_MAINNET_NETWORK = f"eip155:{CHAIN_ID}"
CDP_FACILITATOR_URL = "https://x402.org/facilitator"


def build_cdp_route_configs() -> dict[str, Any]:
    """
    Build x402 SDK RouteConfig objects from HYDRA's PRICING dict.

    Maps each HYDRA endpoint to a CDP-compatible route config with
    payment options, descriptions, and MIME types for Bazaar indexing.
    """
    try:
        from x402.http import PaymentOption
        from x402.http.types import RouteConfig
    except ImportError:
        logger.warning("x402 SDK not installed — CDP facilitator disabled. Install with: pip install x402[fastapi,evm]")
        return {}

    routes: dict[str, Any] = {}

    method_map = {
        "/v1/markets/feed": "GET",
        "/v1/util/crypto/price": "GET",
        "/v1/util/crypto/balance": "GET",
    }

    for path, pricing_info in PRICING.items():
        method = method_map.get(path, "POST")
        amount_base_units = str(pricing_info["amount_base_units"])
        description = pricing_info["description"]

        route_key = f"{method} {path}"

        # For parameterized routes, use wildcard
        if path == "/v1/markets/signal":
            route_key = f"{method} {path}/*"

        routes[route_key] = RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact",
                    pay_to=WALLET_ADDRESS,
                    price={
                        "amount": amount_base_units,
                        "asset": USDC_CONTRACT_ADDRESS,
                        "extra": {"name": "USDC", "version": "2"},
                    },
                    network=BASE_MAINNET_NETWORK,
                ),
            ],
            mime_type="application/json",
            description=f"HYDRA Regulatory Intelligence — {description}",
        )

    logger.info("Built %d CDP route configs for Bazaar discovery", len(routes))
    return routes


def create_cdp_server() -> Any | None:
    """
    Create and configure an x402ResourceServer with the CDP facilitator.

    Returns None if the x402 SDK is not installed (graceful degradation).
    The custom X-Payment-Proof middleware continues to work regardless.
    """
    try:
        from x402.http import FacilitatorConfig, HTTPFacilitatorClient
        from x402.mechanisms.evm.exact import ExactEvmServerScheme
        from x402.server import x402ResourceServer
    except ImportError:
        logger.warning("x402 SDK not available — running with custom middleware only")
        return None

    try:
        facilitator = HTTPFacilitatorClient(
            FacilitatorConfig(url=CDP_FACILITATOR_URL)
        )
        server = x402ResourceServer(facilitator)
        server.register(BASE_MAINNET_NETWORK, ExactEvmServerScheme())
        logger.info(
            "CDP facilitator configured: url=%s network=%s wallet=%s",
            CDP_FACILITATOR_URL, BASE_MAINNET_NETWORK, WALLET_ADDRESS,
        )
        return server
    except Exception as exc:
        logger.error("Failed to create CDP server: %s — falling back to custom middleware", exc)
        return None


def add_cdp_middleware(app: Any) -> bool:
    """
    Add the official x402 PaymentMiddlewareASGI to a FastAPI app.

    Returns True if successfully added, False if SDK not available.
    The app continues to work with the custom middleware either way.
    """
    try:
        from x402.http.middleware.fastapi import PaymentMiddlewareASGI
    except ImportError:
        logger.warning("x402 SDK not installed — CDP middleware not added")
        return False

    server = create_cdp_server()
    if server is None:
        return False

    routes = build_cdp_route_configs()
    if not routes:
        logger.warning("No CDP routes configured — CDP middleware not added")
        return False

    try:
        app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
        logger.info(
            "CDP PaymentMiddlewareASGI added with %d routes — "
            "HYDRA is now discoverable via x402 Bazaar",
            len(routes),
        )
        return True
    except Exception as exc:
        logger.error("Failed to add CDP middleware: %s", exc)
        return False
