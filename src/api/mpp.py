"""
MPP (Machine Payments Protocol) discovery and status endpoints.

Exposes MPP payment capabilities for agents using Stripe/Tempo
session-based micropayments alongside x402.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

mpp_router = APIRouter(tags=["System"])


@mpp_router.get("/v1/mpp/manifest", tags=["System"])
async def mpp_manifest():
    """MPP payment capabilities manifest for agent discovery."""
    try:
        from mpp import payment_capabilities
        caps = payment_capabilities()
        return JSONResponse(content={
            "protocol": "mpp",
            "version": caps.get("version", "0.6.0"),
            "capabilities": caps,
            "service": {
                "name": "HYDRA Regulatory Intelligence",
                "url": "https://hydra-api-nlnj.onrender.com",
            },
            "x402_fallback": "https://hydra-api-nlnj.onrender.com/.well-known/x402.json",
        })
    except ImportError:
        return JSONResponse(content={
            "protocol": "mpp",
            "status": "unavailable",
            "message": "pympp not installed — use x402 payment flow",
            "x402_manifest": "https://hydra-api-nlnj.onrender.com/.well-known/x402.json",
        })


@mpp_router.get("/v1/mpp/status", tags=["System"])
async def mpp_status():
    """MPP middleware status check."""
    try:
        from src.x402.mpp_integration import get_mpp_status
        status = get_mpp_status()
        return JSONResponse(content={
            "mpp_enabled": status.get("enabled", False),
            "mpp_status": status,
            "payment_protocols": ["x402", "mpp", "x-payment-proof"],
        })
    except Exception:
        return JSONResponse(content={
            "mpp_enabled": False,
            "payment_protocols": ["x402", "x-payment-proof"],
        })
