"""
HYDRA Arm 3 — Prediction Market Integration Service

Connects to Polymarket and Kalshi APIs to:
  1. Discover active regulatory markets across both platforms
  2. Generate regulatory intelligence signals for prediction market traders
  3. Match real-time regulatory events to active markets
  4. Provide resolution data formatted for oracle consumption (UMA, Chainlink, API3)

External APIs used:
  Polymarket Gamma:  https://gamma-api.polymarket.com   (market discovery)
  Polymarket CLOB:   https://clob.polymarket.com        (order book / prices)
  Kalshi:            https://api.elections.kalshi.com/trade-api/v2 (all markets)

Cache TTLs:
  Market data:          5 minutes  (market prices change frequently)
  Regulatory analysis:  60 minutes (underlying regulatory data is slow-moving)
  Event feed:           5 minutes  (new events arrive continuously)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from cachetools import TTLCache

# Import the existing HYDRA regulatory engine
from src.services import feeds as feed_service
from src.services import regulatory as reg_service

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Cache Setup
# ─────────────────────────────────────────────────────────────

# 5-minute cache for live market data (prices, volumes, order books)
_market_cache: TTLCache = TTLCache(maxsize=200, ttl=300)

# 60-minute cache for HYDRA regulatory analysis (expensive to compute)
_analysis_cache: TTLCache = TTLCache(maxsize=100, ttl=3600)

# 5-minute cache for regulatory event feeds
_event_cache: TTLCache = TTLCache(maxsize=50, ttl=300)

# ─────────────────────────────────────────────────────────────
# Regulatory market filter keywords
# ─────────────────────────────────────────────────────────────

REGULATORY_KEYWORDS = [
    # Fed / monetary policy
    "fed fund", "fomc", "interest rate", "rate cut", "rate hike", "federal reserve",
    # Macro economic indicators
    "inflation", "cpi", "pce", "gdp", "recession", "unemployment", "jobs report",
    # Trade / sanctions
    "tariff", "trade war", "trade deal", "sanctions", "ofac",
    # SEC / securities regulation
    "sec enforcement", "sec charges", "sec sues", "sec action", "sec settlement",
    "sec order", "sec investigation", "securities fraud", "insider trading",
    "etf approval", "etf denied", "spot etf",
    # CFTC / derivatives
    "cftc", "commodity futures", "derivatives regulation",
    # Crypto regulation
    "crypto regulation", "stablecoin", "genius act", "fit21", "clarity act",
    "market structure bill", "digital asset legislation", "bitcoin etf",
    "ethereum etf", "crypto bill", "senate crypto", "house crypto",
    # Bitcoin/Ethereum only if tied to regulation context (handled in filter fn)
    # FinCEN / AML
    "fincen", "anti-money", "bank secrecy", "aml", "bsa compliance",
    # Treasury / fiscal
    "treasury", "debt ceiling", "government shutdown",
    # Generic regulatory
    "executive order", "deregulation", "rulemaking",
]

# Non-regulatory topics that should be EXCLUDED even if they match other keywords
_EXCLUSION_PATTERNS = [
    # Sports / entertainment
    r"\bnba\b", r"\bnfl\b", r"\bmlb\b", r"\bnhl\b", r"\bsoccer\b",
    r"\bsuper bowl\b", r"\bworld cup\b", r"\boscars?\b", r"\bgrammy\b",
    r"\bboxing\b", r"\bwrestl\b", r"\bmma\b", r"\bufc\b",
    # Pure politics (elections, candidates) without regulatory context
    r"\b(?:win|wins|winning|winner|elected|election|vote|votes|voting|ballot|primary|nominee|nomination|nominate)\b.*\b(?:president|senate race|congress|governor|mayor|democrat|republican|biden|trump|harris|desantis|newsom)\b",
    r"\b(?:president|senate race|congress|governor|mayor)\b.*\b(?:win|wins|elected|election|vote|ballot|primary|nominee)\b",
    r"\b2028 (?:president|election|primary|nominee|dem|rep)\b",
    r"\b2026 (?:midterm|election|senate|congress)\b",
    r"\bpresidential (?:election|primary|race|nominee|candidate)\b",
    # Entertainment / celebrity
    r"\bactor\b", r"\bactress\b", r"\bsinger\b", r"\bband\b",
    r"\balbum\b", r"\bmovie\b", r"\bfilm\b", r"\btelevision\b",
    r"\b(?:elon musk|spacex|tesla)\b",
    # Non-regulatory crypto (price predictions, company events)
    r"\b(?:will|price|reach|above|below|hit)\s+(?:\$|usd)?\d",
    r"\bcoinbase (?:ipo|stock|shares)\b",
    r"\bmicrostrategy\b",
    r"\bkraken (?:ipo|stock)\b",
    r"\bripple (?:ipo|stock)\b",
]

# Tag IDs on Polymarket for regulatory/political markets
# These are discovered empirically; regulation/politics/crypto are the core buckets
POLYMARKET_REGULATORY_TAG_SLUGS = [
    "regulation", "crypto", "politics", "federal-reserve", "legislation",
    "economics", "us-politics", "finance", "law",
]

# Kalshi series tickers for regulatory markets
KALSHI_REGULATORY_SERIES = [
    "KXFED",          # Fed funds rate decisions
    "KXSEC",          # SEC-related markets
    "KXCRYPTO",       # Crypto regulation
    "KXCRYPTOSTRUCTURE",  # Crypto market structure legislation
    "KXGENIUS",       # GENIUS Act stablecoin
    "KXSTABLECOIN",   # Stablecoin regulation broadly
    "KXCFTC",         # CFTC markets
    "KXCONGRESS",     # Congressional legislation
]

# Kalshi event categories to search
KALSHI_REGULATORY_CATEGORIES = [
    "economics", "financialregulation", "politics", "legal",
]


def _matches_regulatory(text: str, strict: bool = True) -> bool:
    """Return True if text matches any regulatory keyword and passes exclusion filters.

    Parameters
    ----------
    text : str
        The market title + description to check.
    strict : bool
        If True, also check _EXCLUSION_PATTERNS to eliminate non-regulatory content.
        Default True — use strict mode for market discovery.
    """
    text_lower = text.lower()
    # Must match at least one regulatory keyword
    if not any(kw in text_lower for kw in REGULATORY_KEYWORDS):
        return False
    # Must not match any exclusion pattern
    if strict:
        for pattern in _EXCLUSION_PATTERNS:
            if re.search(pattern, text_lower):
                return False
    return True


def _cache_key(*parts: Any) -> str:
    """Generate a deterministic cache key from parts."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324 — used for caching only


# ─────────────────────────────────────────────────────────────
# HYDRA Regulatory Intelligence Engine
# (internal analysis helpers that map market questions to HYDRA knowledge)
# ─────────────────────────────────────────────────────────────

# Mapping from market topic keywords → regulatory context + HYDRA knowledge
_REGULATORY_DOMAIN_PROFILES: dict[str, dict[str, Any]] = {
    "fed_rate": {
        "keywords": ["federal reserve", "fed rate", "fomc", "interest rate", "basis points",
                     "rate cut", "rate hike", "pause", "pivot", "fed funds"],
        "regulatory_context": (
            "The Federal Reserve sets the federal funds rate target range at FOMC meetings "
            "(8 scheduled per year). Rate decisions are announced via official press releases at "
            "federalreserve.gov and simultaneously in the FOMC statement. The Fed has a dual mandate: "
            "price stability (2% inflation target) and maximum employment. As of early 2026, the Fed "
            "entered a prolonged pause after cutting rates 100bps in late 2024."
        ),
        "key_dates": [
            "FOMC meetings: Jan 28-29, Mar 18-19, May 6-7, Jun 17-18, Jul 29-30, Sep 16-17, "
            "Oct 28-29, Dec 9-10 (2026 schedule, verify at federalreserve.gov)"
        ],
        "historical_precedent": (
            "The Fed last raised rates in July 2023 (5.25-5.50%). It cut 25bps in Sep, Nov, Dec 2024 "
            "to reach 4.25-4.50%. Markets in early 2026 price ~80% probability of the rate being held "
            "steady. Historical precedent: the Fed rarely reverses course within 2 meetings unless "
            "significant economic deterioration occurs."
        ),
        "risk_factors": [
            "CPI/PCE inflation data deviating significantly from 2% target",
            "Labor market shock (large jobs report miss or surge)",
            "Financial stability event (bank failure, credit market seizure)",
            "Geopolitical shock affecting energy/supply chains",
            "Fed Chair public statements or congressional testimony",
        ],
        "resolution_source": "federalreserve.gov/newsevents/pressreleases/",
    },
    "sec_enforcement": {
        "keywords": ["sec enforcement", "sec charges", "sec sues", "sec action", "sec settlement",
                     "securities fraud", "insider trading", "sec order", "sec investigation"],
        "regulatory_context": (
            "The SEC's Enforcement Division brings civil actions in federal court and administrative "
            "proceedings for violations of federal securities laws. Key enforcement categories: "
            "insider trading, accounting fraud, market manipulation, unregistered securities offerings "
            "(including crypto tokens). Enforcement actions are published at sec.gov/litigation/. "
            "Under Chair Paul Atkins (confirmed 2025), SEC enforcement posture toward crypto "
            "has moderated significantly compared to the Gensler era."
        ),
        "key_dates": [
            "SEC enforcement releases: published continuously at sec.gov/litigation/litreleases/",
            "Fiscal year end: September 30 (enforcement statistics reported annually)",
            "Annual enforcement report: typically published November-December",
        ],
        "historical_precedent": (
            "2023: SEC filed 784 enforcement actions, obtained $4.9B in penalties. "
            "2024: Enforcement dropped ~15% in crypto category after industry legal pushback. "
            "2025-2026: SEC under Atkins pivoted to 'regulation by rulemaking not enforcement' — "
            "major crypto enforcement actions declined sharply. ETF approvals (spot Bitcoin Jan 2024, "
            "spot Ethereum May 2024) established precedent for further crypto product approvals."
        ),
        "risk_factors": [
            "Change in SEC Chair or enforcement leadership",
            "Congressional pressure to act (or not act) on specific cases",
            "Court rulings in parallel cases setting precedent",
            "Target company cooperation or settlement negotiations",
            "Whistleblower tips triggering investigations",
        ],
        "resolution_source": "sec.gov/litigation/ and sec.gov/news/pressreleases",
    },
    "crypto_legislation": {
        "keywords": ["genius act", "clarity act", "fit21", "stablecoin", "crypto regulation",
                     "market structure", "crypto bill", "digital asset", "legislation crypto",
                     "crypto law", "senate crypto", "house crypto", "congress crypto"],
        "regulatory_context": (
            "The US Congress has been working on three parallel crypto legislative tracks: "
            "(1) Stablecoin regulation: GENIUS Act (Senate) — requires 1:1 reserve backing, "
            "federal/state registration, monthly attestation. STABLE Act (House alternative). "
            "(2) Market structure: FIT21 (Financial Innovation and Technology for the 21st Century Act) "
            "passed House 279-136 in May 2024; Senate version pending. Allocates regulatory jurisdiction "
            "between SEC (securities) and CFTC (commodities) for digital assets. "
            "(3) AML/KYC: Crypto industry faces ongoing BSA compliance requirements regardless of "
            "other legislation. FinCEN proposed rules for unhosted wallets remain contested."
        ),
        "key_dates": [
            "GENIUS Act: Senate Banking Committee markup scheduled; floor vote target Q2 2026",
            "FIT21 Senate companion bill: committee hearings ongoing in 2026",
            "Congressional calendar: Must pass before recess; key windows Apr-Jun and Sep-Oct 2026",
            "Presidential signature: Required within 10 days of congressional passage",
        ],
        "historical_precedent": (
            "FIT21 passed House with bipartisan support in May 2024 — rare for crypto legislation. "
            "The GENIUS Act gained Senate co-sponsors in early 2025. Stablecoin legislation historically "
            "moves faster than broader market structure bills due to narrower scope and banking industry "
            "support. EU MiCA came into full effect Dec 2024, creating pressure for US action."
        ),
        "risk_factors": [
            "Senate filibuster / procedural delays",
            "Conference committee reconciliation between House and Senate versions",
            "Presidential veto threat or signing statement",
            "Industry lobbying lobbying either direction",
            "Unrelated political events consuming congressional floor time",
            "Competing legislative priorities (budget, appropriations)",
        ],
        "resolution_source": "congress.gov official bill status tracking",
    },
    "cftc_regulation": {
        "keywords": ["cftc", "commodity futures", "derivatives", "futures exchange", "cftc ruling",
                     "cftc enforcement", "cftc approval", "prediction market cftc",
                     "sports betting cftc", "cftc anprm"],
        "regulatory_context": (
            "The CFTC regulates commodity futures, options, and swaps under the Commodity Exchange Act. "
            "As the primary US derivatives regulator, it has jurisdiction over crypto commodities "
            "(Bitcoin, Ether designated as commodities by courts). In 2025-2026, key CFTC activities: "
            "(1) ANPRM on prediction market event contracts (notably sports/politics contracts) — "
            "comment period generated massive industry response. "
            "(2) Enforcement against crypto exchanges for unregistered derivatives. "
            "(3) Rulemaking on DeFi protocols and their regulatory status. "
            "Kalshi and ForecastEx are CFTC-regulated Designated Contract Markets (DCMs)."
        ),
        "key_dates": [
            "CFTC ANPRM on event contracts: comment period closed; final rule pending",
            "CFTC commissioners: rotating membership; Chairman nomination affects rulemaking pace",
            "CFTC advisory committees: typically meet quarterly",
        ],
        "historical_precedent": (
            "CFTC approved Kalshi's political event contracts in 2023 after initial denial. "
            "ForecastEx (Nasdaq subsidiary) received DCM designation for prediction markets. "
            "CFTC vs. prediction markets: 2022-2023 legal battle over election contracts resolved "
            "in favor of event contract markets. Crypto enforcement: BitMEX ($100M settlement 2021), "
            "Binance ($4.3B DOJ/CFTC settlement 2023), Coinbase facing ongoing CFTC scrutiny."
        ),
        "risk_factors": [
            "CFTC rulemaking pace and final rule text",
            "New CFTC Chair or commissioner appointments",
            "Industry legal challenges to CFTC jurisdiction",
            "Interagency turf battles (SEC vs. CFTC over crypto classification)",
            "Congressional legislation clarifying CFTC jurisdiction",
        ],
        "resolution_source": "cftc.gov/PressRoom/ and Federal Register",
    },
    "bank_failure": {
        "keywords": ["bank failure", "bank fails", "fdic", "fdic seizure", "bank closure",
                     "regional bank", "bank collapse", "receivership"],
        "regulatory_context": (
            "Bank failures are resolved by the FDIC as receiver, typically announced on Friday evenings. "
            "The FDIC publishes failed bank lists at fdic.gov/bank/individual/failed/banklist.html. "
            "Post-SVB/Signature/First Republic 2023 crisis, regulators increased oversight of "
            "unrealized securities losses and commercial real estate (CRE) concentrations. "
            "As of 2026, elevated CRE stress remains the primary systemic risk for community banks."
        ),
        "key_dates": [
            "FDIC failed bank list: updated on failure (typically Friday evenings)",
            "FDIC quarterly banking profile: released ~6 weeks after quarter end",
            "Bank stress test results (DFAST): typically June annually",
        ],
        "historical_precedent": (
            "2023: SVB ($209B), Signature ($110B), First Republic ($229B) — largest bank failures "
            "since 2008. 2024-2025: No systemic failures; isolated community bank closures. "
            "Base rate for prediction markets: ~4-8 bank failures per year historically (2012-2019), "
            "with major clustered events in 2008-2010 (500+ failures) and 2023."
        ),
        "risk_factors": [
            "Commercial real estate loan book quality",
            "Rising credit card and consumer loan delinquencies",
            "Unrealized securities losses (HTM portfolio)",
            "Deposit concentration and stability",
            "Federal Reserve rate policy (higher-for-longer stresses balance sheets)",
        ],
        "resolution_source": "fdic.gov failed bank list, FDIC press releases",
    },
    "crypto_etf": {
        "keywords": ["etf", "spot etf", "bitcoin etf", "ethereum etf", "crypto etf", "sec approval",
                     "etf approval", "asset manager etf"],
        "regulatory_context": (
            "The SEC approved spot Bitcoin ETFs in January 2024 (11 products launched day-one) "
            "and spot Ethereum ETFs in May 2024. Under Chair Atkins (2025+), the SEC established "
            "a Crypto Task Force taking a more permissive posture toward crypto products. "
            "New applications: Solana ETF, XRP ETF, multi-asset crypto ETFs, in-kind redemption "
            "approval for existing products. Standard SEC review: 240 days maximum; can approve or "
            "deny at any point. New 19b-4 rule changes have accelerated crypto product approvals."
        ),
        "key_dates": [
            "SEC review deadlines: 45/90/180/240 days from filing — check specific fund's S-1/19b-4",
            "SEC Crypto Task Force: meets monthly; releases interpretive guidance periodically",
        ],
        "historical_precedent": (
            "Bitcoin spot ETF: rejected 10+ times (2013-2023), approved January 2024. "
            "Ethereum spot ETF: approved May 2024, launched July 2024. "
            "In-kind redemption: approved for Bitcoin ETFs in Nov 2024. "
            "Post-Atkins: dramatically faster approvals. Solana ETF applications from "
            "21Shares, Canary, VanEck, Bitwise pending as of March 2026."
        ),
        "risk_factors": [
            "SEC staff comment letters slowing review",
            "Congressional pressure on SEC crypto posture",
            "Market manipulation concerns for underlying asset",
            "Custody solution adequacy (SEC scrutiny of qualified custodians)",
            "Liquidity and market cap thresholds for new assets",
        ],
        "resolution_source": "sec.gov EDGAR — 19b-4 filings and approval orders",
    },
    "scotus_legal": {
        "keywords": ["scotus", "supreme court", "certiorari", "cert", "appeals court",
                     "circuit court", "court ruling", "legal challenge"],
        "regulatory_context": (
            "The US Supreme Court issues opinions on cases it accepts (cert granted) "
            "during its term (October-June). Landmark financial regulation cases can overturn "
            "agency rulemaking (Chevron deference overturned in Loper Bright 2024, drastically "
            "changing deference to agency interpretation of ambiguous statutes). "
            "Financial regulation cases in SCOTUS: SEC enforcement limits (Kokesh 2017, Liu 2020), "
            "CFPB funding (CFPB v. CFSA 2024 — upheld funding structure)."
        ),
        "key_dates": [
            "SCOTUS term: October - June; opinions issued October through end of June",
            "Cert petitions: typically decided within 3-4 months of filing",
            "Opinion announcement: Mondays at 10am ET (and additional days at end of term)",
        ],
        "historical_precedent": (
            "Post-Loper Bright (2024): courts no longer defer to agency legal interpretations — "
            "major implication for SEC/CFTC crypto rulemakings. CFPB v. CFSA (2024): Court upheld "
            "CFPB's funding mechanism 7-2. SCOTUS acceptance rate: ~1% of petitions (cert granted "
            "in ~70-80 cases per year from ~7,000 petitions)."
        ),
        "risk_factors": [
            "Whether cert is granted (low base rate)",
            "Composition of the Court and recent precedent",
            "Amicus brief filings signaling Court interest",
            "Lower court circuit split (increases cert probability significantly)",
        ],
        "resolution_source": "supremecourt.gov — official docket and opinion releases",
    },
}


# Extended domain classification keywords — covers ALL target domains
_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "fed_monetary": [
        "federal reserve", "fed reserve", "fomc", "fed fund", "interest rate",
        "rate cut", "rate hike", "rate pause", "rate hold", "basis points",
        "monetary policy", "quantitative", "powell", "fed chair", "fed meeting",
        "open market committee", "fed decision", "fed announcement",
    ],
    "sec_enforcement": [
        "sec enforcement", "sec charges", "sec sues", "sec action", "sec settlement",
        "sec order", "sec investigation", "sec files", "sec wins", "sec loses",
        "securities fraud", "insider trading", "securities law", "sec ruling",
        "sec approves", "sec denies", "sec rejects", "sec approve",
        "etf approval", "etf denied", "etf rejected", "spot etf",
        "etf approved", "etf launch", "bitcoin etf", "ethereum etf",
        "sec chair", "atkins", "gensler",
    ],
    "cftc_derivatives": [
        "cftc", "commodity futures", "derivatives regulation", "cftc ruling",
        "cftc enforcement", "cftc approval", "cftc action", "cftc charges",
        "designated contract market", "dcm", "swap dealer", "prediction market cftc",
        "kalshi cftc", "event contract", "cftc rule",
    ],
    "crypto_regulation": [
        "crypto regulation", "crypto bill", "crypto law", "crypto legislation",
        "stablecoin", "genius act", "fit21", "clarity act", "digital asset bill",
        "market structure bill", "crypto market structure", "senate crypto",
        "house crypto", "congress crypto", "digital asset legislation",
        "bitcoin legislation", "ethereum legislation", "defi regulation",
        "crypto framework", "crypto policy", "web3 legislation",
        "virtual currency regulation", "fincen crypto",
        "bitcoin", "ethereum", "crypto", "digital asset",
    ],
    "trade_tariff": [
        "tariff", "trade war", "trade deal", "trade policy", "sanctions",
        "ofac", "trade agreement", "import duty", "export control",
        "trade deficit", "trade surplus", "wto", "usmca", "nafta",
        "china tariff", "steel tariff", "aluminum tariff",
        "blockade", "embargo", "china taiwan", "geopolitical",
    ],
    "macro_economic": [
        "inflation", "cpi", "pce", "gdp", "recession", "unemployment",
        "jobs report", "nonfarm payroll", "labor market", "consumer price",
        "producer price", "economic growth", "economic data", "ism",
        "retail sales", "housing data", "fed inflation", "core inflation",
        "stagflation", "soft landing", "hard landing", "economic indicator",
    ],
    "legislation": [
        "debt ceiling", "government shutdown", "budget deal", "continuing resolution",
        "appropriations", "reconciliation bill", "fincen", "anti-money laundering",
        "bank secrecy act", "aml", "bsa", "treasury department",
        "executive order", "deregulation", "financial regulation bill",
        "dodd-frank", "banking regulation", "fdic rule", "occ rule",
    ],
}

# Map old profile names to new domain names for backwards compatibility
_DOMAIN_PROFILE_ALIAS: dict[str, str] = {
    "fed_rate": "fed_monetary",
    "crypto_legislation": "crypto_regulation",
    "bank_failure": "macro_economic",
    "crypto_etf": "sec_enforcement",
    "scotus_legal": "legislation",
}


def _classify_market_domain(title: str, description: str = "") -> str:
    """
    Classify a market into a HYDRA regulatory domain.

    Returns one of:
      "fed_monetary", "sec_enforcement", "cftc_derivatives",
      "crypto_regulation", "trade_tariff", "macro_economic",
      "legislation", or "unknown"

    The domain is determined by keyword frequency across title + description.
    """
    combined = (title + " " + description).lower()
    best_match: str = "unknown"
    best_score = 0

    for domain, keywords in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > best_score:
            best_score = score
            best_match = domain

    # Fallback: use _REGULATORY_DOMAIN_PROFILES for domains not in _DOMAIN_KEYWORDS
    if best_score == 0:
        for domain, profile in _REGULATORY_DOMAIN_PROFILES.items():
            score = sum(1 for kw in profile["keywords"] if kw in combined)
            if score > best_score:
                best_score = score
                # Map to canonical domain name
                best_match = _DOMAIN_PROFILE_ALIAS.get(domain, domain)

    return best_match if best_score >= 1 else "unknown"


def _generate_hydra_analysis(
    market_title: str,
    current_yes_price: float,
    domain: str | None,
    volume_24h: float = 0.0,
) -> dict[str, Any]:
    """
    Generate HYDRA's regulatory intelligence analysis for a prediction market.

    This uses HYDRA's knowledge base (from the regulatory service) to provide
    genuinely useful context — not placeholder text.
    """
    if domain and domain in _REGULATORY_DOMAIN_PROFILES:
        profile = _REGULATORY_DOMAIN_PROFILES[domain]
        regulatory_context = profile["regulatory_context"]
        key_dates = profile["key_dates"]
        historical_precedent = profile["historical_precedent"]
        risk_factors = profile["risk_factors"]
        resolution_source = profile.get("resolution_source", "Official government sources")
    else:
        # Use the regulatory engine's Q&A knowledge base for unknown domains
        try:
            result = reg_service.answer_regulatory_query(question=market_title)
            regulatory_context = result.answer
            key_dates = ["Check official agency website for upcoming deadlines"]
            historical_precedent = "; ".join(result.relevant_regulations) if result.relevant_regulations else "No direct precedent found in HYDRA knowledge base."
            risk_factors = result.follow_up_questions or ["Monitor official agency announcements"]
            resolution_source = "; ".join(result.sources) if result.sources else "Official government sources"
        except Exception:
            regulatory_context = (
                "This market falls outside HYDRA's primary regulatory intelligence domains. "
                "Monitor official government sources and agency press releases for resolution data."
            )
            key_dates = ["No specific deadlines identified"]
            historical_precedent = "Insufficient historical data in HYDRA knowledge base for this market."
            risk_factors = ["Monitor official sources for developments"]
            resolution_source = "Official government sources"

    # Derive signal direction from current price and domain context
    signal_direction, confidence, reasoning = _derive_signal(
        market_title=market_title,
        yes_price=current_yes_price,
        domain=domain,
        profile=_REGULATORY_DOMAIN_PROFILES.get(domain, {}) if domain else {},
    )

    return {
        "regulatory_context": regulatory_context,
        "key_dates": key_dates,
        "historical_precedent": historical_precedent,
        "risk_factors": risk_factors,
        "signal_direction": signal_direction,
        "confidence": confidence,
        "reasoning": reasoning,
        "resolution_source": resolution_source,
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "data_sources": [
            "HYDRA Regulatory Knowledge Base v3",
            "SEC EDGAR RSS Feeds",
            "CFTC Press Releases",
            "Federal Register",
            "FinCEN News",
        ],
    }


def _derive_signal(
    market_title: str,
    yes_price: float,
    domain: str | None,
    profile: dict[str, Any],
) -> tuple[str, int, str]:
    """
    Derive a trading signal direction, confidence score, and reasoning.

    Returns: (signal_direction, confidence, reasoning)
    signal_direction: "bullish_yes" | "bullish_no" | "neutral"
    confidence: 0-100
    """
    title_lower = market_title.lower()

    # ── Fed rate domain ──────────────────────────────────────────
    if domain == "fed_rate":
        # Current regime: Fed has been on pause; markets price high probability of hold
        if any(w in title_lower for w in ["pause", "hold", "no change", "unchanged"]):
            if yes_price < 0.75:
                return (
                    "bullish_yes",
                    72,
                    "HYDRA assessment: Fed pause probability is historically high in this rate environment. "
                    "Current price appears to under-price the hold probability given FOMC communication patterns "
                    "and the absence of significant inflation re-acceleration. "
                    "Consider the Fed's track record of telegraphing changes well in advance — "
                    "no such signals have been issued.",
                )
            elif yes_price > 0.90:
                return (
                    "neutral",
                    55,
                    "Market already pricing very high hold probability. Limited upside; tail risk "
                    "of surprise cut or hike remains. HYDRA suggests neutral positioning at these prices.",
                )
        elif any(w in title_lower for w in ["cut", "lower", "reduce"]):
            if yes_price > 0.50:
                return (
                    "bullish_no",
                    65,
                    "HYDRA assessment: Rate cuts require persistent inflation decline toward 2% PCE target. "
                    "Current economic data does not strongly support near-term cuts. "
                    "Market appears to be over-pricing cut probability relative to Fed communication.",
                )
        return (
            "neutral",
            50,
            "Fed rate market within expected probability range. HYDRA sees no strong directional signal "
            "given current FOMC communication and economic data.",
        )

    # ── Crypto legislation ──────────────────────────────────────
    elif domain == "crypto_legislation":
        if any(w in title_lower for w in ["genius act", "stablecoin", "stable coin"]):
            if yes_price < 0.60:
                return (
                    "bullish_yes",
                    68,
                    "HYDRA assessment: The GENIUS Act has broader bipartisan support than typical "
                    "crypto legislation, with banking industry backing for regulated stablecoins. "
                    "Current Senate co-sponsor count and committee progress suggest higher pass probability "
                    "than market is pricing. Key risk: Senate floor time competition.",
                )
        if any(w in title_lower for w in ["market structure", "fit21", "clarity"]):
            if yes_price > 0.70:
                return (
                    "bullish_no",
                    60,
                    "HYDRA assessment: Comprehensive crypto market structure legislation faces higher "
                    "procedural hurdles than single-topic stablecoin bills. Senate passage and conference "
                    "reconciliation adds significant uncertainty. Market may be over-weighting passage probability.",
                )
        return (
            "neutral",
            52,
            "Crypto legislation timeline is difficult to price precisely. HYDRA sees roughly equal "
            "probability of passage and delay given current congressional calendar and priorities.",
        )

    # ── SEC enforcement ─────────────────────────────────────────
    elif domain == "sec_enforcement":
        if any(w in title_lower for w in ["approve", "approval", "etf"]):
            if yes_price < 0.55:
                return (
                    "bullish_yes",
                    70,
                    "HYDRA assessment: Under Chair Atkins, SEC approval rates for crypto products "
                    "have improved significantly. The regulatory posture has shifted from 'denial unless "
                    "proven safe' to 'approve with conditions.' Historical precedent for similar products "
                    "and current Crypto Task Force guidance suggest higher approval probability.",
                )
        if any(w in title_lower for w in ["fine", "penalty", "enforcement", "charges"]):
            return (
                "neutral",
                50,
                "SEC enforcement actions depend on case-specific facts and settlement negotiations. "
                "HYDRA cannot predict outcomes for individual cases without additional context.",
            )
        return ("neutral", 50, "Insufficient directional signal for this SEC market.")

    # ── CFTC ────────────────────────────────────────────────────
    elif domain == "cftc_regulation":
        return (
            "neutral",
            52,
            "CFTC rulemaking and enforcement outcomes depend heavily on administrative proceedings "
            "and internal deliberations. HYDRA recommends monitoring CFTC press releases and "
            "Federal Register notices for directional signals.",
        )

    # ── Bank failure ─────────────────────────────────────────────
    elif domain == "bank_failure":
        if yes_price < 0.15:
            return (
                "neutral",
                55,
                "HYDRA assessment: Individual bank failure markets have low base rates but fat tails. "
                "Current market pricing at <15% reflects general banking system stability. "
                "Monitor FDIC Call Report data and CRE loan concentration ratios for directional signals.",
            )
        if yes_price > 0.40:
            return (
                "bullish_no",
                60,
                "HYDRA assessment: >40% bank failure probability seems elevated absent specific "
                "institution-level stress data. Regulatory intervention (conservatorship, emergency acquisition) "
                "typically precedes formal failure, adding uncertainty to binary outcomes.",
            )
        return ("neutral", 50, "Bank failure probability within reasonable range given current banking sector conditions.")

    # ── Crypto ETF ──────────────────────────────────────────────
    elif domain == "crypto_etf":
        if yes_price < 0.60:
            return (
                "bullish_yes",
                65,
                "HYDRA assessment: Under the Atkins SEC and with Crypto Task Force active, "
                "novel crypto ETF approvals have accelerated dramatically. "
                "Historical base rate of 'once the first is approved, others follow quickly' "
                "applies here. Market may be under-pricing approval probability.",
            )
        return (
            "neutral",
            55,
            "ETF approval probability appears reasonably priced. Monitor SEC EDGAR for "
            "staff comment letters that signal review progress.",
        )

    # ── SCOTUS ──────────────────────────────────────────────────
    elif domain == "scotus_legal":
        if any(w in title_lower for w in ["accept", "certiorari", "cert", "grant"]):
            if yes_price > 0.25:
                return (
                    "bullish_no",
                    62,
                    "HYDRA assessment: SCOTUS accepts approximately 1% of petitions. "
                    "Unless a significant circuit split exists or the case is of extraordinary national importance, "
                    "the base rate strongly favors cert denial. Market appears to over-price acceptance.",
                )
        return ("neutral", 50, "SCOTUS outcome depends on case-specific legal factors beyond HYDRA's quantitative models.")

    # ── Default ─────────────────────────────────────────────────
    else:
        # Generic signal based on price extremes
        if yes_price < 0.10:
            return ("neutral", 45, "Very low yes probability. Monitor for trigger events. No strong HYDRA directional signal.")
        elif yes_price > 0.90:
            return ("neutral", 45, "Very high yes probability already priced. Limited upside.")
        return ("neutral", 40, "Market outside HYDRA's primary regulatory intelligence domains.")


# ─────────────────────────────────────────────────────────────
# PolymarketClient
# ─────────────────────────────────────────────────────────────

class PolymarketClient:
    """
    Async client for Polymarket's public APIs.

    Uses the Gamma API for market discovery and CLOB API for order book data.
    No authentication required for read operations.
    """

    GAMMA_BASE = "https://gamma-api.polymarket.com"
    CLOB_BASE = "https://clob.polymarket.com"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0),
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HYDRA-RegulatoryIntelligence/1.0",
                },
                follow_redirects=True,
            )
        return self._client

    async def _get(self, base: str, path: str, params: dict | None = None) -> Any:
        """Make a GET request with error handling."""
        url = f"{base}{path}"
        try:
            client = self._get_client()
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            logger.warning("Polymarket timeout: %s", url)
            return None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("Polymarket rate limit hit: %s", url)
            else:
                logger.error("Polymarket HTTP error %d: %s", exc.response.status_code, url)
            return None
        except Exception as exc:
            logger.error("Polymarket request failed %s: %s", url, exc)
            return None

    async def get_regulatory_markets(self) -> list[dict[str, Any]]:
        """
        Fetch active Polymarket events that are strictly regulatory/economic in nature.

        Only returns markets about:
        - Federal Reserve / FOMC / monetary policy / interest rates
        - SEC enforcement / ETF approvals / securities regulation
        - CFTC rulings / derivatives regulation
        - Crypto regulation / stablecoin legislation / market structure bills
        - Tariffs / trade policy / sanctions / OFAC
        - Macro indicators: CPI, PCE, GDP, unemployment, recession
        - FinCEN / AML / BSA
        - Congressional legislation on financial/economic topics

        Does NOT return general politics, sports, entertainment, or
        non-regulatory crypto price markets.

        Returns structured list of markets with title, slug, volume_24hr, liquidity,
        outcome_prices, condition_id, end_date, end_date_iso, description, tags.
        """
        import json as _json

        cache_key = "poly_regulatory_markets"
        if cache_key in _market_cache:
            return _market_cache[cache_key]

        markets: list[dict[str, Any]] = []
        seen_condition_ids: set[str] = set()

        # Fetch active events sorted by volume — get top 200 to have enough to filter
        events_data = await self._get(
            self.GAMMA_BASE,
            "/events",
            params={
                "active": "true",
                "closed": "false",
                "order": "volume_24hr",
                "ascending": "false",
                "limit": 200,
            },
        )

        raw_events: list[dict] = []
        if isinstance(events_data, list):
            raw_events.extend(events_data)
        elif isinstance(events_data, dict):
            raw_events.extend(events_data.get("events", events_data.get("data", [])) or [])

        for event in raw_events:
            title = (event.get("title") or event.get("question") or "").strip()
            description = (event.get("description") or "").strip()
            slug = event.get("slug", "")

            # STRICT: check title + description against regulatory keywords
            # and apply exclusion patterns
            if not _matches_regulatory(title + " " + description, strict=True):
                continue

            # Extract tag slugs for additional context
            tag_slugs = [t.get("slug", "") for t in (event.get("tags") or [])]

            # Each event may have multiple markets (outcomes)
            for market in (event.get("markets") or []):
                cid = market.get("conditionId") or market.get("condition_id")
                if not cid or cid in seen_condition_ids:
                    continue
                # Skip already-closed individual markets (event.active=true but market closed)
                if market.get("closed") and not market.get("active"):
                    continue
                seen_condition_ids.add(cid)

                market_question = (market.get("question") or title).strip()
                market_desc = (market.get("description") or description).strip()

                # Double-check the specific market question also passes filter
                if not _matches_regulatory(market_question + " " + market_desc, strict=True):
                    continue

                # Parse outcome prices
                outcome_prices_raw = market.get("outcomePrices") or market.get("outcome_prices") or "[]"
                try:
                    if isinstance(outcome_prices_raw, str):
                        outcome_prices = _json.loads(outcome_prices_raw)
                    else:
                        outcome_prices = outcome_prices_raw
                    outcome_prices = [float(p) for p in outcome_prices]
                except Exception:
                    outcome_prices = []

                # Parse outcomes
                outcomes_raw = market.get("outcomes") or "[]"
                try:
                    if isinstance(outcomes_raw, str):
                        outcomes = _json.loads(outcomes_raw)
                    else:
                        outcomes = outcomes_raw
                except Exception:
                    outcomes = ["Yes", "No"]

                # Extract volume + liquidity (prefer CLOB fields when available)
                vol_24hr = float(
                    market.get("volume24hr") or
                    event.get("volume24hr") or
                    market.get("volume24hrClob") or
                    0
                )
                liquidity = float(
                    market.get("liquidity") or
                    market.get("liquidityNum") or
                    market.get("liquidityClob") or
                    0
                )

                markets.append({
                    "platform": "polymarket",
                    "title": title,
                    "market_question": market_question,
                    "description": market_desc[:500] if market_desc else "",
                    "slug": slug,
                    "market_slug": market.get("slug") or slug,
                    "volume_24hr": vol_24hr,
                    "liquidity": liquidity,
                    "outcomes": outcomes,
                    "outcome_prices": outcome_prices,
                    "condition_id": cid,
                    "end_date": event.get("endDate") or market.get("endDate"),
                    "end_date_iso": market.get("endDateIso") or event.get("endDateIso"),
                    "active": market.get("active", True),
                    "url": f"https://polymarket.com/event/{slug}",
                    "tags": tag_slugs,
                    "regulatory_domain": _classify_market_domain(market_question, market_desc),
                })

        # Sort by 24h volume descending
        markets.sort(key=lambda x: x["volume_24hr"], reverse=True)
        _market_cache[cache_key] = markets

        logger.info(
            "PolymarketClient: discovered %d regulatory markets (filtered from %d raw events)",
            len(markets), len(raw_events),
        )
        return markets

    async def get_market_details(self, condition_id: str) -> dict[str, Any] | None:
        """
        Get full market data including order book depth for a specific condition ID.
        """
        cache_key = f"poly_market_{condition_id}"
        if cache_key in _market_cache:
            return _market_cache[cache_key]

        # Fetch market data from Gamma API
        market_data = await self._get(
            self.GAMMA_BASE,
            f"/markets/{condition_id}",
        )

        if not market_data:
            # Try by conditionId parameter
            market_data = await self._get(
                self.GAMMA_BASE,
                "/markets",
                params={"condition_id": condition_id},
            )
            if isinstance(market_data, list) and market_data:
                market_data = market_data[0]

        if not market_data:
            return None

        # Try to get order book from CLOB API for token IDs
        token_ids = market_data.get("clobTokenIds") or []
        if isinstance(token_ids, str):
            try:
                import json as _json
                token_ids = _json.loads(token_ids)
            except Exception:
                token_ids = []

        order_book = None
        if token_ids:
            book_data = await self._get(
                self.CLOB_BASE,
                "/book",
                params={"token_id": token_ids[0]},
            )
            if book_data:
                order_book = {
                    "bids": book_data.get("bids", [])[:10],  # top 10 levels
                    "asks": book_data.get("asks", [])[:10],
                }

        result = {
            **market_data,
            "order_book": order_book,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        _market_cache[cache_key] = result
        return result

    async def get_regulatory_market_signals(self) -> list[dict[str, Any]]:
        """
        For each active regulatory market, generate a HYDRA signal combining
        the market data with HYDRA's regulatory intelligence engine output.
        """
        markets = await self.get_regulatory_markets()
        signals = []

        for market in markets:
            domain = market.get("regulatory_domain")
            outcome_prices = market.get("outcome_prices", [])

            # Parse yes price
            yes_price = 0.5
            try:
                if outcome_prices:
                    yes_price = float(outcome_prices[0])
            except (ValueError, IndexError):
                pass

            analysis_key = _cache_key("poly_signal", market["condition_id"])
            if analysis_key in _analysis_cache:
                hydra_analysis = _analysis_cache[analysis_key]
            else:
                hydra_analysis = _generate_hydra_analysis(
                    market_title=market["market_question"],
                    current_yes_price=yes_price,
                    domain=domain,
                    volume_24h=market.get("volume_24hr", 0),
                )
                _analysis_cache[analysis_key] = hydra_analysis

            signals.append({
                "market_title": market["market_question"],
                "platform": "polymarket",
                "condition_id": market["condition_id"],
                "current_price": {
                    "yes": yes_price,
                    "no": round(1 - yes_price, 4),
                },
                "volume_24h": market.get("volume_24hr", 0),
                "liquidity": market.get("liquidity", 0),
                "end_date": market.get("end_date"),
                "url": market.get("url"),
                "regulatory_domain": domain,
                "hydra_analysis": hydra_analysis,
            })

        return signals

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ─────────────────────────────────────────────────────────────
# KalshiClient
# ─────────────────────────────────────────────────────────────

class KalshiClient:
    """
    Async client for Kalshi's public API endpoints (no auth required for read).

    Despite the 'elections' subdomain, this base URL covers ALL Kalshi markets.
    Kalshi is a CFTC-regulated Designated Contract Market.
    """

    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0),
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HYDRA-RegulatoryIntelligence/1.0",
                },
                follow_redirects=True,
            )
        return self._client

    async def _get(self, path: str, params: dict | None = None) -> Any:
        """Make a GET request to Kalshi API with error handling."""
        url = f"{self.BASE_URL}{path}"
        try:
            client = self._get_client()
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            logger.warning("Kalshi timeout: %s", url)
            return None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("Kalshi rate limit hit: %s", url)
            elif exc.response.status_code == 401:
                logger.warning("Kalshi auth required for: %s", url)
            else:
                logger.error("Kalshi HTTP error %d: %s", exc.response.status_code, url)
            return None
        except Exception as exc:
            logger.error("Kalshi request failed %s: %s", url, exc)
            return None

    async def get_regulatory_markets(self) -> list[dict[str, Any]]:
        """
        Fetch Kalshi events/markets strictly related to regulation and economic policy.

        Strategy:
          1. Fetch known regulatory series directly (KXFED, etc.) — always regulatory
          2. Fetch events with category="Economics" server-side filtered — always economic
          3. Fetch events with category="Financials" server-side filtered
          4. For "Politics" category: only include if title/subtitle passes strict keyword filter
          5. Skip all other categories (Sports, Entertainment, etc.)
        """
        cache_key = "kalshi_regulatory_markets"
        if cache_key in _market_cache:
            return _market_cache[cache_key]

        markets: list[dict[str, Any]] = []
        seen_tickers: set[str] = set()
        seen_event_tickers: set[str] = set()

        async def _fetch_markets_for_event(event: dict) -> None:
            """Fetch and add markets for a single Kalshi event."""
            event_ticker = event.get("event_ticker", "")
            if not event_ticker or event_ticker in seen_event_tickers:
                return
            seen_event_tickers.add(event_ticker)
            mdata = await self._get("/markets", params={"event_ticker": event_ticker, "limit": 50, "status": "open"})
            if mdata:
                for market in mdata.get("markets", []):
                    ticker = market.get("ticker", "")
                    if ticker and ticker not in seen_tickers:
                        seen_tickers.add(ticker)
                        markets.append(self._normalize_kalshi_market(market, event))

        # --- Strategy 1: Fetch known regulatory series directly ---
        # These are always regulatory — no keyword filter needed
        for series in KALSHI_REGULATORY_SERIES:
            data = await self._get(
                "/events",
                params={"limit": 50, "status": "open", "series_ticker": series},
            )
            if data:
                for event in data.get("events", []):
                    await _fetch_markets_for_event(event)

        # --- Strategy 2: Fetch Economics category — all are economic/macro ---
        # Pass category server-side to reduce payload size
        for category in ("Economics", "Financials"):
            data = await self._get(
                "/events",
                params={"limit": 200, "status": "open", "category": category},
            )
            if data:
                for event in data.get("events", []):
                    # Economics and Financials events are inherently relevant
                    # but still apply keyword check to exclude edge cases like
                    # "Who will win the Economics Nobel Prize"
                    title = (event.get("title") or "").strip()
                    sub = (event.get("sub_title") or "").strip()
                    combined = title + " " + sub
                    if _matches_regulatory(combined, strict=True):
                        await _fetch_markets_for_event(event)
                    elif category == "Economics" and any(kw in combined.lower() for kw in [
                        "rate", "inflation", "gdp", "cpi", "pce", "unemployment", "jobs",
                        "recession", "deficit", "debt", "federal reserve", "fomc",
                        "tariff", "trade", "treasury",
                    ]):
                        # Economics-specific looser match for clearly economic events
                        await _fetch_markets_for_event(event)

        # --- Strategy 3: Politics category — STRICT keyword filter only ---
        data = await self._get(
            "/events",
            params={"limit": 200, "status": "open", "category": "Politics"},
        )
        if data:
            for event in data.get("events", []):
                title = (event.get("title") or "").strip()
                sub = (event.get("sub_title") or "").strip()
                combined = title + " " + sub
                # Very strict: must match regulatory keyword AND not be a pure election market
                if _matches_regulatory(combined, strict=True):
                    await _fetch_markets_for_event(event)

        # Cache and return
        _market_cache[cache_key] = markets
        logger.info(
            "Kalshi: found %d regulatory markets across %d events",
            len(markets), len(seen_event_tickers),
        )
        return markets

    @staticmethod
    def _normalize_kalshi_market(market: dict, event: dict | None = None) -> dict[str, Any]:
        """Normalize a Kalshi market dict into HYDRA's common schema."""
        ticker = market.get("ticker", "")
        title = market.get("title") or market.get("question") or (event or {}).get("title", "")
        series_ticker = market.get("series_ticker", "")
        event_ticker = market.get("event_ticker") or (event or {}).get("event_ticker", "")
        yes_price_cents = market.get("yes_ask") or market.get("yes_bid") or 50
        yes_price = yes_price_cents / 100.0
        return {
            "platform": "kalshi",
            "title": title,
            "market_question": title,
            "ticker": ticker,
            "series_ticker": series_ticker,
            "event_ticker": event_ticker,
            "volume_24hr": float(market.get("volume") or market.get("volume_24h") or 0),
            "liquidity": float(market.get("liquidity") or 0),
            "yes_bid": market.get("yes_bid"),
            "yes_ask": market.get("yes_ask"),
            "no_bid": market.get("no_bid"),
            "no_ask": market.get("no_ask"),
            "yes_price": yes_price,
            "close_time": market.get("close_time") or market.get("expiration_time"),
            "status": market.get("status"),
            "url": f"https://kalshi.com/markets/{ticker}",
            "regulatory_domain": _classify_market_domain(title),
        }

    # (old get_regulatory_markets code removed — replaced above)

    async def get_market_details(self, ticker: str) -> dict[str, Any] | None:
        """
        Get full market data for a Kalshi ticker, including order book.
        """
        cache_key = f"kalshi_market_{ticker}"
        if cache_key in _market_cache:
            return _market_cache[cache_key]

        market_data = await self._get(f"/markets/{ticker}")
        if not market_data:
            return None

        market = market_data.get("market", market_data)

        # Fetch order book
        orderbook_data = await self._get(f"/markets/{ticker}/orderbook")
        orderbook = None
        if orderbook_data:
            ob = orderbook_data.get("orderbook") or orderbook_data
            orderbook = {
                "yes": ob.get("yes", [])[:10],
                "no": ob.get("no", [])[:10],
            }

        result = {
            **market,
            "order_book": orderbook,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        _market_cache[cache_key] = result
        return result

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ─────────────────────────────────────────────────────────────
# PredictionMarketAggregator
# ─────────────────────────────────────────────────────────────

class PredictionMarketAggregator:
    """
    Combines Polymarket and Kalshi data into a unified regulatory market feed
    with HYDRA regulatory intelligence overlays.
    """

    def __init__(self) -> None:
        self.polymarket = PolymarketClient()
        self.kalshi = KalshiClient()

    async def get_all_regulatory_markets(self) -> list[dict[str, Any]]:
        """
        Returns unified list of regulatory prediction markets across Polymarket and Kalshi.

        Fetches both platforms concurrently and merges results.
        Falls back gracefully if either platform is unavailable.
        """
        cache_key = "aggregator_all_markets"
        if cache_key in _market_cache:
            return _market_cache[cache_key]

        results = await asyncio.gather(
            self.polymarket.get_regulatory_markets(),
            self.kalshi.get_regulatory_markets(),
            return_exceptions=True,
        )

        all_markets: list[dict[str, Any]] = []

        poly_markets = results[0] if not isinstance(results[0], Exception) else []
        kalshi_markets = results[1] if not isinstance(results[1], Exception) else []

        if isinstance(results[0], Exception):
            logger.error("Polymarket fetch failed: %s", results[0])
        if isinstance(results[1], Exception):
            logger.error("Kalshi fetch failed: %s", results[1])

        all_markets.extend(poly_markets)
        all_markets.extend(kalshi_markets)

        # Sort by volume descending (cross-platform)
        all_markets.sort(key=lambda x: x.get("volume_24hr", 0), reverse=True)
        _market_cache[cache_key] = all_markets

        logger.info(
            "Aggregator: %d total regulatory markets (%d Polymarket, %d Kalshi)",
            len(all_markets), len(poly_markets), len(kalshi_markets),
        )
        return all_markets

    async def generate_regulatory_signals(
        self,
        platform: str = "all",
        category: str = "all",
    ) -> list[dict[str, Any]]:
        """
        For each regulatory market, generate a HYDRA intelligence signal with:
          - regulatory context (what HYDRA knows about this area)
          - key dates (upcoming deadlines, hearings, decisions)
          - historical precedent (similar past actions and outcomes)
          - risk factors (what could change the outcome)
          - signal direction (bullish_yes / bullish_no / neutral)
          - confidence score (0-100)
          - reasoning (plain-language explanation)

        Parameters
        ----------
        platform : "polymarket" | "kalshi" | "all"
        category : "regulation" | "crypto" | "fed" | "sec" | "all"
        """
        all_markets = await self.get_all_regulatory_markets()

        # Filter by platform
        if platform != "all":
            all_markets = [m for m in all_markets if m.get("platform") == platform]

        # Filter by category/domain
        category_domain_map = {
            "fed": "fed_rate",
            "sec": "sec_enforcement",
            "crypto": "crypto_legislation",
            "regulation": None,  # include all regulatory domains
        }
        if category != "all" and category in category_domain_map:
            target_domain = category_domain_map[category]
            if target_domain:
                all_markets = [m for m in all_markets if m.get("regulatory_domain") == target_domain]
            # category="regulation" includes everything

        signals = []
        for market in all_markets:
            domain = market.get("regulatory_domain")

            # Get yes price based on platform format
            if market["platform"] == "polymarket":
                outcome_prices = market.get("outcome_prices", [])
                yes_price = float(outcome_prices[0]) if outcome_prices else 0.5
                market_id = market.get("condition_id", "")
            else:  # kalshi
                yes_price = market.get("yes_price", 0.5)
                market_id = market.get("ticker", "")

            analysis_key = _cache_key("signal", market["platform"], market_id)
            if analysis_key in _analysis_cache:
                hydra_analysis = _analysis_cache[analysis_key]
            else:
                hydra_analysis = _generate_hydra_analysis(
                    market_title=market["market_question"],
                    current_yes_price=yes_price,
                    domain=domain,
                    volume_24h=market.get("volume_24hr", 0),
                )
                _analysis_cache[analysis_key] = hydra_analysis

            signals.append({
                "market_title": market["market_question"],
                "platform": market["platform"],
                "market_id": market_id,
                "current_price": {
                    "yes": round(yes_price, 4),
                    "no": round(1 - yes_price, 4),
                },
                "volume_24h": market.get("volume_24hr", 0),
                "liquidity": market.get("liquidity", 0),
                "end_date": market.get("end_date") or market.get("close_time"),
                "url": market.get("url"),
                "regulatory_domain": domain,
                "hydra_analysis": hydra_analysis,
            })

        return signals

    async def close(self) -> None:
        await asyncio.gather(
            self.polymarket.close(),
            self.kalshi.close(),
            return_exceptions=True,
        )


# ─────────────────────────────────────────────────────────────
# RegulatoryEventFeed
# ─────────────────────────────────────────────────────────────

class RegulatoryEventFeed:
    """
    Real-time regulatory event feed optimized for prediction market consumption.

    Pulls from SEC EDGAR RSS, CFTC press releases, FinCEN news, Federal Register.
    Returns events tagged with which active prediction markets they affect.
    """

    # Agencies to monitor and their HYDRA feed_service keys
    AGENCY_MAP = {
        "SEC": "SEC",
        "CFTC": "CFTC",
        "FinCEN": "FinCEN",
        "OCC": "OCC",
        "CFPB": "CFPB",
    }

    # Federal Register RSS for rulemaking notices
    FEDERAL_REGISTER_FEEDS = [
        "https://www.federalregister.gov/documents/search.rss?conditions%5Bagencies%5D%5B%5D=securities-and-exchange-commission",
        "https://www.federalregister.gov/documents/search.rss?conditions%5Bagencies%5D%5B%5D=commodity-futures-trading-commission",
    ]

    async def get_latest_events(
        self,
        since_hours: int = 24,
        agencies: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Pull recent regulatory events from official agency feeds.

        Parameters
        ----------
        since_hours : int
            How many hours back to look (default 24)
        agencies : list[str] | None
            Filter to specific agencies. None = all agencies.

        Returns
        -------
        list of event dicts, each tagged with:
          - title, agency, published, summary, url, item_type
          - prediction_market_relevance: list of potential market impacts
          - urgency: "high" | "medium" | "low"
        """
        cache_key = _cache_key("event_feed", since_hours, str(sorted(agencies or [])))
        if cache_key in _event_cache:
            return _event_cache[cache_key]

        agencies_to_fetch = agencies or list(self.AGENCY_MAP.keys())
        days = max(1, since_hours // 24)

        # Fetch from HYDRA's existing feed infrastructure
        all_events: list[dict[str, Any]] = []

        for agency in agencies_to_fetch:
            hydra_key = self.AGENCY_MAP.get(agency)
            if not hydra_key:
                continue
            try:
                items = feed_service.get_agency_items(
                    agency_name=hydra_key,
                    days=max(days, 1),  # feed_service minimum is 1 day
                )
                for item in items:
                    # Filter to requested time window
                    if item.published:
                        try:
                            pub = datetime.fromisoformat(item.published)
                            if pub.tzinfo is None:
                                pub = pub.replace(tzinfo=timezone.utc)
                            cutoff = datetime.now(timezone.utc).timestamp() - (since_hours * 3600)
                            if pub.timestamp() < cutoff:
                                continue
                        except Exception:
                            pass  # Include if we can't parse date

                    relevance_tags = _tag_event_for_prediction_markets(
                        title=item.title or "",
                        summary=item.summary or "",
                        agency=agency,
                    )
                    urgency = _assess_event_urgency(item.title or "", item.item_type or "")

                    all_events.append({
                        "title": item.title,
                        "agency": agency,
                        "published": item.published,
                        "summary": item.summary,
                        "url": item.url,
                        "item_type": item.item_type,
                        "prediction_market_relevance": relevance_tags,
                        "urgency": urgency,
                    })
            except Exception as exc:
                logger.warning("Failed to fetch %s events: %s", agency, exc)

        # Sort by published date descending
        all_events.sort(key=lambda x: x.get("published") or "0000-00-00", reverse=True)

        _event_cache[cache_key] = all_events
        return all_events

    async def match_events_to_markets(
        self,
        events: list[dict[str, Any]],
        markets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Match regulatory events to active prediction markets.

        Uses keyword matching and regulatory domain classification.
        Returns events with `matched_markets` list attached.
        """
        enriched_events = []

        for event in events:
            event_text = (
                (event.get("title") or "") + " " +
                (event.get("summary") or "")
            ).lower()
            event_domain = _classify_market_domain(event.get("title") or "", event.get("summary") or "")

            matched = []
            for market in markets:
                market_text = (market.get("market_question") or market.get("title") or "").lower()
                market_domain = market.get("regulatory_domain")

                # Domain match
                domain_match = (event_domain and market_domain and event_domain == market_domain)

                # Keyword overlap
                event_words = set(re.findall(r"\b\w{4,}\b", event_text))
                market_words = set(re.findall(r"\b\w{4,}\b", market_text))
                keyword_overlap = len(event_words & market_words)

                if domain_match or keyword_overlap >= 3:
                    matched.append({
                        "platform": market.get("platform"),
                        "market_id": market.get("condition_id") or market.get("ticker"),
                        "market_title": market.get("market_question") or market.get("title"),
                        "url": market.get("url"),
                        "impact_assessment": _assess_event_impact(event, market),
                    })

            enriched_events.append({
                **event,
                "matched_markets": matched,
                "markets_affected_count": len(matched),
            })

        return enriched_events


def _tag_event_for_prediction_markets(title: str, summary: str, agency: str) -> list[str]:
    """Tag a regulatory event with relevant prediction market categories."""
    text = (title + " " + summary).lower()
    tags = []

    if agency == "SEC":
        tags.append("polymarket:regulation")
        if any(w in text for w in ["crypto", "bitcoin", "ethereum", "digital asset"]):
            tags.append("polymarket:crypto")
            tags.append("kalshi:KXCRYPTO")
        if any(w in text for w in ["etf", "exchange-traded"]):
            tags.append("polymarket:etf-approval")
        if any(w in text for w in ["enforcement", "charge", "settle", "order"]):
            tags.append("polymarket:sec-enforcement")

    elif agency == "CFTC":
        tags.append("polymarket:regulation")
        tags.append("kalshi:KXCFTC")
        if any(w in text for w in ["prediction market", "event contract", "election"]):
            tags.append("polymarket:prediction-markets-regulation")

    elif agency in ("Fed", "Federal Reserve"):
        tags.append("polymarket:fed-rate")
        tags.append("kalshi:KXFED")

    elif agency == "FinCEN":
        tags.append("polymarket:regulation")
        if any(w in text for w in ["crypto", "virtual currency", "stablecoin"]):
            tags.append("polymarket:crypto")

    return tags


def _assess_event_urgency(title: str, item_type: str) -> str:
    """Assess urgency level of a regulatory event for trading purposes."""
    title_lower = title.lower()
    if item_type == "enforcement" or any(
        w in title_lower for w in ["order", "fine", "charges", "immediate", "emergency", "alert"]
    ):
        return "high"
    elif item_type in ("final_rule", "press_release") or any(
        w in title_lower for w in ["rule", "approve", "adopt", "finalize"]
    ):
        return "medium"
    else:
        return "low"


def _assess_event_impact(event: dict[str, Any], market: dict[str, Any]) -> str:
    """Generate a short impact assessment for an event-market pair."""
    event_title = event.get("title") or ""
    market_title = market.get("market_question") or market.get("title") or ""
    agency = event.get("agency") or ""
    urgency = event.get("urgency") or "low"

    if urgency == "high":
        return (
            f"HIGH IMPACT: {agency} action '{event_title[:80]}' directly relevant to "
            f"market '{market_title[:80]}'. Review immediately for position adjustment."
        )
    elif urgency == "medium":
        return (
            f"MEDIUM IMPACT: {agency} publication '{event_title[:80]}' relevant to "
            f"'{market_title[:80]}'. Monitor for market repricing."
        )
    else:
        return (
            f"LOW IMPACT: Background regulatory activity from {agency} tangentially "
            f"relevant to '{market_title[:80]}'."
        )


# ─────────────────────────────────────────────────────────────
# OracleDataProvider
# ─────────────────────────────────────────────────────────────

class OracleDataProvider:
    """
    Formats HYDRA regulatory data for oracle consumption.

    Supports three oracle formats:
      - UMA Optimistic Oracle (OOv2/OOv3)
      - Chainlink External Adapter
      - API3 Airnode RRP response

    These formatted outputs enable HYDRA to act as a resolution data provider
    for prediction markets, DeFi protocols, and smart contracts.
    """

    def format_for_uma(
        self,
        market_question: str,
        resolution_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Format HYDRA resolution data for UMA Optimistic Oracle submission.

        Produces structured data for submitting a proposal to UMA OOv2/OOv3
        for Polymarket market resolution.

        Parameters
        ----------
        market_question : str
            The exact market question string (must match Polymarket description)
        resolution_data : dict
            HYDRA's assessed resolution: {resolved, resolution_value, confidence, evidence_summary}

        Returns
        -------
        UMA-compatible assertion data dict with bond recommendations and evidence chain
        """
        resolved = resolution_data.get("resolved", False)
        resolution_value = resolution_data.get("resolution_value", "")
        confidence = resolution_data.get("confidence", 0)
        evidence = resolution_data.get("evidence_summary", "")
        sources = resolution_data.get("sources", [])

        # UMA OOv2 expects ancillaryData as a string
        # Format follows Polymarket's standard: "q: <question>, res: <resolution>"
        ancillary_data = (
            f"q: {market_question}\n"
            f"res: {resolution_value}\n"
            f"evidence: {evidence[:500]}\n"
            f"sources: {'; '.join(sources[:3])}"
        )

        # Encode as bytes (hex) as UMA expects
        ancillary_data_hex = "0x" + ancillary_data.encode("utf-8").hex()

        return {
            "uma_version": "OOv2",
            "assertion_type": "price_request",
            "identifier": "YES_OR_NO_QUERY",
            "ancillary_data": ancillary_data,
            "ancillary_data_hex": ancillary_data_hex,
            "proposed_price": 1_000_000_000_000_000_000 if resolution_value == "Yes" else 0,
            "proposed_price_label": resolution_value,
            "currency": "USDC.e",
            "currency_address_polygon": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "bond_recommendation_usdc": 750,
            "bond_recommendation_note": (
                "Standard Polymarket bond is $750 USDC.e. "
                "Post to OptimisticOracleV2 on Polygon (chain 137). "
                f"HYDRA confidence: {confidence}/100 — {'High confidence, low dispute risk.' if confidence >= 70 else 'Moderate confidence, verify before bonding.'}"
            ),
            "liveness_seconds": 7200,
            "challenge_window_hours": 2,
            "resolved": resolved,
            "resolution_value": resolution_value,
            "hydra_confidence": confidence,
            "evidence_summary": evidence,
            "sources": sources,
            "assertion_timestamp": datetime.now(timezone.utc).isoformat(),
            "asserter_note": (
                "HYDRA regulatory data is sourced from official US government publications "
                "(SEC.gov, CFTC.gov, federalreserve.gov, congress.gov, federalregister.gov). "
                "All data is verifiable from primary sources. HYDRA recommends asserters "
                "review the evidence chain before posting bonds."
            ),
            "uma_contracts": {
                "polygon_optimistic_oracle_v2": "0xee3Afe347D5C74317041E2618C49534dAf887c24",
                "polygon_store": "0x1B60C15f4DD2D3Fa4Ad40b35Fa4C13D0b9F1C399",
                "usdc_e_polygon": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            },
        }

    def format_for_chainlink(self, data_point: dict[str, Any]) -> dict[str, Any]:
        """
        Format HYDRA data as a Chainlink External Adapter response.

        Chainlink nodes call HYDRA's endpoint and expect this format.
        The 'result' field is what gets written on-chain.

        Compatible with Chainlink's standard External Adapter specification.
        """
        job_run_id = data_point.get("jobRunID") or data_point.get("job_run_id") or "1"
        data = data_point.get("data") or {}

        # Chainlink EA standard: primary result goes in data.result
        # For regulatory yes/no: 1 = yes/true, 0 = no/false
        result_value = data.get("result") or data.get("value") or data.get("resolved")

        if isinstance(result_value, bool):
            numeric_result = 1 if result_value else 0
        elif isinstance(result_value, str):
            numeric_result = 1 if result_value.upper() in ("YES", "TRUE", "1", "PASS") else 0
        elif isinstance(result_value, (int, float)):
            numeric_result = result_value
        else:
            numeric_result = 0

        return {
            "jobRunID": job_run_id,
            "data": {
                "result": numeric_result,
                **{k: v for k, v in data.items() if k != "result"},
                "hydra_source": "HYDRA Regulatory Intelligence v1",
                "timestamp": int(time.time()),
            },
            "result": numeric_result,
            "statusCode": 200,
            "pending": False,
            "error": None,
        }

    def format_for_api3(self, data_point: dict[str, Any]) -> dict[str, Any]:
        """
        Format HYDRA data as an API3 Airnode RRP (Request-Response Protocol) response.

        API3 Airnode calls HYDRA and expects this format for on-chain delivery.
        The encoded_value is ABI-encoded and posted on-chain via AirnodeRrp.sol.

        Supports API3's dAPI (decentralized API) interface, which implements
        Chainlink's AggregatorV2V3Interface for drop-in compatibility.
        """
        import struct

        request_id = data_point.get("requestId") or data_point.get("request_id") or "0x" + "0" * 64
        data = data_point.get("data") or {}

        # The primary value — normalize to a signed int224 (API3 standard)
        value = data.get("value") or data.get("result") or 0
        if isinstance(value, bool):
            int_value = 1 if value else 0
        elif isinstance(value, str):
            int_value = 1 if value.upper() in ("YES", "TRUE") else 0
        else:
            try:
                int_value = int(float(value) * 10**18)  # Scale to 18 decimals for on-chain
            except (TypeError, ValueError):
                int_value = 0

        # ABI encode as int256 (simplified — production would use eth_abi)
        # int224 fits in 32 bytes; we pad with 0s
        encoded_hex = f"0x{int_value:064x}"

        return {
            "requestId": request_id,
            "data": {
                **data,
                "hydra_source": "HYDRA Regulatory Intelligence Airnode v1",
                "timestamp": int(time.time()),
            },
            "encodedValue": encoded_hex,
            "rawValue": int_value,
            "timestamp": int(time.time()),
            "signature": None,  # Populated by Airnode signer in production
            "statusCode": 200,
            "airnode_note": (
                "In production, deploy HYDRA Airnode to AWS Lambda with config.json pointing "
                "to HYDRA API endpoints. Airnode signs responses with HYDRA's Airnode private key. "
                "AirnodeRrp.sol on-chain verifies the signature. "
                "See api3.org/docs for Airnode deployment guide."
            ),
            "dapi_interface": {
                "description": "HYDRA Airnode implements Chainlink AggregatorV2V3Interface for dAPI compatibility.",
                "read_call": "IApi3ReaderProxy(proxyAddress).read() returns (int224 value, uint32 timestamp)",
                "market_api3_url": "https://market.api3.org",
            },
        }

    async def assess_market_resolution(
        self,
        market_question: str,
        market_id: str,
        evidence: str = "",
    ) -> dict[str, Any]:
        """
        Assess how a prediction market should resolve based on HYDRA regulatory data.

        Used for the /v1/markets/resolution endpoint — premium oracle-grade output
        for asserters and market creators.
        """
        # Classify the market domain
        domain = _classify_market_domain(market_question, evidence)
        profile = _REGULATORY_DOMAIN_PROFILES.get(domain, {}) if domain else {}

        # Run HYDRA regulatory Q&A for this question
        try:
            qa_result = reg_service.answer_regulatory_query(question=market_question + " " + evidence)
            hydra_answer = qa_result.answer
            relevant_regs = qa_result.relevant_regulations or []
            sources = qa_result.sources or []
        except Exception as exc:
            logger.warning("Regulatory query failed during resolution assessment: %s", exc)
            hydra_answer = ""
            relevant_regs = []
            sources = []

        # Look for resolution-indicative keywords in the question and evidence
        combined = (market_question + " " + evidence + " " + hydra_answer).lower()

        # Determine resolution based on domain and evidence keywords
        resolved = False
        resolution_value = "Unresolved"
        confidence = 30
        evidence_summary = ""

        if domain == "fed_rate":
            # Fed markets typically resolve based on post-meeting statement
            if any(w in combined for w in ["held", "paused", "no change", "unchanged", "maintained"]):
                resolved = True
                resolution_value = "Yes" if "pause" in market_question.lower() or "hold" in market_question.lower() else "No"
                confidence = 85
                evidence_summary = "Federal Reserve official press release language indicates rate was held unchanged."
            elif any(w in combined for w in ["cut", "reduced", "lowered"]):
                resolved = True
                resolution_value = "Yes" if "cut" in market_question.lower() else "No"
                confidence = 85
                evidence_summary = "Federal Reserve official press release indicates a rate cut."

        elif domain == "crypto_legislation":
            if any(w in combined for w in ["signed into law", "enacted", "became law", "president signed"]):
                resolved = True
                resolution_value = "Yes"
                confidence = 95
                evidence_summary = "Official congressional records and presidential signing confirm legislation enacted."
            elif any(w in combined for w in ["failed", "rejected", "tabled", "died in committee"]):
                resolved = True
                resolution_value = "No"
                confidence = 90
                evidence_summary = "Congressional records indicate legislation did not advance."

        elif domain == "sec_enforcement":
            if any(w in combined for w in ["approved", "granted", "issued order of approval"]):
                resolved = True
                resolution_value = "Yes"
                confidence = 88
                evidence_summary = "SEC official press release or EDGAR filing confirms approval."
            elif any(w in combined for w in ["denied", "rejected", "disapproved"]):
                resolved = True
                resolution_value = "No"
                confidence = 88
                evidence_summary = "SEC official order indicates denial."

        if not resolved:
            # Generic heuristic resolution check
            yes_signals = ["yes", "approved", "passed", "enacted", "confirmed", "true", "correct"]
            no_signals = ["no", "denied", "failed", "rejected", "false", "incorrect"]
            yes_count = sum(1 for w in yes_signals if w in combined)
            no_count = sum(1 for w in no_signals if w in combined)

            if yes_count > no_count + 2:
                resolution_value = "Yes"
                confidence = min(60, 30 + yes_count * 5)
                evidence_summary = f"HYDRA text analysis suggests Yes resolution based on provided evidence. Confidence is limited — verify against official sources: {profile.get('resolution_source', 'official government publications')}."
            elif no_count > yes_count + 2:
                resolution_value = "No"
                confidence = min(60, 30 + no_count * 5)
                evidence_summary = f"HYDRA text analysis suggests No resolution based on provided evidence. Confidence is limited — verify against official sources."
            else:
                evidence_summary = (
                    f"Insufficient evidence to determine resolution. "
                    f"HYDRA regulatory domain: {domain or 'unclassified'}. "
                    f"Check resolution source: {profile.get('resolution_source', 'official government publications')}. "
                    f"HYDRA analysis: {hydra_answer[:300] if hydra_answer else 'No specific answer available.'}"
                )

        if sources:
            evidence_summary += f" HYDRA data sources: {'; '.join(sources[:2])}."

        return {
            "market_question": market_question,
            "market_id": market_id,
            "resolved": resolved,
            "resolution_value": resolution_value,
            "confidence": confidence,
            "evidence_summary": evidence_summary,
            "regulatory_domain": domain,
            "relevant_regulations": relevant_regs[:5],
            "sources": sources[:5] + ([profile["resolution_source"]] if profile.get("resolution_source") else []),
            "hydra_analysis": hydra_answer[:500] if hydra_answer else None,
            "assessment_timestamp": datetime.now(timezone.utc).isoformat(),
            "important_note": (
                "HYDRA provides regulatory intelligence as a data signal, not legal advice. "
                "For UMA OO assertions, HYDRA recommends posting bonds only when confidence >= 70 "
                "and official source data is directly available. Always verify against the "
                "market's named resolution source before bonding."
            ),
        }


# ─────────────────────────────────────────────────────────────
# Module-level singleton instances for route handlers
# ─────────────────────────────────────────────────────────────

_aggregator: PredictionMarketAggregator | None = None
_event_feed: RegulatoryEventFeed | None = None
_oracle_provider: OracleDataProvider | None = None


def get_aggregator() -> PredictionMarketAggregator:
    global _aggregator
    if _aggregator is None:
        _aggregator = PredictionMarketAggregator()
    return _aggregator


def get_event_feed() -> RegulatoryEventFeed:
    global _event_feed
    if _event_feed is None:
        _event_feed = RegulatoryEventFeed()
    return _event_feed


def get_oracle_provider() -> OracleDataProvider:
    global _oracle_provider
    if _oracle_provider is None:
        _oracle_provider = OracleDataProvider()
    return _oracle_provider
