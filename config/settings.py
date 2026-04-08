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

# CORS allowed origins (comma-separated). Use "*" for public API (default).
CORS_ALLOWED_ORIGINS: list[str] = os.getenv(
    "CORS_ALLOWED_ORIGINS", "*"
).split(",") if os.getenv("CORS_ALLOWED_ORIGINS") else ["*"]

# ─────────────────────────────────────────────────────────────
# Pricing Tiers (in USDC, human-readable)
# These are converted to base units (6 decimals) at verification time.
# ─────────────────────────────────────────────────────────────

PRICING: dict[str, dict] = {
    # ── Core Regulatory Intelligence ──────────────────────────
    "/v1/regulatory/scan": {
        "amount_usdc": Decimal("2.00"),
        "description": "Full regulatory risk scan — analyzes a business against all applicable frameworks with scored impact assessment",
        "amount_base_units": 2_000_000,
    },
    "/v1/regulatory/changes": {
        "amount_usdc": Decimal("1.00"),
        "description": "Classified regulatory changes — SEC, CFTC, FinCEN, OCC, CFPB filings with event type tags and market impact scores",
        "amount_base_units": 1_000_000,
    },
    "/v1/regulatory/jurisdiction": {
        "amount_usdc": Decimal("3.00"),
        "description": "Jurisdiction comparison with compliance cost modeling across US states and international frameworks",
        "amount_base_units": 3_000_000,
    },
    "/v1/regulatory/query": {
        "amount_usdc": Decimal("1.00"),
        "description": "Regulatory Q&A — scored answers with statutory citations and confidence levels",
        "amount_base_units": 1_000_000,
    },
    # ── Prediction Market Signals (Layer 1-2: Collection + Classification) ──
    "/v1/markets/feed": {
        "amount_usdc": Decimal("0.25"),
        "description": "Micro regulatory event feed — last 10 events matched to prediction markets. High-frequency bot polling.",
        "amount_base_units": 250_000,
    },
    "/v1/markets/events": {
        "amount_usdc": Decimal("1.50"),
        "description": "Classified regulatory event feed — SEC, CFTC, Fed, FinCEN events tagged by type, agency, and affected prediction markets",
        "amount_base_units": 1_500_000,
    },
    # ── Prediction Market Signals (Layer 3: Scoring) ──
    "/v1/markets/signal": {
        "amount_usdc": Decimal("5.00"),
        "description": "Scored market signal — HYDRA regulatory probability, expected price impact, risk factors for one prediction market",
        "amount_base_units": 5_000_000,
    },
    "/v1/markets/signals": {
        "amount_usdc": Decimal("15.00"),
        "description": "Bulk scored signals — all active regulatory prediction markets with HYDRA probability, impact scoring, and signal direction",
        "amount_base_units": 15_000_000,
    },
    # ── Prediction Market Signals (Layer 4: Recommendation) ──
    "/v1/markets/alpha": {
        "amount_usdc": Decimal("30.00"),
        "description": "Premium alpha report — regulatory probability, edge vs market price, Kelly sizing, entry price, historical analogues, resolution timeline, trade verdict",
        "amount_base_units": 30_000_000,
    },
    # ── Fed Decision Package (highest-value recurring category) ──
    "/v1/fed/signal": {
        "amount_usdc": Decimal("5.00"),
        "description": "Pre-FOMC signal — speech analysis, dot plot tracking, employment data interpretation, rate probability model",
        "amount_base_units": 5_000_000,
    },
    "/v1/fed/decision": {
        "amount_usdc": Decimal("25.00"),
        "description": "Real-time FOMC decision classification — HOLD/CUT/HIKE + basis points within 30 seconds of release. Cryptographic timestamp.",
        "amount_base_units": 25_000_000,
    },
    "/v1/fed/resolution": {
        "amount_usdc": Decimal("50.00"),
        "description": "FOMC resolution verdict with full evidence chain — formatted for UMA bond assertion. Includes statement text, vote breakdown, and dot plot delta.",
        "amount_base_units": 50_000_000,
    },
    # ── Oracle Integration ──
    "/v1/oracle/uma": {
        "amount_usdc": Decimal("10.00"),
        "description": "UMA Optimistic Oracle assertion data — evidence chain, proposed price, bond parameters for regulatory market resolution",
        "amount_base_units": 10_000_000,
    },
    "/v1/oracle/chainlink": {
        "amount_usdc": Decimal("10.00"),
        "description": "Chainlink External Adapter response — regulatory data formatted for on-chain delivery via Any API Direct Request",
        "amount_base_units": 10_000_000,
    },
    # ── Resolution-as-a-Service ──
    "/v1/markets/resolution": {
        "amount_usdc": Decimal("50.00"),
        "description": "Professional resolution verdict — HYDRA's authoritative assessment of how a prediction market should resolve, with evidence chain and confidence score",
        "amount_base_units": 50_000_000,
    },
}

# ─────────────────────────────────────────────────────────────
# Cache Settings
# ─────────────────────────────────────────────────────────────

# How long to cache RSS feed results (seconds)
FEED_CACHE_TTL: int = int(os.getenv("FEED_CACHE_TTL", "3600"))  # 1 hour

# How long to cache payment verifications (seconds); prevents replay attacks.
# Shorter TTL reduces risk from chain reorgs invalidating cached verifications.
PAYMENT_CACHE_TTL: int = int(os.getenv("PAYMENT_CACHE_TTL", "3600"))  # 1 hour

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

# ─────────────────────────────────────────────────────────────
# State / Data Directory
# ─────────────────────────────────────────────────────────────

# Directory for persistent state (state.json, transactions.jsonl, remittance-config.json)
HYDRA_STATE_DIR: str = os.getenv("HYDRA_STATE_DIR", os.getenv("HYDRA_BOOTSTRAP_DIR", "/app/data"))
