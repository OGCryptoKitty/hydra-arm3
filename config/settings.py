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

# Base L2 RPC endpoint (primary)
BASE_RPC_URL: str = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")

# Fallback RPC endpoints for payment verification resilience
BASE_RPC_FALLBACKS: list[str] = [
    "https://base.llamarpc.com",
    "https://base.drpc.org",
    "https://1rpc.io/base",
]

# USDC contract on Base mainnet
USDC_CONTRACT_ADDRESS: str = os.getenv(
    "USDC_CONTRACT_ADDRESS", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
)

# USDC has 6 decimal places
USDC_DECIMALS: int = 6

# ─────────────────────────────────────────────────────────────
# Application Settings
# ─────────────────────────────────────────────────────────────

APP_NAME: str = "HYDRA — 402-native paid work engine"
APP_VERSION: str = "2.0.0"
APP_DESCRIPTION: str = (
    "Autonomous regulatory + market intelligence API with 75+ paid endpoints delivering real-time data "
    "from 22+ authoritative sources. Binance real-time prices/orderbook/klines, DexScreener DEX pairs, "
    "Bitcoin fees/mempool/Lightning (mempool.space), Treasury auction results, "
    "live crypto prices (CoinGecko), DeFi TVL/yields (DeFi Llama), "
    "stablecoin peg tracking, multi-chain gas, Fear & Greed Index, ECB forex rates, "
    "Kalshi KXFED market-calibrated Fed rate probabilities, FDIC bank failure monitoring, "
    "FRED economic data, SEC EDGAR, and prediction market signals. "
    "Pay-per-call from $0.001 USDC via x402 on Base L2."
)

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8402"))

DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

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
        "amount_usdc": Decimal("0.10"),
        "description": "Micro regulatory event feed — last 10 events matched to prediction markets. High-frequency bot polling.",
        "amount_base_units": 100_000,
    },
    "/v1/markets/events": {
        "amount_usdc": Decimal("0.50"),
        "description": "Classified regulatory event feed — SEC, CFTC, Fed, FinCEN events tagged by type, agency, and affected prediction markets",
        "amount_base_units": 500_000,
    },
    # ── Prediction Market Signals (Layer 3: Scoring) ──
    "/v1/markets/signal": {
        "amount_usdc": Decimal("2.00"),
        "description": "Scored market signal — HYDRA regulatory probability, expected price impact, risk factors for one prediction market",
        "amount_base_units": 2_000_000,
    },
    "/v1/markets/signals": {
        "amount_usdc": Decimal("5.00"),
        "description": "Bulk scored signals — all active regulatory prediction markets with HYDRA probability, impact scoring, and signal direction",
        "amount_base_units": 5_000_000,
    },
    # ── Prediction Market Signals (Layer 4: Recommendation) ──
    "/v1/markets/alpha": {
        "amount_usdc": Decimal("10.00"),
        "description": "Premium alpha report — regulatory probability, edge vs market price, Kelly sizing, entry price, historical analogues, resolution timeline, trade verdict",
        "amount_base_units": 10_000_000,
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
        "amount_usdc": Decimal("5.00"),
        "description": "UMA Optimistic Oracle assertion data — evidence chain, proposed price, bond parameters for regulatory market resolution",
        "amount_base_units": 5_000_000,
    },
    "/v1/oracle/chainlink": {
        "amount_usdc": Decimal("5.00"),
        "description": "Chainlink External Adapter response — regulatory data formatted for on-chain delivery via Any API Direct Request",
        "amount_base_units": 5_000_000,
    },
    # ── Resolution-as-a-Service ──
    "/v1/markets/resolution": {
        "amount_usdc": Decimal("25.00"),
        "description": "Professional resolution verdict — HYDRA's authoritative assessment of how a prediction market should resolve, with evidence chain and confidence score",
        "amount_base_units": 25_000_000,
    },
    # ── High-Volume Utility Services (agent-optimized pricing) ──
    "/v1/util/scrape": {
        "amount_usdc": Decimal("0.005"),
        "description": "Web scrape — URL to clean structured text. HTML parsed, scripts removed. High-volume agent utility.",
        "amount_base_units": 5_000,
    },
    "/v1/util/crypto/price": {
        "amount_usdc": Decimal("0.001"),
        "description": "Token price lookup — current price, 24h change, market cap, volume for any listed token.",
        "amount_base_units": 1_000,
    },
    "/v1/util/rss": {
        "amount_usdc": Decimal("0.002"),
        "description": "RSS/Atom feed parser — feed URL to structured JSON with parsed entries and metadata.",
        "amount_base_units": 2_000,
    },
    "/v1/util/crypto/balance": {
        "amount_usdc": Decimal("0.001"),
        "description": "Wallet balance on Base L2 — ETH and USDC balance for any address.",
        "amount_base_units": 1_000,
    },
    "/v1/util/gas": {
        "amount_usdc": Decimal("0.001"),
        "description": "Base L2 gas prices — current gas price, base fee, estimated costs for transfers/swaps/mints.",
        "amount_base_units": 1_000,
    },
    "/v1/util/tx": {
        "amount_usdc": Decimal("0.001"),
        "description": "Transaction receipt lookup — confirmation status, gas used, block number, log count.",
        "amount_base_units": 1_000,
    },
    "/v1/batch": {
        "amount_usdc": Decimal("0.01"),
        "description": "Batch up to 5 utility calls in one request. Saves gas costs vs individual x402 payments.",
        "amount_base_units": 10_000,
    },
    # ── Extraction Services ──────────────────────────────────────
    "/v1/extract/url": {
        "amount_usdc": Decimal("0.01"),
        "description": "Structured web extraction — title, headings, clean text, links, OpenGraph metadata from any URL.",
        "amount_base_units": 10_000,
    },
    "/v1/extract/multi": {
        "amount_usdc": Decimal("0.05"),
        "description": "Batch extraction from up to 5 URLs in parallel. Structured output per URL.",
        "amount_base_units": 50_000,
    },
    "/v1/extract/search": {
        "amount_usdc": Decimal("0.02"),
        "description": "Web search with structured result extraction — titles, snippets, URLs.",
        "amount_base_units": 20_000,
    },
    # ── Web Infrastructure Checks ────────────────────────────────
    "/v1/check/url": {
        "amount_usdc": Decimal("0.005"),
        "description": "URL health check — status code, response time, redirect chain, content type.",
        "amount_base_units": 5_000,
    },
    "/v1/check/dns": {
        "amount_usdc": Decimal("0.005"),
        "description": "DNS record lookup — A, AAAA, MX, TXT, NS, CNAME via Google DNS-over-HTTPS.",
        "amount_base_units": 5_000,
    },
    "/v1/check/ssl": {
        "amount_usdc": Decimal("0.005"),
        "description": "SSL certificate inspection — issuer, expiry, SANs, protocol, days remaining.",
        "amount_base_units": 5_000,
    },
    "/v1/check/headers": {
        "amount_usdc": Decimal("0.003"),
        "description": "HTTP response headers with security headers analysis and score.",
        "amount_base_units": 3_000,
    },
    # ── Format Conversion ────────────────────────────────────────
    "/v1/convert/html2md": {
        "amount_usdc": Decimal("0.005"),
        "description": "HTML to Markdown — preserves headings, lists, links, code blocks, tables.",
        "amount_base_units": 5_000,
    },
    "/v1/convert/json2csv": {
        "amount_usdc": Decimal("0.003"),
        "description": "JSON array of objects to CSV with auto-detected headers.",
        "amount_base_units": 3_000,
    },
    "/v1/convert/csv2json": {
        "amount_usdc": Decimal("0.003"),
        "description": "CSV text to JSON array of objects. First row = headers.",
        "amount_base_units": 3_000,
    },
    # ── Developer Tools ──────────────────────────────────────────
    "/v1/tools/hash": {
        "amount_usdc": Decimal("0.001"),
        "description": "Hash text with SHA-256, SHA-512, MD5, SHA-1, or SHA3-256.",
        "amount_base_units": 1_000,
    },
    "/v1/tools/encode": {
        "amount_usdc": Decimal("0.001"),
        "description": "Encode/decode text — Base64, URL encoding, hex.",
        "amount_base_units": 1_000,
    },
    "/v1/tools/diff": {
        "amount_usdc": Decimal("0.003"),
        "description": "Unified diff between two texts with change stats and similarity ratio.",
        "amount_base_units": 3_000,
    },
    "/v1/tools/validate/json": {
        "amount_usdc": Decimal("0.001"),
        "description": "JSON syntax validation with pretty-print and structure info.",
        "amount_base_units": 1_000,
    },
    "/v1/tools/validate/email": {
        "amount_usdc": Decimal("0.002"),
        "description": "Email format validation with MX record check.",
        "amount_base_units": 2_000,
    },
    # ── Public Data Search ───────────────────────────────────────
    "/v1/data/wikipedia": {
        "amount_usdc": Decimal("0.01"),
        "description": "Wikipedia article summary — extract, thumbnail, description, page URL.",
        "amount_base_units": 10_000,
    },
    "/v1/data/arxiv": {
        "amount_usdc": Decimal("0.02"),
        "description": "arXiv academic paper search — titles, authors, abstracts, PDF links.",
        "amount_base_units": 20_000,
    },
    "/v1/data/edgar": {
        "amount_usdc": Decimal("0.02"),
        "description": "SEC EDGAR filing search — 10-K, 10-Q, 8-K by company, ticker, or keyword.",
        "amount_base_units": 20_000,
    },
    # ── x402 Ecosystem Hub ──────────────────────────────────────
    "/v1/x402/status": {
        "amount_usdc": Decimal("0.005"),
        "description": "Real-time health and capability check of any x402 service — manifest, endpoints, pricing.",
        "amount_base_units": 5_000,
    },
    "/v1/x402/route": {
        "amount_usdc": Decimal("0.001"),
        "description": "Intelligent x402 service routing — find the best service for a capability request.",
        "amount_base_units": 1_000,
    },
    # ── Composite Intelligence ──────────────────────────────────
    "/v1/intelligence/pulse": {
        "amount_usdc": Decimal("0.50"),
        "description": "Hourly regulatory pulse — aggregated SEC, CFTC, FinCEN, Fed, Treasury activity with risk signals.",
        "amount_base_units": 500_000,
    },
    "/v1/intelligence/alpha": {
        "amount_usdc": Decimal("5.00"),
        "description": "Composite alpha signal — regulatory risk + Fed rate probability + prediction market sentiment + directional bias.",
        "amount_base_units": 5_000_000,
    },
    "/v1/intelligence/risk-score": {
        "amount_usdc": Decimal("2.00"),
        "description": "Real-time 0-100 risk score for any token or protocol based on regulatory exposure and agency attention.",
        "amount_base_units": 2_000_000,
    },
    "/v1/intelligence/digest": {
        "amount_usdc": Decimal("1.00"),
        "description": "Daily market + regulatory digest — comprehensive summary for compliance teams and trading agents.",
        "amount_base_units": 1_000_000,
    },
    "/v1/intelligence/economic-snapshot": {
        "amount_usdc": Decimal("0.50"),
        "description": "Atomic real-time economic data — FRED, BLS, Treasury yields, Federal Register rulemakings. Live at request time.",
        "amount_base_units": 500_000,
    },
    "/v1/intelligence/regulatory-pulse-live": {
        "amount_usdc": Decimal("0.50"),
        "description": "Live regulatory pulse — SEC EDGAR search, Federal Register API, Congress bill tracker. Real-time at request.",
        "amount_base_units": 500_000,
    },
    "/v1/intelligence/bank-failures": {
        "amount_usdc": Decimal("0.25"),
        "description": "FDIC bank failure monitor — recent failures, resolution details, losses. BankFind API live data.",
        "amount_base_units": 250_000,
    },
    # ── Push Alert System ───────────────────────────────────────
    "/v1/alerts/subscribe": {
        "amount_usdc": Decimal("0.10"),
        "description": "Register for push alerts — webhook delivery of regulatory events matching your conditions. $0.10 per 100 alerts.",
        "amount_base_units": 100_000,
    },
    "/v1/alerts/feed": {
        "amount_usdc": Decimal("0.05"),
        "description": "Real-time regulatory alert feed — last 24 hours of detected events across all monitored sources.",
        "amount_base_units": 50_000,
    },
    # ── Portfolio Intelligence ──────────────────────────────────
    "/v1/portfolio/scan": {
        "amount_usdc": Decimal("10.00"),
        "description": "Portfolio-level regulatory risk scan — up to 20 tokens/protocols with aggregate risk and cross-correlation.",
        "amount_base_units": 10_000_000,
    },
    "/v1/portfolio/watchlist": {
        "amount_usdc": Decimal("2.00"),
        "description": "Portfolio regulatory watchlist — recent agency mentions and alert levels for up to 20 assets.",
        "amount_base_units": 2_000_000,
    },
    "/v1/portfolio/market-brief": {
        "amount_usdc": Decimal("3.00"),
        "description": "Executive market brief — regulatory events + Fed signal + prediction markets in one comprehensive view.",
        "amount_base_units": 3_000_000,
    },
    # ── Live Market Data (perpetually live, no API key) ─────────
    "/v1/market/prices": {
        "amount_usdc": Decimal("0.001"),
        "description": "Live crypto prices, market caps, 24h change via CoinGecko. Up to 20 coins.",
        "amount_base_units": 1_000,
    },
    "/v1/market/global": {
        "amount_usdc": Decimal("0.001"),
        "description": "Global crypto market overview — total market cap, BTC/ETH dominance, 24h volume.",
        "amount_base_units": 1_000,
    },
    "/v1/market/trending": {
        "amount_usdc": Decimal("0.001"),
        "description": "Top trending cryptocurrencies (most searched last 24h) via CoinGecko.",
        "amount_base_units": 1_000,
    },
    "/v1/market/fear-greed": {
        "amount_usdc": Decimal("0.001"),
        "description": "Crypto Fear & Greed Index — 0-100 score with 7-day history.",
        "amount_base_units": 1_000,
    },
    "/v1/market/gas": {
        "amount_usdc": Decimal("0.001"),
        "description": "Live gas prices across Ethereum, Base, Arbitrum, Optimism, Polygon from public RPCs.",
        "amount_base_units": 1_000,
    },
    "/v1/market/stablecoins": {
        "amount_usdc": Decimal("0.002"),
        "description": "Top 20 stablecoins with circulating supply and real-time peg deviation tracking.",
        "amount_base_units": 2_000,
    },
    "/v1/market/defi/tvl": {
        "amount_usdc": Decimal("0.002"),
        "description": "Top 25 DeFi protocols by TVL with 1d/7d change via DeFi Llama.",
        "amount_base_units": 2_000,
    },
    "/v1/market/defi/yields": {
        "amount_usdc": Decimal("0.005"),
        "description": "Top DeFi yield opportunities across all chains — APY, TVL, IL risk, stablecoin flag.",
        "amount_base_units": 5_000,
    },
    "/v1/market/defi/chains": {
        "amount_usdc": Decimal("0.001"),
        "description": "Top 30 blockchains ranked by total DeFi TVL via DeFi Llama.",
        "amount_base_units": 1_000,
    },
    "/v1/market/forex": {
        "amount_usdc": Decimal("0.001"),
        "description": "Major forex rates from the European Central Bank — ~30 currency pairs vs EUR.",
        "amount_base_units": 1_000,
    },
    "/v1/market/snapshot": {
        "amount_usdc": Decimal("0.05"),
        "description": "Complete market snapshot — crypto prices, global market, fear/greed, gas, stablecoins in one call.",
        "amount_base_units": 50_000,
    },
    "/v1/market/binance/prices": {
        "amount_usdc": Decimal("0.002"),
        "description": "Real-time Binance prices with 24h stats — volume, high/low, trades, bid/ask.",
        "amount_base_units": 2_000,
    },
    "/v1/market/binance/orderbook": {
        "amount_usdc": Decimal("0.005"),
        "description": "Binance order book with bids, asks, and spread for any trading pair.",
        "amount_base_units": 5_000,
    },
    "/v1/market/binance/klines": {
        "amount_usdc": Decimal("0.005"),
        "description": "Binance candlestick/OHLCV data for charting and technical analysis.",
        "amount_base_units": 5_000,
    },
    "/v1/market/dex/token": {
        "amount_usdc": Decimal("0.01"),
        "description": "All DEX trading pairs for a token across all chains — price, volume, liquidity via DexScreener.",
        "amount_base_units": 10_000,
    },
    "/v1/market/dex/search": {
        "amount_usdc": Decimal("0.005"),
        "description": "Search DEX pairs by name, symbol, or address across all chains via DexScreener.",
        "amount_base_units": 5_000,
    },
    "/v1/market/bitcoin/fees": {
        "amount_usdc": Decimal("0.002"),
        "description": "Bitcoin fees, mempool stats, hashrate, difficulty via mempool.space. Real-time.",
        "amount_base_units": 2_000,
    },
    "/v1/market/bitcoin/lightning": {
        "amount_usdc": Decimal("0.002"),
        "description": "Bitcoin Lightning Network stats — nodes, channels, capacity, fee rates.",
        "amount_base_units": 2_000,
    },
    "/v1/market/treasury/auctions": {
        "amount_usdc": Decimal("0.005"),
        "description": "U.S. Treasury auction results — yield, bid-to-cover, accepted/tendered. Tier 1 government data.",
        "amount_base_units": 5_000,
    },
    # ── Task Orchestration ──────────────────────────────────────
    "/v1/orchestrate": {
        "amount_usdc": Decimal("0.05"),
        "description": "Multi-step task orchestration — execute up to 10 HYDRA endpoint calls in one request.",
        "amount_base_units": 50_000,
    },
}

# ─────────────────────────────────────────────────────────────
# Cache Settings
# ─────────────────────────────────────────────────────────────

# How long to cache RSS feed results (seconds)
FEED_CACHE_TTL: int = int(os.getenv("FEED_CACHE_TTL", "600"))  # 10 minutes (was 1 hour)

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
