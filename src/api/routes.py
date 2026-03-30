"""
HYDRA Arm 3 — API Routes

Endpoints:
  GET  /health                    — free
  GET  /pricing                   — free
  POST /v1/regulatory/scan        — $1.00 USDC (x402)
  POST /v1/regulatory/changes     — $0.50 USDC (x402)
  POST /v1/regulatory/jurisdiction — $2.00 USDC (x402)
  POST /v1/regulatory/query       — $0.50 USDC (x402)

The x402 payment flow is handled entirely by X402PaymentMiddleware.
These route handlers assume payment has already been verified.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import config.settings as settings
from src.models.schemas import (
    Agency,
    EndpointPricing,
    HealthResponse,
    JurisdictionRequest,
    PricingResponse,
    RegulatoryChangesRequest,
    RegulatoryChangesResponse,
    RegulatoryQueryRequest,
    RegulatoryQueryResponse,
    RegulatoryScenRequest,
    RegulatoryScenResponse,
)
from src.services import feeds as feed_service
from src.services import regulatory as reg_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────
# Free Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("/", tags=["System"])
async def root():
    """Root endpoint — landing page."""
    return {
        "name": "HYDRA Arm 3 — Regulatory Intelligence SaaS",
        "status": "operational",
        "docs": "/docs",
        "pricing": "/pricing",
        "payment_protocol": "x402",
        "payment_token": "USDC on Base (Chain 8453)",
        "wallet": "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141"
    }

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """
    Returns application health status. No payment required.
    """
    # Include automaton status snapshot (non-critical — never fails the health check)
    automaton_status: dict = {}
    try:
        from src.runtime.automaton import get_automaton
        automaton_status = get_automaton().get_status()
    except Exception as exc:
        logger.debug("Could not fetch automaton status for /health: %s", exc)

    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        app_name=settings.APP_NAME,
        payment_network=settings.PAYMENT_NETWORK,
        payment_token=settings.PAYMENT_TOKEN,
        wallet_address=settings.WALLET_ADDRESS,
        automaton=automaton_status if automaton_status else None,
    )


@router.get("/pricing", response_model=PricingResponse, tags=["System"])
async def get_pricing() -> PricingResponse:
    """
    Returns pricing for all paid endpoints. No payment required.
    """
    endpoints = [
        EndpointPricing(
            endpoint=path,
            amount_usdc=str(info["amount_usdc"]),
            amount_base_units=info["amount_base_units"],
            description=info["description"],
        )
        for path, info in settings.PRICING.items()
    ]

    return PricingResponse(
        endpoints=endpoints,
        payment_network=settings.PAYMENT_NETWORK,
        payment_token=settings.PAYMENT_TOKEN,
        wallet_address=settings.WALLET_ADDRESS,
        chain_id=settings.CHAIN_ID,
        instructions=(
            f"All paid endpoints require USDC payment on Base (chain ID {settings.CHAIN_ID}). "
            f"Send the exact USDC amount to {settings.WALLET_ADDRESS}, then retry your request "
            f"with the transaction hash in the X-Payment-Proof header."
        ),
    )


# ─────────────────────────────────────────────────────────────
# Paid Endpoints — x402 middleware verifies payment before
# these handlers are invoked.
# ─────────────────────────────────────────────────────────────

@router.post(
    "/v1/regulatory/scan",
    response_model=RegulatoryScenResponse,
    tags=["Regulatory Intelligence"],
    summary="Regulatory Risk Scan ($1.00 USDC)",
    description=(
        "Analyzes a business description against all applicable regulatory frameworks. "
        "Returns risk score, applicable regulations, compliance gaps, and priority actions. "
        "**Requires x402 payment of $1.00 USDC on Base.**"
    ),
)
async def regulatory_scan(
    request_body: RegulatoryScenRequest,
    request: Request,
) -> RegulatoryScenResponse:
    """
    Perform a comprehensive regulatory risk scan.

    Payment: $1.00 USDC via X-Payment-Proof header.
    """
    logger.info(
        "Regulatory scan: jurisdiction=%s description_length=%d",
        request_body.jurisdiction,
        len(request_body.business_description),
    )

    try:
        result = reg_service.analyze_regulatory_risk(
            business_description=request_body.business_description,
            jurisdiction=request_body.jurisdiction,
        )
    except Exception as exc:
        logger.exception("Error in regulatory scan: %s", exc)
        raise HTTPException(status_code=500, detail=f"Regulatory analysis failed: {exc}") from exc

    return result


@router.post(
    "/v1/regulatory/changes",
    response_model=RegulatoryChangesResponse,
    tags=["Regulatory Intelligence"],
    summary="Recent Regulatory Changes ($0.50 USDC)",
    description=(
        "Fetches recent regulatory changes, proposed rules, and enforcement actions from "
        "official RSS feeds of SEC, CFTC, FinCEN, OCC, and CFPB. Results are cached for 1 hour. "
        "**Requires x402 payment of $0.50 USDC on Base.**"
    ),
)
async def regulatory_changes(
    request_body: RegulatoryChangesRequest,
    request: Request,
) -> RegulatoryChangesResponse:
    """
    Fetch recent regulatory changes from official agency feeds.

    Payment: $0.50 USDC via X-Payment-Proof header.
    """
    agency_name = request_body.agency.value
    days = request_body.days

    logger.info("Regulatory changes: agency=%s days=%d", agency_name, days)

    try:
        if agency_name == Agency.ALL.value:
            all_items_by_agency = feed_service.get_all_agencies_items(days=days)
            all_items = []
            for agency_items in all_items_by_agency.values():
                all_items.extend(agency_items)
            # Sort combined list by published date descending
            all_items.sort(
                key=lambda x: x.published or "0000-00-00",
                reverse=True,
            )
            sources: list[str] = []
            for ag in feed_service.FEED_REGISTRY:
                sources.extend(feed_service.get_data_sources(ag))
        else:
            all_items = feed_service.get_agency_items(agency_name=agency_name, days=days)
            sources = feed_service.get_data_sources(agency_name)

    except Exception as exc:
        logger.exception("Error fetching regulatory feeds: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch regulatory feeds: {exc}",
        ) from exc

    return RegulatoryChangesResponse(
        agency=agency_name,
        days_requested=days,
        total_items=len(all_items),
        items=all_items,
        data_sources=sources,
    )


@router.post(
    "/v1/regulatory/jurisdiction",
    response_model=None,  # We'll return raw dict to avoid serialization issues
    tags=["Regulatory Intelligence"],
    summary="Jurisdiction Comparison ($2.00 USDC)",
    description=(
        "Compares regulatory requirements across US states and international jurisdictions "
        "for a specific business type (crypto, fintech, securities, banking). "
        "Includes friendliness scores, key advantages/risks, and incorporation details. "
        "**Requires x402 payment of $2.00 USDC on Base.**"
    ),
)
async def jurisdiction_comparison(
    request_body: JurisdictionRequest,
    request: Request,
) -> JSONResponse:
    """
    Compare regulatory requirements across jurisdictions.

    Supported jurisdictions: WY, DE, NV, NY, TX, EU, UK, SG
    Payment: $2.00 USDC via X-Payment-Proof header.
    """
    logger.info(
        "Jurisdiction comparison: jurisdictions=%s business_type=%s",
        request_body.jurisdictions,
        request_body.business_type.value,
    )

    try:
        result = reg_service.compare_jurisdictions(
            jurisdictions=request_body.jurisdictions,
            business_type=request_body.business_type,
        )
    except Exception as exc:
        logger.exception("Error in jurisdiction comparison: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Jurisdiction comparison failed: {exc}",
        ) from exc

    return JSONResponse(content=result.model_dump())


@router.post(
    "/v1/regulatory/query",
    response_model=RegulatoryQueryResponse,
    tags=["Regulatory Intelligence"],
    summary="Regulatory Q&A ($0.50 USDC)",
    description=(
        "Answers natural-language questions about regulatory requirements using a structured "
        "knowledge base covering SEC, CFTC, FinCEN, state regulators, and international frameworks. "
        "**Requires x402 payment of $0.50 USDC on Base.**"
    ),
)
async def regulatory_query(
    request_body: RegulatoryQueryRequest,
    request: Request,
) -> RegulatoryQueryResponse:
    """
    Answer a regulatory question.

    Topics covered: securities law, derivatives, AML/BSA, money transmission, cryptocurrency,
    jurisdiction comparison, investment funds, data privacy.
    Payment: $0.50 USDC via X-Payment-Proof header.
    """
    logger.info(
        "Regulatory query: question_length=%d",
        len(request_body.question),
    )

    try:
        result = reg_service.answer_regulatory_query(question=request_body.question)
    except Exception as exc:
        logger.exception("Error in regulatory query: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {exc}",
        ) from exc

    return result
