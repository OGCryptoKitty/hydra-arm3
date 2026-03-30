"""
HYDRA Arm 3 — Prediction Market Endpoint Pricing Configuration

Pricing for all prediction market intelligence endpoints.
This module defines PREDICTION_PRICING as a standalone dict that is merged
into the main PRICING dict in config/settings.py during integration.

Free endpoints (no entry here — middleware skips them):
  GET  /v1/markets              → FREE  (basic market list — the bait)
  GET  /v1/markets/discovery    → FREE  (full discovery hook with metadata)
  GET  /v1/markets/pricing      → FREE  (pricing transparency endpoint)

Paid endpoints (all require USDC payment via x402 X-Payment-Proof header):
  GET  /v1/markets/feed         → $0.05 USDC   (high-frequency micro feed)
  POST /v1/markets/signals      → $0.25 USDC   (bulk signals — core bot product)
  POST /v1/markets/signal/{id}  → $0.10 USDC   (single market deep signal)
  POST /v1/markets/events       → $0.15 USDC   (event feed matched to markets)
  POST /v1/markets/resolution   → $1.00 USDC   (oracle-grade resolution assessment)
  POST /v1/markets/alpha        → $2.00 USDC   (full alpha report — premium)
  POST /v1/oracle/uma           → $0.50 USDC   (UMA OO formatted assertion data)
  POST /v1/oracle/chainlink     → $0.50 USDC   (Chainlink external adapter format)

All amounts:
  amount_usdc       — human-readable string (for display and Decimal comparison)
  amount_base_units — integer in USDC base units (6 decimals); used by x402 middleware
"""

from __future__ import annotations

from decimal import Decimal

# ─────────────────────────────────────────────────────────────
# Prediction Market Pricing Dict
# ─────────────────────────────────────────────────────────────

PREDICTION_PRICING: dict[str, dict] = {
    # ── Cheapest: micro feed for bot polling ──────────────────────────────
    "/v1/markets/feed": {
        "amount_usdc": Decimal("0.05"),
        "amount_base_units": 50_000,    # 0.05 USDC * 10^6
        "description": (
            "Micro regulatory event feed — latest 10 events from last hour, pre-matched to "
            "active prediction markets. Minimal payload for high-frequency bot polling every 2-5 minutes. "
            "When a HIGH urgency event appears, call /v1/markets/signal/{market_id} for full analysis."
        ),
        "method": "GET",
        "category": "prediction_markets",
        "bot_use_case": "Poll every 2-5 minutes to catch breaking regulatory events before the market reacts",
    },

    # ── Single market deep signal ─────────────────────────────────────────
    "/v1/markets/signal": {
        "amount_usdc": Decimal("0.10"),
        "amount_base_units": 100_000,   # 0.10 USDC * 10^6
        "description": (
            "Single market deep signal — full HYDRA regulatory analysis for one specific "
            "Polymarket condition_id or Kalshi ticker. Includes: regulatory context, key dates, "
            "historical precedent, risk factors, signal direction (bullish_yes/bullish_no/neutral), "
            "and confidence score 0-100. Fastest endpoint — bots call this per-trade."
        ),
        "method": "POST",
        "category": "prediction_markets",
        "bot_use_case": "Call before each trade when you already know which market to enter",
    },

    # ── Bulk signals — core bot product ──────────────────────────────────
    "/v1/markets/signals": {
        "amount_usdc": Decimal("0.25"),
        "amount_base_units": 250_000,   # 0.25 USDC * 10^6
        "description": (
            "Prediction market signals — bulk HYDRA regulatory signals for all matching markets "
            "(Polymarket + Kalshi; Fed/SEC/crypto/regulation). Core pre-trade intelligence for trading bots. "
            "Filters: platform (polymarket/kalshi/all) and category (fed/sec/crypto/regulation/all). "
            "Each signal includes signal direction, confidence 0-100, regulatory context, and key dates."
        ),
        "method": "POST",
        "category": "prediction_markets",
        "bot_use_case": "Call before market open or before sizing a basket of positions across multiple markets",
    },

    # ── Event feed matched to markets ─────────────────────────────────────
    "/v1/markets/events": {
        "amount_usdc": Decimal("0.15"),
        "amount_base_units": 150_000,   # 0.15 USDC * 10^6
        "description": (
            "Regulatory event feed — real-time SEC EDGAR, CFTC, FinCEN, OCC, CFPB events "
            "matched to active prediction markets with impact assessments. "
            "Filters: since_hours (1-168) and agencies (SEC/CFTC/Fed/FinCEN/OCC/CFPB/all). "
            "Each event includes urgency level (high/medium/low) and which markets it affects."
        ),
        "method": "POST",
        "category": "prediction_markets",
        "bot_use_case": "React to breaking regulatory events; use since_hours=1 for real-time monitoring",
    },

    # ── Oracle resolution assessment ─────────────────────────────────────
    "/v1/markets/resolution": {
        "amount_usdc": Decimal("1.00"),
        "amount_base_units": 1_000_000,  # 1.00 USDC * 10^6
        "description": (
            "Oracle resolution assessment — HYDRA's verdict on how a prediction market should resolve. "
            "For UMA bond asserters: determines whether posting a $750 USDC.e bond is safe. "
            "Returns: resolution recommendation (YES/NO), confidence 0-100, evidence summary, "
            "relevant regulations, and sources. Premium pricing reflects bond risk mitigation value."
        ),
        "method": "POST",
        "category": "oracle",
        "bot_use_case": "Call before posting a UMA OOv2 assertion bond — $1.00 cost vs $750 bond risk",
    },

    # ── PREMIUM: Full alpha report ────────────────────────────────────────
    "/v1/markets/alpha": {
        "amount_usdc": Decimal("2.00"),
        "amount_base_units": 2_000_000,  # 2.00 USDC * 10^6
        "description": (
            "Full alpha report — HYDRA's complete trading intelligence for one specific market and position. "
            "Input: market_id, position (yes/no), size_usdc. "
            "Output: HYDRA regulatory probability, edge vs market price, expected value, "
            "risk/reward ratio, Kelly optimal sizing, optimal entry price, "
            "similar historical trades with outcomes, resolution timeline, and trade verdict. "
            "Designed for quant funds and serious traders sizing $1,000+ positions."
        ),
        "method": "POST",
        "category": "prediction_markets",
        "bot_use_case": (
            "High-value pre-trade research for large positions. "
            "At $1,000 position size, a 2% edge improvement from HYDRA analysis covers the $2.00 cost 10x."
        ),
    },

    # ── Oracle: UMA Optimistic Oracle ────────────────────────────────────
    "/v1/oracle/uma": {
        "amount_usdc": Decimal("0.50"),
        "amount_base_units": 500_000,   # 0.50 USDC * 10^6
        "description": (
            "UMA Optimistic Oracle formatted assertion data — complete ancillary data, "
            "proposed price, bond details, and evidence chain for submitting to UMA OOv2 on Polygon. "
            "Ready to submit directly to OptimisticOracleV2 at 0x255483434aba5a75dc60c1391bB162BCd9DE2882. "
            "Bond currency: USDC.e (Polygon standard for Polymarket resolutions)."
        ),
        "method": "POST",
        "category": "oracle",
        "bot_use_case": "Format and verify assertion data before posting UMA bond on Polymarket markets",
    },

    # ── Oracle: Chainlink external adapter ───────────────────────────────
    "/v1/oracle/chainlink": {
        "amount_usdc": Decimal("0.50"),
        "amount_base_units": 500_000,   # 0.50 USDC * 10^6
        "description": (
            "Chainlink External Adapter response — regulatory data formatted for on-chain delivery "
            "via Chainlink node operators. Compatible with Chainlink Any API Direct Request model. "
            "Response format: {\"jobRunID\": id, \"data\": {\"result\": val}, \"statusCode\": 200}. "
            "For node operators: list HYDRA on market.link or configure as EA in node TOML."
        ),
        "method": "POST",
        "category": "oracle",
        "bot_use_case": "Chainlink node operators use this to deliver HYDRA regulatory data on-chain",
    },
}


# ─────────────────────────────────────────────────────────────
# Convenience: pricing display list (for /v1/markets/pricing endpoint)
# ─────────────────────────────────────────────────────────────

def get_prediction_pricing_list() -> list[dict]:
    """
    Returns prediction market pricing as a sorted list for display.

    Free endpoints (not in PREDICTION_PRICING) are included manually
    for completeness in the pricing response.
    """
    free_endpoints = [
        {
            "endpoint": "/v1/markets",
            "method": "GET",
            "amount_usdc": "0.00",
            "amount_base_units": 0,
            "description": (
                "All active regulatory prediction markets — basic info (title, price, volume). "
                "Free discovery hook."
            ),
            "free": True,
        },
        {
            "endpoint": "/v1/markets/discovery",
            "method": "GET",
            "amount_usdc": "0.00",
            "amount_base_units": 0,
            "description": (
                "Full market discovery with HYDRA coverage metadata, domain descriptions, "
                "and paid endpoint guide. Free."
            ),
            "free": True,
        },
        {
            "endpoint": "/v1/markets/pricing",
            "method": "GET",
            "amount_usdc": "0.00",
            "amount_base_units": 0,
            "description": "Pricing for all prediction market endpoints. Free.",
            "free": True,
        },
    ]

    paid_endpoints = [
        {
            "endpoint": path,
            "method": info["method"],
            "amount_usdc": str(info["amount_usdc"]),
            "amount_base_units": info["amount_base_units"],
            "description": info["description"],
            "free": False,
            "bot_use_case": info.get("bot_use_case", ""),
        }
        for path, info in sorted(
            PREDICTION_PRICING.items(),
            key=lambda x: x[1]["amount_base_units"],  # sort by price ascending
        )
    ]

    return free_endpoints + paid_endpoints
