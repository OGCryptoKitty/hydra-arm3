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
  - Auto-remittance: prompts owner at $1,000 USDC threshold
  - System endpoints: /system/* (localhost or bearer token protected)
  - Rate limiting: 60/min free, 30/min paid, 10/min system per IP
  - Request ID tracking: X-Request-ID header on all responses
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
from src.middleware.https_redirect import HTTPSRedirectMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.request_id import RequestIDMiddleware
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
    import json, os
    pk = os.getenv("WALLET_PRIVATE_KEY", "")
    if not pk:
        # Try loading from wallet.json in state directory
        from src.runtime.remittance import BOOTSTRAP_DIR
        wallet_json = BOOTSTRAP_DIR / "wallet.json"
        if wallet_json.exists():
            try:
                with open(wallet_json) as f:
                    pk = json.load(f).get("private_key", "")
            except Exception:
                pass
        if not pk:
            logger.warning(
                "WALLET_PRIVATE_KEY not set. Automaton runs in READ-ONLY mode. "
                "Remittance transfers will not be possible until a private key is configured."
            )

    try:
        automaton = HydraAutomaton(
            wallet_address=settings.WALLET_ADDRESS,
            private_key=pk,
            base_rpc_url=settings.BASE_RPC_URL,
        )
        set_automaton(automaton)
        heartbeat_task = asyncio.create_task(
            automaton.run(), name="hydra-automaton-heartbeat"
        )
        automaton._task = heartbeat_task
        app.state.automaton = automaton
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
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
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

# 3. Rate Limiting — per-IP request throttling
app.add_middleware(RateLimitMiddleware)

# 4. Request ID — traceability for every request
app.add_middleware(RequestIDMiddleware)

# 5. HTTPS Redirect — enforce HTTPS in production (set ENFORCE_HTTPS=true)
app.add_middleware(HTTPSRedirectMiddleware)


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
        automaton = getattr(request.app.state, "automaton", None) or get_automaton()
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


# ─────────────────────────────────────────────────────────────
# Metrics endpoint — operational monitoring
# ─────────────────────────────────────────────────────────────

@app.get("/metrics", tags=["System"], include_in_schema=True)
async def metrics(request: Request) -> JSONResponse:
    """
    Operational metrics for monitoring dashboards.
    Returns uptime, transaction counts, balance, and endpoint pricing summary.
    No payment required.
    """
    import time as _time
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
        "llm_enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
        "version": settings.APP_VERSION,
    })


@app.get("/metrics/prometheus", tags=["System"], include_in_schema=True)
async def prometheus_metrics(request: Request) -> Response:
    """
    Prometheus-compatible metrics endpoint.
    Scrape this with Prometheus, Grafana Agent, or DataDog.
    """
    from starlette.responses import PlainTextResponse
    from src.middleware.monitoring import get_metrics_collector
    collector = get_metrics_collector()
    return PlainTextResponse(
        content=collector.to_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ─────────────────────────────────────────────────────────────
# Global Exception Handlers
# ─────────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return structured 404 with available endpoint list."""
    endpoint_list = [
        "GET  /health",
        "GET  /pricing",
        "GET  /metrics",
    ]
    for path, info in settings.PRICING.items():
        endpoint_list.append(f"POST {path:<35s} (${info['amount_usdc']} USDC)")
    endpoint_list.extend([
        "--- System (localhost/bearer token) ---",
        "POST /system/wallet",
        "GET  /system/remittance/status",
        "POST /system/remittance/execute",
        "GET  /system/transactions",
        "GET  /system/status",
        "POST /system/shutdown",
    ])
    return JSONResponse(
        status_code=404,
        content={
            "error":   "Not Found",
            "message": f"Endpoint {request.url.path} does not exist.",
            "available_endpoints": endpoint_list,
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
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    logger.exception("Unhandled internal server error [%s]: %s", request_id, exc)
    content: dict = {
        "error":   "Internal Server Error",
        "message": "An unexpected error occurred. Please try again.",
    }
    if request_id:
        content["request_id"] = request_id
    return JSONResponse(status_code=500, content=content)


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
