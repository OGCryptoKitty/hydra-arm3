"""
revenue_optimizer.py — HYDRA Autonomous Revenue Optimizer
==========================================================
Analyzes API usage patterns, tracks endpoint performance,
and generates data-driven pricing recommendations.

Runs autonomously — no human involvement required.
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hydra.revenue_optimizer")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STATE_DIR = Path(os.getenv("HYDRA_STATE_DIR", os.getenv("HYDRA_BOOTSTRAP_DIR", "/tmp/hydra-data")))
TRANSACTION_LOG = _STATE_DIR / "transaction_log.jsonl"
REVENUE_REPORT_DIR = _STATE_DIR / "reports"
MARKETING_LOG = _STATE_DIR / "marketing_log.jsonl"

# Current pricing (USDC) — synced from config/settings.py PRICING dict
# Kept in sync so revenue_optimizer can reference prices without importing settings
# at module level (avoids circular imports in some test configurations).
CURRENT_PRICING = {
    # Utility tier ($0.001 - $0.005)
    "/v1/util/crypto/price": Decimal("0.001"),
    "/v1/util/crypto/balance": Decimal("0.001"),
    "/v1/util/gas": Decimal("0.001"),
    "/v1/util/tx": Decimal("0.001"),
    "/v1/tools/hash": Decimal("0.001"),
    "/v1/tools/encode": Decimal("0.001"),
    "/v1/tools/validate/json": Decimal("0.001"),
    "/v1/x402/route": Decimal("0.001"),
    "/v1/util/rss": Decimal("0.002"),
    "/v1/tools/validate/email": Decimal("0.002"),
    "/v1/check/headers": Decimal("0.003"),
    "/v1/convert/json2csv": Decimal("0.003"),
    "/v1/convert/csv2json": Decimal("0.003"),
    "/v1/tools/diff": Decimal("0.003"),
    "/v1/util/scrape": Decimal("0.005"),
    "/v1/check/url": Decimal("0.005"),
    "/v1/check/dns": Decimal("0.005"),
    "/v1/check/ssl": Decimal("0.005"),
    "/v1/convert/html2md": Decimal("0.005"),
    "/v1/x402/status": Decimal("0.005"),
    # Mid tier ($0.01 - $0.10)
    "/v1/batch": Decimal("0.01"),
    "/v1/extract/url": Decimal("0.01"),
    "/v1/data/wikipedia": Decimal("0.01"),
    "/v1/extract/search": Decimal("0.02"),
    "/v1/data/arxiv": Decimal("0.02"),
    "/v1/data/edgar": Decimal("0.02"),
    "/v1/extract/multi": Decimal("0.05"),
    "/v1/alerts/feed": Decimal("0.05"),
    "/v1/orchestrate": Decimal("0.05"),
    "/v1/markets/feed": Decimal("0.10"),
    "/v1/alerts/subscribe": Decimal("0.10"),
    # Intelligence tier ($0.25 - $1.00)
    "/v1/intelligence/bank-failures": Decimal("0.25"),
    "/v1/markets/events": Decimal("0.50"),
    "/v1/intelligence/pulse": Decimal("0.50"),
    "/v1/intelligence/economic-snapshot": Decimal("0.50"),
    "/v1/intelligence/regulatory-pulse-live": Decimal("0.50"),
    "/v1/regulatory/changes": Decimal("1.00"),
    "/v1/regulatory/query": Decimal("1.00"),
    "/v1/intelligence/digest": Decimal("1.00"),
    # Signal tier ($2.00 - $5.00)
    "/v1/markets/signal/{market_id}": Decimal("2.00"),
    "/v1/regulatory/scan": Decimal("2.00"),
    "/v1/intelligence/risk-score": Decimal("2.00"),
    "/v1/portfolio/watchlist": Decimal("2.00"),
    "/v1/regulatory/jurisdiction": Decimal("3.00"),
    "/v1/portfolio/market-brief": Decimal("3.00"),
    "/v1/fed/signal": Decimal("5.00"),
    "/v1/markets/signals": Decimal("5.00"),
    "/v1/oracle/uma": Decimal("5.00"),
    "/v1/oracle/chainlink": Decimal("5.00"),
    "/v1/intelligence/alpha": Decimal("5.00"),
    # Premium tier ($10.00 - $50.00)
    "/v1/markets/alpha": Decimal("10.00"),
    "/v1/portfolio/scan": Decimal("10.00"),
    "/v1/markets/resolution": Decimal("25.00"),
    "/v1/fed/decision": Decimal("25.00"),
    "/v1/fed/resolution": Decimal("50.00"),
}

# High-value endpoint categories
HIGH_VALUE_ENDPOINTS = {
    "/v1/fed/decision", "/v1/fed/resolution", "/v1/markets/alpha",
    "/v1/markets/resolution", "/v1/portfolio/scan",
}
SIGNAL_ENDPOINTS = {
    "/v1/markets/signals", "/v1/markets/signal/{market_id}", "/v1/markets/feed",
    "/v1/markets/events",
}
UTILITY_ENDPOINTS = {
    "/v1/util/scrape", "/v1/util/crypto/price", "/v1/util/rss",
    "/v1/util/crypto/balance", "/v1/util/gas", "/v1/util/tx", "/v1/batch",
    "/v1/tools/hash", "/v1/tools/encode", "/v1/tools/diff",
    "/v1/tools/validate/json", "/v1/tools/validate/email",
    "/v1/check/url", "/v1/check/dns", "/v1/check/ssl", "/v1/check/headers",
    "/v1/convert/html2md", "/v1/convert/json2csv", "/v1/convert/csv2json",
    "/v1/extract/url", "/v1/extract/multi", "/v1/extract/search",
    "/v1/data/wikipedia", "/v1/data/arxiv", "/v1/data/edgar",
}
ORACLE_ENDPOINTS = {"/v1/oracle/uma", "/v1/oracle/chainlink", "/v1/markets/resolution"}
INTELLIGENCE_ENDPOINTS = {
    "/v1/intelligence/pulse", "/v1/intelligence/alpha",
    "/v1/intelligence/risk-score", "/v1/intelligence/digest",
    "/v1/intelligence/economic-snapshot", "/v1/intelligence/regulatory-pulse-live",
    "/v1/intelligence/bank-failures",
}
PORTFOLIO_ENDPOINTS = {
    "/v1/portfolio/scan", "/v1/portfolio/watchlist", "/v1/portfolio/market-brief",
}
ECOSYSTEM_ENDPOINTS = {"/v1/x402/status", "/v1/x402/route"}
ALERT_ENDPOINTS = {"/v1/alerts/subscribe", "/v1/alerts/feed"}


# ---------------------------------------------------------------------------
# RevenueOptimizer
# ---------------------------------------------------------------------------


class RevenueOptimizer:
    """
    Autonomous revenue analytics and optimization engine.

    Reads the transaction log, computes per-endpoint metrics,
    and generates actionable pricing and expansion recommendations.
    """

    def __init__(self) -> None:
        REVENUE_REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Method 1: analyze_endpoint_performance()
    # ------------------------------------------------------------------

    def analyze_endpoint_performance(self) -> Dict[str, Any]:
        """
        Read transaction_log.jsonl and compute revenue metrics per endpoint.

        Returns
        -------
        dict with keys:
          - total_revenue_usdc: total inbound revenue
          - by_endpoint: {endpoint: {calls, revenue, avg_revenue, revenue_share}}
          - top_callers: list of top wallet addresses by spend
          - revenue_by_day: daily revenue breakdown
          - highest_value_endpoints: ranked by total revenue
        """
        transactions = self._load_transactions()

        if not transactions:
            logger.info("No transactions found in log — returning empty analysis")
            return self._empty_analysis()

        # Aggregate by endpoint
        endpoint_calls: Dict[str, int] = defaultdict(int)
        endpoint_revenue: Dict[str, Decimal] = defaultdict(Decimal)
        caller_spend: Dict[str, Decimal] = defaultdict(Decimal)
        daily_revenue: Dict[str, Decimal] = defaultdict(Decimal)

        total_revenue = Decimal("0")

        for tx in transactions:
            if tx.get("direction") != "inbound":
                continue

            endpoint = tx.get("endpoint", "unknown")
            amount_str = tx.get("amount_usdc", "0")
            try:
                amount = Decimal(str(amount_str))
            except Exception:
                amount = Decimal("0")

            caller = tx.get("payer_address", "unknown")
            timestamp = tx.get("timestamp", "")

            endpoint_calls[endpoint] += 1
            endpoint_revenue[endpoint] += amount
            caller_spend[caller] += amount
            total_revenue += amount

            # Daily bucketing
            if timestamp:
                try:
                    day = timestamp[:10]  # YYYY-MM-DD
                    daily_revenue[day] += amount
                except Exception:
                    pass

        # Compute revenue shares
        by_endpoint: Dict[str, Any] = {}
        for endpoint in set(list(endpoint_calls.keys()) + list(endpoint_revenue.keys())):
            calls = endpoint_calls[endpoint]
            rev = endpoint_revenue[endpoint]
            share = float(rev / total_revenue * 100) if total_revenue > 0 else 0.0
            by_endpoint[endpoint] = {
                "calls": calls,
                "revenue_usdc": float(rev),
                "avg_revenue_usdc": float(rev / calls) if calls > 0 else 0.0,
                "revenue_share_pct": round(share, 2),
            }

        # Top callers
        top_callers = sorted(
            [{"address": addr, "total_spend_usdc": float(spend)} for addr, spend in caller_spend.items()],
            key=lambda x: x["total_spend_usdc"],
            reverse=True,
        )[:10]

        # Ranked endpoints
        ranked_endpoints = sorted(
            [{"endpoint": ep, **data} for ep, data in by_endpoint.items()],
            key=lambda x: x["revenue_usdc"],
            reverse=True,
        )

        return {
            "total_revenue_usdc": float(total_revenue),
            "total_calls": sum(endpoint_calls.values()),
            "by_endpoint": by_endpoint,
            "ranked_endpoints": ranked_endpoints,
            "top_callers": top_callers,
            "revenue_by_day": {day: float(rev) for day, rev in sorted(daily_revenue.items())},
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Method 2: generate_pricing_recommendation()
    # ------------------------------------------------------------------

    def generate_pricing_recommendation(self) -> Dict[str, Any]:
        """
        Based on usage patterns, suggest optimal pricing.

        Strategy:
          - High-call, low-revenue endpoints: consider price increase
          - Zero-call endpoints: consider price reduction as trial incentive
          - High-value endpoints with repeat callers: suggest bundle pricing
          - Low conversion on free endpoints: suggest lowering first paid tier
        """
        performance = self.analyze_endpoint_performance()

        if performance["total_revenue_usdc"] == 0:
            return self._cold_start_pricing_recommendations()

        by_endpoint = performance["by_endpoint"]
        recommendations: List[Dict[str, Any]] = []

        for endpoint, data in by_endpoint.items():
            current_price = CURRENT_PRICING.get(endpoint, Decimal("0"))
            calls = data["calls"]
            revenue = Decimal(str(data["revenue_usdc"]))

            if calls == 0:
                # No calls — reduce price or add free trial
                rec = {
                    "endpoint": endpoint,
                    "action": "reduce_price",
                    "current_price_usdc": float(current_price),
                    "suggested_price_usdc": float(current_price * Decimal("0.5")),
                    "reasoning": "Zero calls — reduce price to drive initial adoption",
                    "priority": "high" if current_price >= Decimal("1.00") else "medium",
                }
                recommendations.append(rec)

            elif calls > 50 and current_price < Decimal("1.00"):
                # High call volume at low price — test price increase
                suggested = current_price * Decimal("1.5")
                rec = {
                    "endpoint": endpoint,
                    "action": "increase_price",
                    "current_price_usdc": float(current_price),
                    "suggested_price_usdc": float(suggested),
                    "reasoning": f"High call volume ({calls} calls) suggests price-inelastic demand",
                    "priority": "medium",
                    "expected_revenue_delta_pct": 30,
                }
                recommendations.append(rec)

        # Bundle recommendation if signal endpoints are heavily used
        signal_calls = sum(
            by_endpoint.get(ep, {}).get("calls", 0) for ep in SIGNAL_ENDPOINTS
        )
        if signal_calls > 20:
            recommendations.append({
                "endpoint": "bundle:signals_subscription",
                "action": "create_bundle",
                "suggested_price_usdc": 10.00,
                "description": "Daily signal bundle — unlimited signal calls for 24h ($10 USDC)",
                "reasoning": f"{signal_calls} signal calls suggest subscription-ready demand",
                "priority": "high",
            })

        # Oracle bundle
        oracle_calls = sum(
            by_endpoint.get(ep, {}).get("calls", 0) for ep in ORACLE_ENDPOINTS
        )
        if oracle_calls > 5:
            recommendations.append({
                "endpoint": "bundle:oracle_package",
                "action": "create_bundle",
                "suggested_price_usdc": 5.00,
                "description": "Oracle verification bundle — UMA + Chainlink + Resolution ($5 USDC)",
                "reasoning": f"{oracle_calls} oracle calls suggest bundling opportunity",
                "priority": "medium",
            })

        return {
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "current_total_revenue_usdc": performance["total_revenue_usdc"],
            "recommendations": recommendations,
            "recommendation_count": len(recommendations),
        }

    # ------------------------------------------------------------------
    # Method 3: identify_expansion_opportunities()
    # ------------------------------------------------------------------

    def identify_expansion_opportunities(self) -> Dict[str, Any]:
        """
        Identify which new endpoints would maximize revenue based on
        current prediction market activity and usage patterns.

        Scans:
          - High-volume free endpoint usage (signals missing paid context)
          - Prediction market categories not covered
          - New regulatory domains gaining traction
        """
        performance = self.analyze_endpoint_performance()

        opportunities: List[Dict[str, Any]] = []

        # Opportunity 1: Portfolio tracking endpoint
        # Users calling signal endpoint repeatedly likely have positions
        opportunities.append({
            "opportunity": "Portfolio Signal Subscription",
            "description": (
                "Endpoint: POST /v1/portfolio/signals\n"
                "User provides list of market IDs, HYDRA returns signals for all.\n"
                "Price: $0.50 USDC (vs $0.10 * N for individual calls)"
            ),
            "target_users": "prediction market traders with 5+ active positions",
            "estimated_revenue_lift": "2x signal endpoint revenue",
            "implementation_effort": "low",
            "priority": "high",
        })

        # Opportunity 2: Webhook subscription
        opportunities.append({
            "opportunity": "Regulatory Event Webhooks",
            "description": (
                "Endpoint: POST /v1/subscribe/webhooks\n"
                "User provides webhook URL + agency filter.\n"
                "HYDRA pushes real-time regulatory events.\n"
                "Price: $5 USDC/month setup + $0.01/event delivered"
            ),
            "target_users": "compliance automation bots that poll /v1/markets/events",
            "estimated_revenue_lift": "recurring revenue stream",
            "implementation_effort": "medium",
            "priority": "high",
        })

        # Opportunity 3: Congressional activity
        opportunities.append({
            "opportunity": "Congressional Prediction Market Signals",
            "description": (
                "Endpoint: POST /v1/markets/congressional\n"
                "Signals for prediction markets around congressional votes,\n"
                "legislation passage, and committee actions.\n"
                "Price: $0.25 USDC"
            ),
            "target_users": "political prediction market traders on Kalshi",
            "estimated_revenue_lift": "new market category",
            "implementation_effort": "medium",
            "priority": "medium",
        })

        # Opportunity 4: Pre-FOMC daily briefing
        opportunities.append({
            "opportunity": "Daily Fed Briefing (Subscription Tier)",
            "description": (
                "Endpoint: GET /v1/fed/daily-brief\n"
                "Automated daily email/webhook with Fed intelligence summary.\n"
                "Price: $25 USDC/month"
            ),
            "target_users": "traders who call /v1/fed/signal before each FOMC",
            "estimated_revenue_lift": "converts high-value one-time to recurring",
            "implementation_effort": "low",
            "priority": "high",
        })

        # Opportunity 5: Crypto regulation tracker
        opportunities.append({
            "opportunity": "Crypto Regulatory Pipeline Tracker",
            "description": (
                "Endpoint: GET /v1/regulatory/crypto-pipeline\n"
                "Real-time tracking of crypto-specific legislation,\n"
                "SEC rulemaking, and CFTC enforcement trends.\n"
                "Price: $1.00 USDC"
            ),
            "target_users": "DeFi protocols and crypto compliance teams",
            "estimated_revenue_lift": "high TAM, $1 price point drives volume",
            "implementation_effort": "low",
            "priority": "high",
        })

        return {
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "current_revenue_baseline_usdc": performance["total_revenue_usdc"],
            "opportunities": opportunities,
            "total_opportunities": len(opportunities),
            "top_priority_count": sum(1 for o in opportunities if o["priority"] == "high"),
        }

    # ------------------------------------------------------------------
    # Method 4: generate_weekly_report()
    # ------------------------------------------------------------------

    def generate_weekly_report(self) -> str:
        """
        Generate a markdown revenue report for the past 7 days.
        Saves to $HYDRA_STATE_DIR/reports/weekly_{date}.md

        Returns the report content as a string.
        """
        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=7)

        performance = self.analyze_endpoint_performance()
        pricing_recs = self.generate_pricing_recommendation()
        expansion = self.identify_expansion_opportunities()

        # Filter to last 7 days
        weekly_revenue = sum(
            rev for day, rev in performance.get("revenue_by_day", {}).items()
            if day >= week_start.strftime("%Y-%m-%d")
        )

        ranked = performance.get("ranked_endpoints", [])
        top_endpoints = ranked[:5]
        top_callers = performance.get("top_callers", [])[:3]

        # Build report
        report_lines = [
            f"# HYDRA Revenue Report — Week of {week_start.strftime('%Y-%m-%d')}",
            "",
            f"**Generated:** {now.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Weekly Revenue | ${weekly_revenue:.2f} USDC |",
            f"| Total Lifetime Revenue | ${performance['total_revenue_usdc']:.2f} USDC |",
            f"| Total API Calls (lifetime) | {performance['total_calls']:,} |",
            f"| Active Endpoints | {len(performance.get('by_endpoint', {}))} |",
            f"| Unique Callers (lifetime) | {len(top_callers)} |",
            "",
            "---",
            "",
            "## Top Endpoints by Revenue",
            "",
            "| Endpoint | Calls | Revenue (USDC) | Share |",
            "|----------|-------|----------------|-------|",
        ]

        for ep in top_endpoints:
            report_lines.append(
                f"| `{ep['endpoint']}` | {ep['calls']} | "
                f"${ep['revenue_usdc']:.2f} | {ep['revenue_share_pct']:.1f}% |"
            )

        report_lines += [
            "",
            "---",
            "",
            "## Top Callers",
            "",
            "| Wallet | Lifetime Spend (USDC) |",
            "|--------|-----------------------|",
        ]

        for caller in top_callers:
            addr = caller["address"]
            short_addr = f"{addr[:6]}...{addr[-4:]}" if len(addr) > 12 else addr
            report_lines.append(
                f"| `{short_addr}` | ${caller['total_spend_usdc']:.2f} |"
            )

        report_lines += [
            "",
            "---",
            "",
            "## Pricing Recommendations",
            "",
        ]

        recs = pricing_recs.get("recommendations", [])
        if recs:
            for rec in recs[:5]:
                action = rec.get("action", "").replace("_", " ").title()
                endpoint = rec.get("endpoint", "")
                reasoning = rec.get("reasoning", "")
                priority = rec.get("priority", "medium")
                report_lines.append(
                    f"- **[{priority.upper()}]** `{endpoint}` — {action}: {reasoning}"
                )
        else:
            report_lines.append("No pricing changes recommended at this time.")

        report_lines += [
            "",
            "---",
            "",
            "## Expansion Opportunities",
            "",
        ]

        for opp in expansion.get("opportunities", [])[:3]:
            report_lines += [
                f"### {opp['opportunity']} [{opp['priority'].upper()}]",
                "",
                opp["description"],
                "",
                f"**Target users:** {opp['target_users']}",
                f"**Revenue lift:** {opp['estimated_revenue_lift']}",
                f"**Effort:** {opp['implementation_effort']}",
                "",
            ]

        report_lines += [
            "---",
            "",
            f"*Report generated autonomously by HYDRA RevenueOptimizer at {now.isoformat()}*",
        ]

        report_content = "\n".join(report_lines)

        # Save report
        report_filename = REVENUE_REPORT_DIR / f"weekly_{now.strftime('%Y%m%d')}.md"
        try:
            REVENUE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            report_filename.write_text(report_content, encoding="utf-8")
            logger.info("Weekly report saved to %s", report_filename)
        except OSError as exc:
            logger.error("Failed to save weekly report: %s", exc)

        return report_content

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_transactions(self) -> List[Dict[str, Any]]:
        """Load all transactions from the transaction log."""
        if not TRANSACTION_LOG.exists():
            return []

        transactions = []
        with TRANSACTION_LOG.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    transactions.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        return transactions

    def _empty_analysis(self) -> Dict[str, Any]:
        """Return empty analysis structure when no transactions exist."""
        return {
            "total_revenue_usdc": 0.0,
            "total_calls": 0,
            "by_endpoint": {},
            "ranked_endpoints": [],
            "top_callers": [],
            "revenue_by_day": {},
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "No transactions found in log",
        }

    def _cold_start_pricing_recommendations(self) -> Dict[str, Any]:
        """
        Pricing recommendations for cold-start (no usage data yet).

        Revenue = $0.  The bottleneck is discovery + first-call friction.
        Recommendations target:
          1. Getting the first agent to complete a paid call at all
          2. Making utility endpoints ultra-low-friction on-ramps
          3. Demonstrating value via free sample responses in 402 bodies
          4. Bundle pricing to reduce per-call payment friction
        """
        return {
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "current_total_revenue_usdc": 0.0,
            "cold_start_strategy": (
                "HYDRA has 55+ endpoints and $0 revenue.  The bottleneck is not pricing — "
                "it is distribution.  No agents have discovered HYDRA yet.  "
                "Priority 1: get listed on every x402 directory, MCP registry, and agent hub.  "
                "Priority 2: ensure 402 responses include sample data so agents see value before paying.  "
                "Priority 3: keep utility endpoints at $0.001-$0.005 as low-friction on-ramps."
            ),
            "recommendations": [
                {
                    "endpoint": "utility_tier",
                    "action": "maintain_low_prices",
                    "endpoints": list(UTILITY_ENDPOINTS),
                    "current_price_range_usdc": "0.001 - 0.02",
                    "reasoning": (
                        "Utility endpoints ($0.001-$0.02) are the on-ramp.  "
                        "An agent that pays $0.001 for a gas price lookup proves the x402 flow works, "
                        "then upgrades to $0.50+ intelligence endpoints.  Do not raise these prices."
                    ),
                    "priority": "high",
                },
                {
                    "endpoint": "intelligence_tier",
                    "action": "verify_sample_responses",
                    "endpoints": list(INTELLIGENCE_ENDPOINTS),
                    "current_price_range_usdc": "0.25 - 5.00",
                    "reasoning": (
                        "Intelligence endpoints are unique products.  Ensure every 402 response "
                        "includes a truncated sample so agents can evaluate quality before paying."
                    ),
                    "priority": "high",
                },
                {
                    "endpoint": "/v1/intelligence/economic-snapshot",
                    "action": "promote_as_flagship",
                    "current_price_usdc": 0.50,
                    "reasoning": (
                        "Atomic economic data from FRED/BLS/Treasury in one call.  "
                        "No other x402 service offers this.  Feature prominently in llms.txt and agents.json."
                    ),
                    "priority": "high",
                },
                {
                    "endpoint": "/v1/intelligence/bank-failures",
                    "action": "promote_as_flagship",
                    "current_price_usdc": 0.25,
                    "reasoning": (
                        "FDIC bank failure data is directly actionable for prediction market traders.  "
                        "At $0.25, this is cheaper than any alternative and drives conversion to "
                        "the $10 portfolio scan and $25 resolution endpoints."
                    ),
                    "priority": "high",
                },
                {
                    "endpoint": "all_paid_endpoints",
                    "action": "create_trial_package",
                    "suggested_price_usdc": 1.00,
                    "description": "Bootstrap trial: $1 USDC for access to all endpoints for 1 hour",
                    "reasoning": "Remove adoption friction by bundling discovery into one payment",
                    "priority": "medium",
                },
                {
                    "endpoint": "premium_tier",
                    "action": "keep_premium_pricing",
                    "endpoints": list(HIGH_VALUE_ENDPOINTS),
                    "current_price_range_usdc": "10.00 - 50.00",
                    "reasoning": (
                        "Fed resolution ($50), FOMC decision ($25), alpha reports ($10) are "
                        "correctly priced for the value delivered.  A $10 alpha report for a $10K "
                        "position is 0.1% cost.  Do not reduce — premium pricing signals quality."
                    ),
                    "priority": "low",
                },
            ],
            "recommendation_count": 6,
            "distribution_actions": [
                "Register on x402scan.com, x402list.fun, the402.ai, x402-list.com",
                "Submit to Glama, Smithery, and other MCP directories",
                "Ensure /.well-known/x402.json, agents.json, mcp.json, llms.txt are all serving",
                "Post to Dev.to and Hacker News about x402-native regulatory intelligence",
                "Add HYDRA to APIs.guru, public-apis, and RapidAPI directories",
            ],
        }
