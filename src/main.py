"""
HYDRA Arm 3 — Regulatory Intelligence SaaS
FastAPI application entry point.

Start with:
  uvicorn src.main:app --host 0.0.0.0 --port 8402

Or via Docker:
  docker-compose up

Payment protocol: x402 (HTTP 402 Payment Required)
Payment token: USDC on Base (chain ID 8453)
Receiving wallet: 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141

Autonomous runtime:
  - HydraAutomaton heartbeat: starts as a background asyncio task on startup
  - Survival tiers: CRITICAL / MINIMAL / VIABLE / FUNDED / SURPLUS
  - Auto-remittance: triggers at $5,000 USDC surplus
  - System endpoints: /system/* (localhost or bearer token protected)

This file is the COMPLETE replacement for src/main.py.
Copy to src/main.py to apply.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import config.settings as settings
from src.api.routes import router
from src.api.prediction_routes import prediction_router
from src.api.system_routes import system_router
from src.api.fed_routes import fed_router
from src.runtime.automaton import HydraAutomaton, set_automaton
from src.runtime.constitution import ConstitutionCheck
from src.runtime.lifecycle import LifecycleManager
from src.runtime.remittance import RemittanceManager
from src.runtime.transaction_log import TransactionLog
from src.x402.middleware import X402PaymentMiddleware

# ─────────────────────────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application startup and shutdown lifecycle.

    Startup:
      1. Initialise all runtime managers (RemittanceManager, ConstitutionCheck,
         TransactionLog, LifecycleManager) and attach to app.state for DI.
      2. Start HydraAutomaton heartbeat as an asyncio background task.

    Shutdown:
      3. Gracefully stop the HydraAutomaton heartbeat.
    """
    logger.info("=" * 60)
    logger.info("HYDRA Arm 3 — Regulatory Intelligence SaaS")
    logger.info("Version : %s", settings.APP_VERSION)
    logger.info("Network : %s (chain %d)", settings.PAYMENT_NETWORK, settings.CHAIN_ID)
    logger.info("Token   : %s", settings.PAYMENT_TOKEN)
    logger.info("Wallet  : %s", settings.WALLET_ADDRESS)
    logger.info("RPC URL : %s", settings.BASE_RPC_URL)
    logger.info("Port    : %d", settings.PORT)
    logger.info("=" * 60)

    # ── Initialise runtime managers and attach to app.state ──
    try:
        app.state.constitution_check = ConstitutionCheck()
        logger.info("ConstitutionCheck initialised.")
    except Exception as exc:
        logger.error("Failed to initialise ConstitutionCheck: %s", exc)
        app.state.constitution_check = None

    try:
        app.state.transaction_log = TransactionLog()
        logger.info("TransactionLog initialised.")
    except Exception as exc:
        logger.error("Failed to initialise TransactionLog: %s", exc)
        app.state.transaction_log = None

    try:
        app.state.lifecycle_manager = LifecycleManager()
        logger.info("LifecycleManager initialised (phase: %s).", app.state.lifecycle_manager.current_phase.name)
    except Exception as exc:
        logger.error("Failed to initialise LifecycleManager: %s", exc)
        app.state.lifecycle_manager = None

    try:
        app.state.remittance_manager = RemittanceManager(
            constitution_checker=app.state.constitution_check,
            transaction_logger=app.state.transaction_log,
        )
        logger.info("RemittanceManager initialised.")
        if app.state.remittance_manager.receiving_wallet:
            logger.info(
                "Receiving wallet configured: %s...",
                app.state.remittance_manager.receiving_wallet[:8],
            )
        else:
            logger.info("No receiving wallet configured — remittance disabled until set.")
    except Exception as exc:
        logger.error("Failed to initialise RemittanceManager: %s", exc)
        app.state.remittance_manager = None

    # ── Start HydraAutomaton heartbeat as background asyncio task ──
    try:
        # Load private key from wallet.json for automaton
        import json, os
        pk = os.getenv("WALLET_PRIVATE_KEY", "")
        if not pk:
            try:
                wf = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "hydra-bootstrap", "wallet.json")
                with open(wf) as f:
                    pk = json.load(f).get("private_key", "")
            except Exception:
                pk = "0x" + "00" * 32  # placeholder — automaton runs in read-only mode
        automaton = HydraAutomaton(
            wallet_address=settings.WALLET_ADDRESS,
            private_key=pk,
            base_rpc_url=settings.BASE_RPC_URL,
        )
        heartbeat_task = asyncio.create_task(
            automaton.run(), name="hydra-automaton-heartbeat"
        )
        app.state.automaton = automaton
        set_automaton(automaton)
        logger.info("HydraAutomaton heartbeat task started.")
    except Exception as exc:
        logger.error("Failed to start HydraAutomaton: %s", exc)
        app.state.automaton = None
        heartbeat_task = None

    yield

    # ── Graceful shutdown ─────────────────────────────────────
    logger.info("HYDRA Arm 3 shutting down.")
    if heartbeat_task and not heartbeat_task.done():
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            logger.info("HydraAutomaton heartbeat cancelled.")
        except Exception as exc:
            logger.warning("Error stopping automaton: %s", exc)


# ─────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "HYDRA Arm 3 API",
        "url":  "https://github.com/hydra-arm3",
    },
    license_info={
        "name": "Proprietary",
    },
    openapi_tags=[
        {
            "name": "System",
            "description": "Health check and pricing — free endpoints",
        },
        {
            "name": "System Management",
            "description": (
                "Automaton management endpoints — **localhost or bearer token required**. "
                "Configure receiving wallet, view treasury status, trigger remittance, "
                "and inspect the transaction log."
            ),
        },
        {
            "name": "Regulatory Intelligence",
            "description": (
                "Paid endpoints — require USDC payment via x402 protocol. "
                "Send USDC to the wallet address on Base (chain 8453), "
                "then include the tx hash in X-Payment-Proof header."
            ),
        },
        {
            "name": "Prediction Markets",
            "description": (
                "Prediction market integration — regulatory signals for Polymarket, Kalshi, "
                "and oracle data feeds. Free discovery endpoints + paid trading signals."
            ),
        },
        {
            "name": "Fed Decision Package",
            "description": (
                "Federal Reserve / FOMC intelligence — the highest-value recurring regulatory data category. "
                "$80M+ volume per FOMC meeting. Pre-decision signals, real-time classification, resolution verdicts."
            ),
        },
    ],
)


# ─────────────────────────────────────────────────────────────
# Middleware Stack (order matters — added last = runs first)
# ─────────────────────────────────────────────────────────────

# 1. CORS — must be first (outermost) middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Accept",
        "Authorization",
        "X-Payment-Proof",
        "X-Payment-Required",
        "X-Payment-Amount",
        "X-Payment-Address",
        "X-Payment-Network",
        "X-Payment-Token",
        "X-Payment-Chain-Id",
        "X-Payment-Endpoint",
        "X-Payment-Verified",
        "X-Payment-Tx",
    ],
    expose_headers=[
        "X-Payment-Required",
        "X-Payment-Amount",
        "X-Payment-Address",
        "X-Payment-Network",
        "X-Payment-Token",
        "X-Payment-Chain-Id",
        "X-Payment-Endpoint",
        "X-Payment-Verified",
        "X-Payment-Tx",
        "X-Payment-Amount-Received",
    ],
)

# 2. x402 Payment Middleware — intercepts paid endpoints
app.add_middleware(X402PaymentMiddleware)


# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────

# Public + paid regulatory endpoints
app.include_router(router)

# Prediction market integration endpoints
app.include_router(prediction_router)

# Fed Decision Package endpoints
app.include_router(fed_router)

# System management endpoints (prefix="" — routes already carry /system/ prefix)
app.include_router(system_router, prefix="")


# ─────────────────────────────────────────────────────────────
# Static files and landing page
# ─────────────────────────────────────────────────────────────

import json as _json
import os as _os

# FIX: Explicit route for x402 discovery manifest — StaticFiles mount is unreliable
# on Render. This explicit route always works regardless of static file serving.
@app.get("/.well-known/x402.json", include_in_schema=False)
async def x402_discovery():
    """Serve x402 service discovery manifest."""
    manifest_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(__file__)),
        "static", ".well-known", "x402.json",
    )
    try:
        with open(manifest_path) as f:
            return _json.load(f)
    except FileNotFoundError:
        logger.warning("x402 manifest not found at %s — using inline fallback", manifest_path)
        return {
            "name": "HYDRA Regulatory Intelligence",
            "url": "https://hydra-api-nlnj.onrender.com",
            "payment": {
                "network": "base",
                "chain_id": 8453,
                "token": "USDC",
                "token_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "wallet": "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141",
            },
            "docs": "https://hydra-api-nlnj.onrender.com/docs",
            "pricing": "https://hydra-api-nlnj.onrender.com/pricing",
        }


# Serve .well-known directory for x402 service discovery (backup static mount)
_static_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "static")
_well_known_dir = _os.path.join(_static_dir, ".well-known")
if _os.path.exists(_well_known_dir):
    app.mount("/.well-known", StaticFiles(directory=_well_known_dir), name="well-known")
    logger.info("Mounted .well-known directory from %s", _well_known_dir)
else:
    logger.warning(".well-known directory not found at %s — x402 discovery manifest unavailable", _well_known_dir)


# Serve landing page at root — MUST come after static mount to avoid route conflict
@app.get("/", response_class=FileResponse, include_in_schema=False, tags=["System"])
async def landing_page() -> FileResponse:
    """Serve the HYDRA HTML landing page at the root URL."""
    _index_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "index.html")
    if _os.path.exists(_index_path):
        return FileResponse(_index_path, media_type="text/html")
    # Fallback to JSON if index.html is missing
    from fastapi.responses import JSONResponse as _JSONResponse
    return _JSONResponse(content={
        "name": "HYDRA Regulatory Intelligence",
        "status": "operational",
        "docs": "/docs",
        "pricing": "/pricing",
        "discovery": "/.well-known/x402.json",
        "payment_protocol": "x402",
        "payment_token": "USDC on Base (Chain 8453)",
        "wallet": "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141",
    })


# ─────────────────────────────────────────────────────────────
# Health endpoint override — includes automaton status
# ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], include_in_schema=True)
async def health_check(request: Request) -> JSONResponse:
    """
    Returns application health status and automaton snapshot.
    No payment required. Publicly accessible.
    """
    automaton_status: dict = {}
    try:
        automaton = getattr(request.app.state, "automaton", None)
        if automaton is None:
            from src.runtime.automaton import get_automaton
            automaton = get_automaton()
        automaton_status = automaton.get_status()
    except Exception as exc:
        logger.debug("Could not fetch automaton status for /health: %s", exc)

    # Include receiving wallet configuration state
    wallet_configured = False
    try:
        rm = getattr(request.app.state, "remittance_manager", None)
        if rm is None:
            from src.runtime.remittance import RemittanceManager
            rm = RemittanceManager()
        wallet_configured = rm.receiving_wallet is not None
    except Exception:
        pass

    return JSONResponse(
        status_code=200,
        content={
            "status":                       "ok",
            "version":                      settings.APP_VERSION,
            "app":                          settings.APP_NAME,
            "payment_network":              settings.PAYMENT_NETWORK,
            "payment_token":                settings.PAYMENT_TOKEN,
            "wallet":                       settings.WALLET_ADDRESS,
            "receiving_wallet_configured":  wallet_configured,
            "automaton":                    automaton_status or None,
        },
    )


# Metrics endpoint — operational monitoring
# ─────────────────────────────────────────────────────────────

@app.get("/metrics", tags=["System"], include_in_schema=True)
async def metrics(request: Request) -> JSONResponse:
    """
    Operational metrics for monitoring dashboards.
    Returns uptime, transaction counts, balance, and endpoint pricing summary.
    No payment required.
    """
    from src.runtime.transaction_log import TransactionLog

    uptime_seconds = 0.0
    balance_usdc = "0.00"
    automaton_phase = "UNKNOWN"
    try:
        automaton = getattr(request.app.state, "automaton", None)
        if automaton:
            status = automaton.get_status()
            uptime_seconds = status.get("uptime_seconds", 0)
            balance_usdc = status.get("balance_usdc", "0")
            automaton_phase = status.get("phase", "UNKNOWN")
    except Exception:
        pass

    tx_summary = {}
    try:
        tl = TransactionLog()
        tx_summary = tl.get_full_summary()
    except Exception:
        pass

    return JSONResponse(content={
        "uptime_seconds": uptime_seconds,
        "phase": automaton_phase,
        "balance_usdc": balance_usdc,
        "total_revenue_usdc": tx_summary.get("total_revenue_usdc", "0"),
        "total_distributions_usdc": tx_summary.get("total_distributions_usdc", "0"),
        "transaction_count": tx_summary.get("transaction_count", 0),
        "remittance_threshold_usdc": "1000",
        "endpoint_count": len(settings.PRICING),
        "llm_enabled": bool(_os.getenv("ANTHROPIC_API_KEY")),
        "version": settings.APP_VERSION,
    })


@app.get("/metrics/revenue", tags=["System"], include_in_schema=True)
async def revenue_metrics(request: Request) -> JSONResponse:
    """
    Revenue analytics — per-endpoint breakdown, net profit, call counts.
    No payment required. Useful for monitoring revenue velocity.
    """
    from src.runtime.transaction_log import TransactionLog

    try:
        tl = getattr(request.app.state, "transaction_log", None)
        if tl is None:
            tl = TransactionLog()
        summary = tl.get_full_summary()
    except Exception:
        summary = {}

    pricing_summary = {}
    for path, info in settings.PRICING.items():
        pricing_summary[path] = {
            "price_usdc": str(info["amount_usdc"]),
            "revenue_usdc": summary.get("revenue_by_endpoint", {}).get(path, {}).get("revenue_usdc", "0.00"),
            "calls": summary.get("revenue_by_endpoint", {}).get(path, {}).get("calls", 0),
        }

    return JSONResponse(content={
        "total_revenue_usdc": summary.get("total_revenue_usdc", "0.00"),
        "total_distributions_usdc": summary.get("total_distributions_usdc", "0.00"),
        "net_profit_usdc": summary.get("net_profit_usdc", "0.00"),
        "transaction_count": summary.get("transaction_count", 0),
        "endpoints": pricing_summary,
        "treasury_wallet": settings.WALLET_ADDRESS,
        "version": settings.APP_VERSION,
    })


# ─────────────────────────────────────────────────────────────
# Global Exception Handlers
# ─────────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return structured 404 with available endpoint list."""
    return JSONResponse(
        status_code=404,
        content={
            "error":   "Not Found",
            "message": f"Endpoint {request.url.path} does not exist.",
            "available_endpoints": [
                "GET  /health",
                "GET  /pricing",
                "POST /v1/regulatory/scan         ($1.00 USDC)",
                "POST /v1/regulatory/changes      ($0.50 USDC)",
                "POST /v1/regulatory/jurisdiction ($2.00 USDC)",
                "POST /v1/regulatory/query        ($0.50 USDC)",
                "--- System (localhost/bearer token) ---",
                "POST /system/wallet",
                "GET  /system/remittance/status",
                "POST /system/remittance/execute",
                "GET  /system/transactions",
                "GET  /system/status",
                "POST /system/shutdown",
            ],
            "docs": "/docs",
        },
    )


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return structured 405 Method Not Allowed."""
    return JSONResponse(
        status_code=405,
        content={
            "error":   "Method Not Allowed",
            "message": f"HTTP {request.method} is not allowed for {request.url.path}.",
        },
    )


@app.exception_handler(422)
async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return structured 422 Validation Error."""
    return JSONResponse(
        status_code=422,
        content={
            "error":   "Validation Error",
            "message": "Request body validation failed.",
            "detail":  str(exc),
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return structured 500 Internal Server Error and log the traceback."""
    logger.exception("Unhandled internal server error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error":   "Internal Server Error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )


# ─────────────────────────────────────────────────────────────
# Direct execution entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
        access_log=True,
    )
