"""
HYDRA Arm 3 — LLM Intelligence Layer
======================================
Provides AI-powered analysis via Claude API for regulatory intelligence,
Fed decision analysis, and prediction market signal generation.

The LLM layer is OPTIONAL — if ANTHROPIC_API_KEY is not set, all methods
fall back to the existing rule-based engine (keyword matching). This means
the system always works, but delivers dramatically better analysis with an
API key configured.

Cost model:
  - Claude Haiku: ~$0.25/1M input, ~$1.25/1M output tokens
  - Average regulatory scan: ~2K input + ~1K output = ~$0.002/call
  - At $2.00/call endpoint price, margin is 99.9%
  - At 1000 calls/day: ~$2/day LLM cost vs $2000/day revenue

Environment:
  ANTHROPIC_API_KEY — Required for LLM features. Without it, rule-based fallback.
  LLM_MODEL — Optional. Default: claude-haiku-4-5-20251001 (fast, cheap, good enough)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("hydra.llm")

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))

_client: Optional[Any] = None


def _get_client() -> Optional[Any]:
    """Lazy-init the Anthropic client. Returns None if no API key."""
    global _client
    if not ANTHROPIC_API_KEY:
        return None
    if _client is None:
        try:
            import anthropic
            _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            logger.info("Anthropic client initialised (model=%s)", LLM_MODEL)
        except ImportError:
            logger.warning("anthropic SDK not installed — LLM features disabled")
            return None
        except Exception as exc:
            logger.error("Failed to initialise Anthropic client: %s", exc)
            return None
    return _client


def is_llm_available() -> bool:
    """Check if LLM is configured and available."""
    return _get_client() is not None


def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 0) -> Optional[str]:
    """
    Make a single LLM call. Returns the text response or None on failure.
    Never raises — all errors are logged and return None for graceful fallback.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=max_tokens or LLM_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text if response.content else None
        if text:
            logger.debug("LLM response: %d chars (model=%s)", len(text), LLM_MODEL)
        return text
    except Exception as exc:
        logger.warning("LLM call failed (falling back to rule-based): %s", exc)
        return None


# ─────────────────────────────────────────────────────────────
# Regulatory Intelligence Prompts
# ─────────────────────────────────────────────────────────────

_REGULATORY_SYSTEM = """You are HYDRA, an expert US financial regulatory analyst. You provide
precise, actionable regulatory compliance analysis for businesses. You cite specific statutes,
CFR sections, and regulatory guidance. You identify exact registration requirements, filing
deadlines, and compliance gaps. You are direct and practical — no disclaimers or hedging.
Output structured JSON only."""


def analyze_regulatory_risk_llm(
    business_description: str,
    jurisdiction: str = "US",
) -> Optional[dict[str, Any]]:
    """
    Use Claude to analyze regulatory risk for a business.
    Returns structured analysis or None (caller falls back to rule-based).
    """
    prompt = f"""Analyze the regulatory compliance requirements for this business:

Business: {business_description}
Jurisdiction: {jurisdiction}

Return a JSON object with:
{{
  "overall_risk_score": <0-100 integer>,
  "overall_risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "applicable_regulations": [
    {{
      "name": "<regulation name>",
      "citation": "<specific statute/CFR cite>",
      "regulator": "<agency>",
      "relevance": "<why this applies>",
      "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
      "description": "<detailed explanation>",
      "recommended_actions": ["<specific action 1>", "<specific action 2>"]
    }}
  ],
  "key_compliance_gaps": ["<gap 1>", "<gap 2>"],
  "priority_actions": ["<action 1>", "<action 2>", "<action 3>"],
  "estimated_compliance_cost": "<range estimate>",
  "timeline_to_compliance": "<estimate>"
}}

Be specific. Cite actual statutes (15 U.S.C., 12 C.F.R., etc.). Include registration
requirements, filing deadlines, and exact regulatory bodies. Consider state-level requirements
for {jurisdiction}."""

    return _call_llm_json(_REGULATORY_SYSTEM, prompt)


def answer_regulatory_query_llm(question: str) -> Optional[dict[str, Any]]:
    """Use Claude to answer a regulatory question with citations."""
    prompt = f"""Answer this regulatory compliance question:

Question: {question}

Return a JSON object with:
{{
  "answer": "<detailed answer with statutory citations>",
  "confidence": <0.0-1.0>,
  "relevant_statutes": ["<statute 1>", "<statute 2>"],
  "relevant_agencies": ["<agency 1>"],
  "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "recommended_actions": ["<action 1>", "<action 2>"],
  "disclaimer": "This is regulatory intelligence, not legal advice."
}}

Cite specific US statutes, CFR sections, and regulatory guidance. Be precise and actionable."""

    return _call_llm_json(_REGULATORY_SYSTEM, prompt)


# ─────────────────────────────────────────────────────────────
# Fed Intelligence Prompts
# ─────────────────────────────────────────────────────────────

_FED_SYSTEM = """You are HYDRA's Federal Reserve intelligence engine. You analyze FOMC
decisions, economic indicators, and Fed communications to generate trading signals for
prediction market participants. You provide probability estimates, not certainties.
Output structured JSON only."""


def analyze_fed_signal_llm(
    current_rate: str,
    economic_data: dict[str, Any],
    recent_speeches: list[dict[str, Any]],
    next_meeting: str,
) -> Optional[dict[str, Any]]:
    """Use Claude to generate a pre-FOMC signal analysis."""
    prompt = f"""Generate a pre-FOMC trading signal based on this data:

Current Fed funds rate: {current_rate}
Next FOMC meeting: {next_meeting}

Economic indicators:
{_format_dict(economic_data)}

Recent Fed speeches:
{_format_list(recent_speeches)}

Return a JSON object with:
{{
  "rate_probabilities": {{
    "hold": <0.0-1.0>,
    "cut_25bp": <0.0-1.0>,
    "cut_50bp": <0.0-1.0>,
    "hike_25bp": <0.0-1.0>
  }},
  "signal_direction": "<HOLD|DOVISH|HAWKISH>",
  "confidence": <0.0-1.0>,
  "key_factors": ["<factor 1>", "<factor 2>", "<factor 3>"],
  "market_impact_assessment": "<brief assessment>",
  "risk_factors": ["<risk 1>", "<risk 2>"],
  "analysis": "<2-3 paragraph analysis of the Fed's likely path>"
}}

Base probabilities on actual economic data, Fed communication patterns, and historical
FOMC behavior. Be specific about which indicators support which outcome."""

    return _call_llm_json(_FED_SYSTEM, prompt, max_tokens=3000)


def generate_resolution_verdict_llm(
    market_question: str,
    evidence: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Use Claude to generate a resolution verdict for a prediction market."""
    prompt = f"""Generate a resolution verdict for this prediction market question:

Market question: {market_question}

Available evidence:
{_format_dict(evidence)}

Return a JSON object with:
{{
  "verdict": "<YES|NO|UNRESOLVABLE>",
  "confidence": <0.0-1.0>,
  "evidence_chain": [
    {{"source": "<source>", "fact": "<relevant fact>", "weight": "<HIGH|MEDIUM|LOW>"}}
  ],
  "reasoning": "<detailed reasoning>",
  "resolution_date": "<date or 'pending'>",
  "dissenting_considerations": ["<consideration 1>"]
}}

Be objective. Cite sources. Consider edge cases in market resolution criteria."""

    return _call_llm_json(_FED_SYSTEM, prompt, max_tokens=3000)


# ─────────────────────────────────────────────────────────────
# Prediction Market Signal Prompts
# ─────────────────────────────────────────────────────────────

_MARKETS_SYSTEM = """You are HYDRA's prediction market signal engine. You analyze regulatory
events and their impact on prediction markets. You combine real market data with regulatory
domain expertise to generate actionable trading signals. Output structured JSON only."""


def generate_market_signal_llm(
    market_data: dict[str, Any],
    regulatory_context: str,
    recent_events: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Use Claude to generate a market-specific trading signal."""
    prompt = f"""Generate a trading signal for this prediction market:

Market: {market_data.get('question', 'Unknown')}
Current price (YES): {market_data.get('yes_price', 'N/A')}
Volume: {market_data.get('volume', 'N/A')}
Platform: {market_data.get('platform', 'Unknown')}

Regulatory context: {regulatory_context}

Recent regulatory events:
{_format_list(recent_events)}

Return a JSON object with:
{{
  "signal_direction": "<BULLISH_YES|BULLISH_NO|NEUTRAL|AVOID>",
  "confidence": <0.0-1.0>,
  "hydra_probability": <0.0-1.0>,
  "edge_vs_market": <decimal, positive = opportunity>,
  "risk_factors": ["<risk 1>", "<risk 2>"],
  "key_drivers": ["<driver 1>", "<driver 2>"],
  "recommended_position_size": "<SMALL|MEDIUM|LARGE based on Kelly criterion>",
  "time_horizon": "<short/medium/long>",
  "analysis": "<brief analysis>"
}}

Compare your regulatory probability estimate against the current market price to identify edge."""

    return _call_llm_json(_MARKETS_SYSTEM, prompt)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _call_llm_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 0,
) -> Optional[dict[str, Any]]:
    """Call LLM and parse JSON response. Returns None on any failure."""
    import json

    text = _call_llm(system_prompt, user_prompt, max_tokens)
    if text is None:
        return None

    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned non-JSON response: %s (first 200 chars: %s)", exc, cleaned[:200])
        return None


def _format_dict(d: dict[str, Any]) -> str:
    """Format a dict for prompt injection."""
    lines = []
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"  {k}:")
            for k2, v2 in v.items():
                lines.append(f"    {k2}: {v2}")
        else:
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _format_list(items: list) -> str:
    """Format a list for prompt injection."""
    lines = []
    for i, item in enumerate(items, 1):
        if isinstance(item, dict):
            lines.append(f"  {i}. {item}")
        else:
            lines.append(f"  {i}. {item}")
    return "\n".join(lines) if lines else "  (none available)"
