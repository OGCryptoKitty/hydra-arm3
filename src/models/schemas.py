"""
HYDRA Arm 3 — Pydantic request/response schemas for all API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────

class Agency(str, Enum):
    SEC = "SEC"
    CFTC = "CFTC"
    FinCEN = "FinCEN"
    OCC = "OCC"
    CFPB = "CFPB"
    ALL = "all"


class BusinessType(str, Enum):
    CRYPTO = "crypto"
    FINTECH = "fintech"
    SECURITIES = "securities"
    BANKING = "banking"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─────────────────────────────────────────────────────────────
# Common Response Envelope
# ─────────────────────────────────────────────────────────────

class PaymentInfo(BaseModel):
    """Embedded in 402 responses to tell clients how to pay."""
    amount_usdc: str = Field(..., description="Amount in human-readable USDC (e.g. '1.00')")
    amount_base_units: int = Field(..., description="Amount in USDC base units (6 decimals)")
    wallet_address: str = Field(..., description="Recipient wallet address on Base")
    network: str = Field(default="base", description="Payment network")
    token: str = Field(default="USDC", description="Payment token")
    chain_id: int = Field(default=8453, description="EVM chain ID for Base mainnet")
    instructions: str = Field(
        default=(
            "Send the exact USDC amount to the wallet address on Base (chain 8453). "
            "Then retry your request with the transaction hash in the X-Payment-Proof header."
        )
    )


class APIResponse(BaseModel):
    """Standard success envelope."""
    success: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Any = None


class ErrorResponse(BaseModel):
    """Standard error envelope."""
    success: bool = False
    error: str
    detail: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    app_name: str
    payment_network: str
    payment_token: str
    wallet_address: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    automaton: Any = Field(
        default=None,
        description="Current HydraAutomaton state snapshot (survival tier, balance, phase)",
    )


# ─────────────────────────────────────────────────────────────
# /pricing
# ─────────────────────────────────────────────────────────────

class EndpointPricing(BaseModel):
    endpoint: str
    amount_usdc: str
    amount_base_units: int
    description: str


class PricingResponse(BaseModel):
    endpoints: list[EndpointPricing]
    payment_network: str
    payment_token: str
    wallet_address: str
    chain_id: int
    instructions: str
    x402: dict | None = None


# ─────────────────────────────────────────────────────────────
# POST /v1/regulatory/scan
# ─────────────────────────────────────────────────────────────

class RegulatoryScenRequest(BaseModel):
    business_description: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Plain-English description of the business, its activities, and target markets",
        examples=["A platform allowing US retail investors to trade tokenized equities via a mobile app"],
    )
    jurisdiction: str = Field(
        default="US",
        description="Primary jurisdiction of operation (e.g. 'US', 'US-WY', 'US-DE', 'EU', 'UK')",
        examples=["US", "US-WY", "EU"],
    )


class ApplicableRegulation(BaseModel):
    name: str
    citation: str
    regulator: str
    relevance: str
    risk_level: RiskLevel
    description: str
    recommended_actions: list[str]


class RegulatoryScenResponse(BaseModel):
    business_description: str
    jurisdiction: str
    overall_risk_score: int = Field(..., ge=0, le=100, description="0=minimal risk, 100=severe risk")
    overall_risk_level: RiskLevel
    applicable_regulations: list[ApplicableRegulation]
    key_compliance_gaps: list[str]
    priority_actions: list[str]
    disclaimer: str = Field(
        default=(
            "This analysis is provided for informational purposes only and does not constitute "
            "legal advice. Consult qualified legal counsel before making compliance decisions."
        )
    )


# ─────────────────────────────────────────────────────────────
# POST /v1/regulatory/changes
# ─────────────────────────────────────────────────────────────

class RegulatoryChangesRequest(BaseModel):
    agency: Agency = Field(default=Agency.ALL, description="Regulatory agency to query")
    days: int = Field(
        default=30,
        ge=1,
        le=180,
        description="Number of days back to fetch regulatory changes",
    )


class RegulatoryItem(BaseModel):
    title: str
    agency: str
    published: str | None = None
    summary: str
    url: str | None = None
    item_type: str = Field(description="press_release, proposed_rule, final_rule, enforcement, notice")


class RegulatoryChangesResponse(BaseModel):
    agency: str
    days_requested: int
    total_items: int
    items: list[RegulatoryItem]
    data_sources: list[str]
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────
# POST /v1/regulatory/jurisdiction
# ─────────────────────────────────────────────────────────────

class JurisdictionRequest(BaseModel):
    jurisdictions: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of jurisdiction codes to compare (e.g. ['WY', 'DE', 'NV', 'EU'])",
        examples=[["WY", "DE", "NV"]],
    )
    business_type: BusinessType = Field(
        ...,
        description="Type of business for jurisdiction comparison",
    )

    @field_validator("jurisdictions")
    @classmethod
    def normalize_jurisdictions(cls, v: list[str]) -> list[str]:
        return [j.strip().upper() for j in v]


class JurisdictionRequirement(BaseModel):
    category: str
    requirement: str
    notes: str | None = None


class JurisdictionProfile(BaseModel):
    jurisdiction: str
    full_name: str
    overall_friendliness: str = Field(description="very_friendly|friendly|neutral|restrictive|very_restrictive")
    friendliness_score: int = Field(..., ge=0, le=100, description="100=most business-friendly")
    requirements: list[JurisdictionRequirement]
    key_advantages: list[str]
    key_risks: list[str]
    notable_regulations: list[str]
    incorporation_cost_usd: str | None = None
    time_to_incorporate_days: str | None = None


class JurisdictionComparisonResponse(BaseModel):
    business_type: str
    jurisdictions_compared: list[str]
    profiles: list[JurisdictionProfile]
    recommendation: str
    comparison_matrix: dict[str, dict[str, str]]
    disclaimer: str = Field(
        default=(
            "Jurisdiction data is for informational purposes only. "
            "Laws change frequently — verify current requirements with local counsel."
        )
    )


# ─────────────────────────────────────────────────────────────
# POST /v1/regulatory/query
# ─────────────────────────────────────────────────────────────

class RegulatoryQueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Natural-language question about regulatory requirements",
        examples=["Do I need a money transmitter license to operate a crypto exchange in Wyoming?"],
    )


class RegulatoryQueryResponse(BaseModel):
    question: str
    answer: str
    confidence: str = Field(description="high|medium|low — based on knowledge base coverage")
    relevant_regulations: list[str]
    relevant_agencies: list[str]
    follow_up_questions: list[str]
    disclaimer: str = Field(
        default=(
            "This answer is generated from a structured regulatory knowledge base and does not "
            "constitute legal advice. Consult qualified legal counsel for your specific situation."
        )
    )


# ─────────────────────────────────────────────────────────────
# x402 Payment Verification
# ─────────────────────────────────────────────────────────────

class PaymentVerificationResult(BaseModel):
    verified: bool
    tx_hash: str
    amount_received_base_units: int | None = None
    amount_required_base_units: int | None = None
    from_address: str | None = None
    to_address: str | None = None
    error: str | None = None
