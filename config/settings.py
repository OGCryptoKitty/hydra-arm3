"""
HYDRA Arm 3 — Regulatory Intelligence SaaS
Application configuration loaded from environment variables.
"""

import os
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Wallet / Chain Configuration
# ─────────────────────────────────────────────────────────────

# Bootstrap wallet that receives USDC payments
WALLET_ADDRESS: str = os.getenv(
    "WALLET_ADDRESS", "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141"
)

# Base L2 RPC endpoint
BASE_RPC_URL: str = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")

# USDC contract on Base mainnet
USDC_CONTRACT_ADDRESS: str = os.getenv(
    "USDC_CONTRACT_ADDRESS", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
)

# USDC has 6 decimal places
USDC_DECIMALS: int = 6

# ─────────────────────────────────────────────────────────────
# Application Settings
# ─────────────────────────────────────────────────────────────

APP_NAME: str = "HYDRA Arm 3 — Regulatory Intelligence SaaS"
APP_VERSION: str = "1.0.0"
APP_DESCRIPTION: str = (
    "AI-powered regulatory compliance analysis via API. "
    "Pay-per-use in USDC on Base via the x402 HTTP payment protocol."
)

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8402"))

DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

# ─────────────────────────────────────────────────────────────
# Pricing Tiers (in USDC, human-readable)
# These are converted to base units (6 decimals) at verification time.
# ─────────────────────────────────────────────────────────────

PRICING: dict[str, dict] = {
    "/v1/regulatory/scan": {
        "amount_usdc": Decimal("1.00"),
        "description": "Full regulatory risk scan — analyzes a business against all applicable frameworks",
        "amount_base_units": 1_000_000,  # 1.00 USDC * 10^6
    },
    "/v1/regulatory/changes": {
        "amount_usdc": Decimal("0.50"),
        "description": "Recent regulatory changes — fetches latest filings from SEC, CFTC, FinCEN, OCC, CFPB",
        "amount_base_units": 500_000,   # 0.50 USDC * 10^6
    },
    "/v1/regulatory/jurisdiction": {
        "amount_usdc": Decimal("2.00"),
        "description": "Jurisdiction comparison — compares regulatory requirements across US states / countries",
        "amount_base_units": 2_000_000,  # 2.00 USDC * 10^6
    },
    "/v1/regulatory/query": {
        "amount_usdc": Decimal("0.50"),
        "description": "Regulatory Q&A — natural-language answers about regulatory requirements",
        "amount_base_units": 500_000,   # 0.50 USDC * 10^6
    },
    # ── Prediction Market Intelligence ─────────────────────────────
    # Free endpoints (discovery hook and pricing) are NOT in this dict;
    # only paid endpoints are listed here so the middleware enforces payment.
    "/v1/markets/signals": {
        "amount_usdc": Decimal("0.25"),
        "description": (
            "Prediction market signals — bulk HYDRA regulatory signals for all matching markets "
            "(polymarket/kalshi; fed/sec/crypto/regulation). Core pre-trade intelligence for trading bots."
        ),
        "amount_base_units": 250_000,   # 0.25 USDC * 10^6
    },
    "/v1/markets/signal": {
        "amount_usdc": Decimal("0.10"),
        "description": (
            "Single market deep signal — full HYDRA regulatory analysis for one specific "
            "Polymarket condition_id or Kalshi ticker. Includes historical precedent and risk factors."
        ),
        "amount_base_units": 100_000,   # 0.10 USDC * 10^6
    },
    "/v1/markets/events": {
        "amount_usdc": Decimal("0.15"),
        "description": (
            "Regulatory event feed — real-time SEC, CFTC, FinCEN, OCC, CFPB events "
            "matched to active prediction markets with impact assessments."
        ),
        "amount_base_units": 150_000,   # 0.15 USDC * 10^6
    },
    "/v1/markets/resolution": {
        "amount_usdc": Decimal("1.00"),
        "description": (
            "Oracle resolution assessment — HYDRA's verdict on how a prediction market should resolve. "
            "For UMA bond asserters: determines whether posting a $750 USDC.e bond is safe. Premium pricing."
        ),
        "amount_base_units": 1_000_000,  # 1.00 USDC * 10^6
    },
    "/v1/oracle/uma": {
        "amount_usdc": Decimal("0.50"),
        "description": (
            "UMA Optimistic Oracle formatted assertion data — complete ancillary data, "
            "proposed price, bond details, and evidence chain for submitting to UMA OOv2 on Polygon."
        ),
        "amount_base_units": 500_000,   # 0.50 USDC * 10^6
    },
    "/v1/oracle/chainlink": {
        "amount_usdc": Decimal("0.50"),
        "description": (
            "Chainlink External Adapter response — regulatory data formatted for on-chain delivery "
            "via Chainlink node operators. Compatible with Chainlink Any API Direct Request model."
        ),
        "amount_base_units": 500_000,   # 0.50 USDC * 10^6
    },
    "/v1/markets/feed": {
        "amount_usdc": Decimal("0.05"),
        "description": (
            "Micro regulatory event feed — latest 10 events from last hour, pre-matched to "
            "prediction markets. Minimal payload for high-frequency bot polling every few minutes."
        ),
        "amount_base_units": 50_000,    # 0.05 USDC * 10^6
    },
    "/v1/markets/alpha": {
        "amount_usdc": Decimal("2.00"),
        "description": (
            "Full alpha report — regulatory probability, edge vs market price, risk/reward ratio, "
            "Kelly optimal sizing, optimal entry price, similar historical trades, resolution timeline, "
            "and trade verdict. Premium endpoint for quant funds and large-position traders."
        ),
        "amount_base_units": 2_000_000,  # 2.00 USDC * 10^6
    },
}

# ─────────────────────────────────────────────────────────────
# Cache Settings
# ─────────────────────────────────────────────────────────────

# How long to cache RSS feed results (seconds)
FEED_CACHE_TTL: int = int(os.getenv("FEED_CACHE_TTL", "3600"))  # 1 hour

# How long to cache payment verifications (seconds); long enough to prevent replay
PAYMENT_CACHE_TTL: int = int(os.getenv("PAYMENT_CACHE_TTL", "86400"))  # 24 hours

# ─────────────────────────────────────────────────────────────
# EVM Constants
# ─────────────────────────────────────────────────────────────

# keccak256("Transfer(address,address,uint256)") — ERC-20 Transfer event topic0
ERC20_TRANSFER_TOPIC: str = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)

# ─────────────────────────────────────────────────────────────
# Network Identifiers
# ─────────────────────────────────────────────────────────────

PAYMENT_NETWORK: str = "base"
PAYMENT_TOKEN: str = "USDC"
CHAIN_ID: int = 8453  # Base mainnet
