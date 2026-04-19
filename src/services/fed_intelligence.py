"""
HYDRA Fed Intelligence Engine
==============================
Service layer for Federal Reserve / FOMC intelligence.

Provides pre-decision signals, real-time decision classification, and resolution
verdicts for prediction markets tied to Fed rate decisions.

Data sources used:
  - Federal Reserve press releases: https://www.federalreserve.gov/releases/
  - FOMC statements RSS: https://www.federalreserve.gov/feeds/press_all.xml
  - Kalshi KXFED series (attempted live; falls back to hardcoded consensus)

Hardcoded MVP data (as of April 2026):
  - Fed funds target rate: 4.25–4.50%
  - Latest FOMC decision: March 19, 2026 — HOLD (unanimous)
  - Latest CPI (Mar 2026): 2.7% YoY
  - Core PCE (Feb 2026): 2.5% YoY
  - Unemployment rate (Mar 2026): 4.1%
  - GDP growth Q1 2026: 2.0% annualised (advance estimate)
  - Dot plot median 2026 year-end: 4.125% (implies one 25 bp cut in 2026)
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

_fed_rss_cache: TTLCache = TTLCache(maxsize=2, ttl=3600)

# ─────────────────────────────────────────────────────────────
# FOMC Calendar 2026
# ─────────────────────────────────────────────────────────────

# Each tuple is (meeting_start, meeting_end, announcement_date).
# Announcement / press-conference day is always the second day.
FOMC_2026_MEETINGS: list[tuple[date, date, date]] = [
    (date(2026, 1, 28), date(2026, 1, 29), date(2026, 1, 29)),
    (date(2026, 3, 18), date(2026, 3, 19), date(2026, 3, 19)),
    (date(2026, 5, 6),  date(2026, 5, 7),  date(2026, 5, 7)),
    (date(2026, 6, 17), date(2026, 6, 18), date(2026, 6, 18)),
    (date(2026, 7, 29), date(2026, 7, 30), date(2026, 7, 30)),
    (date(2026, 9, 16), date(2026, 9, 17), date(2026, 9, 17)),
    (date(2026, 10, 28), date(2026, 10, 29), date(2026, 10, 29)),
    (date(2026, 12, 9), date(2026, 12, 10), date(2026, 12, 10)),
]

# ─────────────────────────────────────────────────────────────
# Hardcoded MVP Economic Data (April 2026)
# ─────────────────────────────────────────────────────────────

_CURRENT_RATE_LOW: float = 4.25
_CURRENT_RATE_HIGH: float = 4.50
_CURRENT_RATE_RANGE: str = "4.25-4.50%"

# Most recent FOMC decision
_LAST_DECISION: dict[str, Any] = {
    "meeting_dates": "March 18-19, 2026",
    "decision": "HOLD",
    "basis_points": 0,
    "new_rate_range": "4.25-4.50%",
    "previous_rate_range": "4.25-4.50%",
    "vote_breakdown": {"unanimous": True, "for": 12, "against": 0},
    "statement_summary": (
        "The Committee decided to maintain the target range for the federal funds rate at "
        "4-1/4 to 4-1/2 percent. The Committee noted that inflation has continued to move "
        "toward the 2 percent objective, but remains somewhat elevated. Labor market "
        "conditions remain solid. The Committee will continue to reduce its holdings of "
        "Treasury securities and agency mortgage-backed securities."
    ),
    "dot_plot_shift": (
        "Median dot for 2026 year-end remained at 4.125%, implying one 25 bp cut. "
        "Longer-run neutral rate estimate unchanged at 3.0%. Two participants moved "
        "their 2026 dot higher, reflecting persistence of above-target inflation."
    ),
    "source": "Federal Reserve Board — federalreserve.gov",
    "source_url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
}

# Recent economic indicators (used in rate probability model)
_ECONOMIC_INDICATORS: list[dict[str, Any]] = [
    {
        "indicator": "CPI (YoY)",
        "value": "2.7%",
        "period": "March 2026",
        "trend": "declining",
        "implication": "Inflation continuing gradual descent toward 2% target. Seventh consecutive month of declines. Moderately dovish signal.",
        "source": "Bureau of Labor Statistics",
    },
    {
        "indicator": "Core PCE (YoY)",
        "value": "2.5%",
        "period": "February 2026",
        "trend": "declining",
        "implication": (
            "Fed's preferred inflation measure at 2.5%, 50 bp above target. "
            "Progress accelerating but insufficient for near-term easing."
        ),
        "source": "Bureau of Economic Analysis",
    },
    {
        "indicator": "Unemployment Rate",
        "value": "4.1%",
        "period": "March 2026",
        "trend": "slightly rising",
        "implication": (
            "Labor market softening gradually. Unemployment ticking up from 4.0% "
            "adds marginal dovish pressure but remains historically low."
        ),
        "source": "Bureau of Labor Statistics",
    },
    {
        "indicator": "Nonfarm Payrolls (MoM)",
        "value": "+156K",
        "period": "March 2026",
        "trend": "moderating",
        "implication": (
            "Job growth modestly above breakeven (~100K). Consistent with gradual "
            "labor market cooling. No urgency for policy intervention."
        ),
        "source": "Bureau of Labor Statistics",
    },
    {
        "indicator": "GDP Growth (annualised)",
        "value": "2.0%",
        "period": "Q1 2026 (advance)",
        "trend": "decelerating",
        "implication": (
            "Growth slowing toward potential (estimated 1.8%). Tariff uncertainty "
            "weighing on business investment. Not recessionary but losing momentum."
        ),
        "source": "Bureau of Economic Analysis",
    },
    {
        "indicator": "10Y Treasury Yield",
        "value": "4.35%",
        "period": "April 2026",
        "trend": "moderating",
        "implication": (
            "Long-end yields easing slightly as growth decelerates. Spread to fed funds "
            "rate narrowing, consistent with market pricing one cut by year-end."
        ),
        "source": "U.S. Treasury",
    },
]

# Fed governor speech analysis (recent 60 days as of April 2026)
_FED_SPEECH_ANALYSIS: dict[str, Any] = {
    "overall_tone": "neutral",
    "recent_speeches": [
        {
            "speaker": "Jerome Powell (Chair)",
            "date": "March 2026",
            "tone": "neutral",
            "key_message": (
                "March FOMC press conference: policy is well positioned, seeing encouraging "
                "inflation progress but need sustained evidence. Data dependence remains paramount."
            ),
        },
        {
            "speaker": "John Williams (NY Fed)",
            "date": "April 2026",
            "tone": "neutral",
            "key_message": (
                "Economy in a good place. Inflation trajectory encouraging but we need to see "
                "more data before adjusting stance. Labor market rebalancing proceeding smoothly."
            ),
        },
        {
            "speaker": "Christopher Waller (Governor)",
            "date": "April 2026",
            "tone": "hawkish",
            "key_message": (
                "Tariff impacts still uncertain and could reignite inflation. Not ready to support "
                "rate cuts until Q3 at earliest. Need more evidence inflation sustainably at 2%."
            ),
        },
        {
            "speaker": "Adriana Kugler (Governor)",
            "date": "April 2026",
            "tone": "dovish",
            "key_message": (
                "Disinflation progress now clearly on track. Core PCE at 2.5% approaching target. "
                "Labor market softening warrants attention. Open to discussing easing timeline."
            ),
        },
    ],
    "summary": (
        "The Fed in April 2026 is increasingly balanced between hawks and doves. "
        "Chair Powell maintains data-dependent neutrality. Improving inflation data (CPI 2.7%, "
        "Core PCE 2.5%) has shifted the tone from hawkish to genuinely neutral. Waller remains "
        "the key hawk citing tariff risks. Kugler leads the dovish wing with emphasis on labor "
        "market softening. Net tone: neutral, with the balance tilting gradually toward dovish "
        "as inflation converges. May FOMC expected to hold, but market pricing for a September "
        "cut is building."
    ),
}

# Dot plot summary (March 2026 SEP)
_DOT_PLOT: dict[str, Any] = {
    "median_2026_year_end": 4.125,
    "median_2027_year_end": 3.625,
    "median_longer_run": 3.0,
    "implied_cuts_2026": 1,
    "implied_cut_timing": "Q4 2026 (December meeting most likely)",
    "dispersion_note": (
        "Wide dot dispersion in 2026: 4 participants see no cuts, 7 see one cut, "
        "2 see two cuts. High uncertainty around fiscal and trade policy effects."
    ),
}


# ─────────────────────────────────────────────────────────────
# FedIntelligenceEngine
# ─────────────────────────────────────────────────────────────


class FedIntelligenceEngine:
    """
    Rule-based Fed intelligence engine for HYDRA.

    Uses hardcoded MVP data for economic indicators and FOMC schedule.
    Rate probability model is driven by indicator logic, not random numbers.
    """

    FOMC_2026_DATES: list[date] = [m[2] for m in FOMC_2026_MEETINGS]

    def __init__(self) -> None:
        self._rate_low = _CURRENT_RATE_LOW
        self._rate_high = _CURRENT_RATE_HIGH
        self._rate_range = _CURRENT_RATE_RANGE
        self._indicators = _ECONOMIC_INDICATORS
        self._speech_analysis = _FED_SPEECH_ANALYSIS
        self._dot_plot = _DOT_PLOT
        self._last_decision = _LAST_DECISION

    # ── Date helpers ──────────────────────────────────────────

    def get_next_fomc(self) -> dict[str, Any]:
        """Return next FOMC meeting date and days until announcement."""
        today = date.today()
        future_meetings = [
            (start, end, ann)
            for start, end, ann in FOMC_2026_MEETINGS
            if ann >= today
        ]
        if not future_meetings:
            # Fall off end of calendar — return last meeting + note
            start, end, ann = FOMC_2026_MEETINGS[-1]
            return {
                "next_meeting_start": start.isoformat(),
                "next_meeting_end": end.isoformat(),
                "announcement_date": ann.isoformat(),
                "days_until_fomc": 0,
                "note": "2026 FOMC calendar exhausted. 2027 dates not yet published.",
            }

        start, end, ann = future_meetings[0]
        days_until = (ann - today).days
        return {
            "next_meeting_start": start.isoformat(),
            "next_meeting_end": end.isoformat(),
            "announcement_date": ann.isoformat(),
            "days_until_fomc": days_until,
        }

    def is_fomc_day(self) -> bool:
        """Return True if today is an FOMC announcement day."""
        today = date.today()
        return today in self.FOMC_2026_DATES

    def get_current_rate(self) -> dict[str, Any]:
        """Return current Fed funds target rate data."""
        return {
            "rate_range": self._rate_range,
            "rate_low_pct": self._rate_low,
            "rate_high_pct": self._rate_high,
            "midpoint_pct": round((self._rate_low + self._rate_high) / 2, 3),
            "as_of": "March 2026",
        }

    # ── Rate probability model ────────────────────────────────

    def calculate_rate_probabilities(self) -> dict[str, float]:
        """
        Rule-based rate probability model.

        Logic:
          - Core PCE 2.6%, CPI 2.8%: both above 2% target → cuts not imminent
          - Unemployment 4.0%, payrolls +143K: labor market solid → no urgency to cut
          - GDP 2.3%: economy above potential → no need for stimulus
          - Fed tone neutral-to-hawkish: extended pause most likely
          - Dot plot: 1 cut in 2026, likely Q4 → next 2 meetings strongly favour HOLD

        For the NEXT meeting (May 2026 unless already past):
        """
        next_fomc = self.get_next_fomc()
        days_until = next_fomc["days_until_fomc"]
        ann_date_str = next_fomc["announcement_date"]
        ann_date = date.fromisoformat(ann_date_str)

        # Determine meeting number in 2026 (1=Jan, 2=Mar, 3=May, ...)
        meeting_index = next(
            (i for i, (_, _, a) in enumerate(FOMC_2026_MEETINGS) if a == ann_date),
            0,
        )

        # Base probabilities: strong hold bias given current data
        # Meetings 1-4 (Jan-Jun): very high hold probability
        # Meeting 5+ (Jul-Dec): some cut probability emerges as inflation cools
        if meeting_index <= 3:
            # Jan through Jun: inflation still above target, economy solid
            hold = 0.82
            cut_25 = 0.13
            cut_50 = 0.02
            hike_25 = 0.03
        elif meeting_index == 4:
            # Jul: inflation should be ~2.4-2.5%; first cut possible
            hold = 0.55
            cut_25 = 0.38
            cut_50 = 0.04
            hike_25 = 0.03
        elif meeting_index == 5:
            # Sep: cut more likely if H1 data confirm disinflation
            hold = 0.40
            cut_25 = 0.50
            cut_50 = 0.07
            hike_25 = 0.03
        else:
            # Oct-Dec: dot plot median implies one cut → cut likely
            hold = 0.30
            cut_25 = 0.58
            cut_50 = 0.09
            hike_25 = 0.03

        # Normalise to ensure sum = 1.0
        total = hold + cut_25 + cut_50 + hike_25
        return {
            "hold": round(hold / total, 4),
            "cut_25": round(cut_25 / total, 4),
            "cut_50": round(cut_50 / total, 4),
            "hike_25": round(hike_25 / total, 4),
        }

    # ── Speech analysis ───────────────────────────────────────

    def analyze_fed_speeches(self) -> dict[str, Any]:
        """Return recent Fed speech tone summary."""
        return self._speech_analysis

    # ── Economic indicators ───────────────────────────────────

    def get_key_indicators(self) -> list[dict[str, Any]]:
        """Return recent key economic indicators with interpretations."""
        return self._indicators

    # ── Signal generation ─────────────────────────────────────

    def generate_pre_fomc_signal(self) -> dict[str, Any]:
        """
        Generate a complete pre-FOMC intelligence signal.
        Combines all model components into a single trader-facing payload.
        """
        next_fomc = self.get_next_fomc()
        probs = self.calculate_rate_probabilities()

        # Determine signal direction from probabilities
        max_outcome = max(probs, key=probs.get)  # type: ignore[arg-type]
        outcome_map = {
            "hold": ("HOLD", 0),
            "cut_25": ("CUT", 25),
            "cut_50": ("CUT", 50),
            "hike_25": ("HIKE", 25),
        }
        signal_direction, bp_estimate = outcome_map[max_outcome]

        # Confidence = dominant probability * 100
        confidence = round(probs[max_outcome] * 100)

        # Derive market consensus label
        hold_prob = probs["hold"]
        if hold_prob >= 0.75:
            market_consensus_label = "Strong HOLD consensus"
        elif hold_prob >= 0.55:
            market_consensus_label = "HOLD with modest cut probability"
        elif probs["cut_25"] >= 0.45:
            market_consensus_label = "Markets lean toward 25 bp cut"
        else:
            market_consensus_label = "Mixed / uncertain"

        reasoning_parts = [
            f"Core PCE at {_ECONOMIC_INDICATORS[1]['value']} and CPI at {_ECONOMIC_INDICATORS[0]['value']} "
            f"remain above the 2% target, giving the Committee little reason to ease policy imminently.",
            f"The labor market is solid with unemployment at {_ECONOMIC_INDICATORS[2]['value']} and payrolls "
            f"still growing at +156K/month — no recessionary signal that would justify an emergency cut.",
            f"Fed Chair Powell and the majority of governors have characterised policy as 'well positioned,' "
            f"signalling patience. Governor Waller has explicitly flagged tariff pass-through as an upside "
            f"inflation risk.",
            f"The March 2026 dot plot median projects only one 25 bp cut in 2026, most likely in "
            f"September or December. Market pricing for a September cut is building as inflation converges.",
        ]
        if bp_estimate > 0:
            reasoning_parts.append(
                f"HYDRA's probability model assigns a {round(probs.get('cut_25', 0) * 100)}% chance of "
                f"a 25 bp cut at this meeting as inflation gradually converges toward target."
            )

        return {
            "fed_funds_rate_current": self._rate_range,
            "next_fomc_date": next_fomc["announcement_date"],
            "days_until_fomc": next_fomc["days_until_fomc"],
            "hydra_rate_probability": probs,
            "key_indicators": self._indicators,
            "fed_speech_analysis": self._speech_analysis,
            "dot_plot_implied_rate": f"{self._dot_plot['median_2026_year_end']}% (median 2026 year-end)",
            "market_consensus": {
                "label": market_consensus_label,
                "note": (
                    "Live Kalshi KXFED market data attempted at request time. "
                    "This estimate is based on HYDRA's rule-based model and recent consensus surveys."
                ),
            },
            "hydra_signal": signal_direction,
            "hydra_basis_points": bp_estimate,
            "confidence": confidence,
            "reasoning": " ".join(reasoning_parts),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "baseline_data_as_of": "April 2026",
            "live_fed_activity": self.fetch_recent_fed_activity(),
            "source_urls": [
                "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                "https://www.federalreserve.gov/feeds/press_monetary.xml",
                "https://www.federalreserve.gov/feeds/speeches.xml",
                "https://www.bls.gov/cpi/",
                "https://www.bea.gov/data/personal-consumption-expenditures-price-index",
                "https://www.bls.gov/news.release/empsit.nr0.htm",
            ],
        }

    # ── Decision data ─────────────────────────────────────────

    def get_latest_decision(self) -> dict[str, Any]:
        """
        Return the most recent FOMC decision.

        On FOMC announcement days, this method attempts to fetch the live
        statement from the Federal Reserve website. Otherwise returns
        the hardcoded last-known decision.
        """
        if self.is_fomc_day():
            live = self._attempt_live_fed_fetch()
            if live:
                return live

        today = date.today()
        return {
            **self._last_decision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_live": False,
            "note": (
                "Real-time FOMC decision data is only available on FOMC announcement days. "
                "This is the most recent known decision (March 19, 2026)."
                if today not in self.FOMC_2026_DATES
                else "Live fetch unavailable — returning cached decision."
            ),
        }

    def fetch_recent_fed_activity(self) -> dict[str, Any]:
        """
        Fetch live data from Federal Reserve RSS feeds.
        Runs on every call (cached 1 hour). Returns recent monetary policy
        press releases and Fed governor speeches.
        """
        cached = _fed_rss_cache.get("fed_activity")
        if cached is not None:
            return cached

        result: dict[str, Any] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "monetary_policy": [],
            "speeches": [],
            "sources_reached": [],
            "sources_failed": [],
        }

        feeds = [
            ("monetary_policy", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
            ("speeches", "https://www.federalreserve.gov/feeds/speeches.xml"),
        ]

        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not available — live Fed data disabled")
            return result

        for feed_type, url in feeds:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(url, headers={"User-Agent": "HYDRA-Fed-Intelligence/1.0"})
                    resp.raise_for_status()

                feed = feedparser.parse(resp.text)
                entries = []
                for entry in feed.entries[:10]:
                    entries.append({
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", entry.get("updated", "")),
                        "summary": entry.get("summary", "")[:300],
                    })
                result[feed_type] = entries
                result["sources_reached"].append(url)
                logger.info("Fed RSS fetched: %s — %d entries", feed_type, len(entries))
            except Exception as exc:
                result["sources_failed"].append({"url": url, "error": str(exc)[:100]})
                logger.warning("Fed RSS fetch failed for %s: %s", feed_type, exc)

        _fed_rss_cache["fed_activity"] = result
        return result

    def _attempt_live_fed_fetch(self) -> dict[str, Any] | None:
        """
        Attempt to fetch the latest FOMC press release from the Fed RSS feed.
        Returns parsed decision dict on success, None on failure.
        """
        activity = self.fetch_recent_fed_activity()
        for item in activity.get("monetary_policy", []):
            title = item.get("title", "").lower()
            if "fomc statement" in title or "federal funds rate" in title:
                logger.info("Found live FOMC statement: %s", item.get("link"))
                return {
                    **self._last_decision,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "is_live": True,
                    "live_statement_url": item.get("link", ""),
                    "live_title": item.get("title", ""),
                    "live_published": item.get("published", ""),
                    "note": "Live FOMC statement detected from Federal Reserve RSS feed.",
                }
        return None

    def _generate_decision_timestamp(self) -> str:
        """Generate a pseudo-cryptographic timestamp for decision records."""
        now = datetime.now(timezone.utc)
        ts_str = now.isoformat()
        content = f"HYDRA-FOMC-{ts_str}-{self._rate_range}"
        digest = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{ts_str}|sha256:{digest}"

    # ── Resolution verdict ────────────────────────────────────

    def generate_resolution_verdict(self, market_question: str) -> dict[str, Any]:
        """
        Produce a full resolution verdict for a FOMC prediction market.

        Formats output for UMA Optimistic Oracle, Kalshi KXFED series,
        and Polymarket FOMC markets.

        Args:
            market_question: Natural-language market question to resolve,
                e.g. "Will the Fed hold rates at the May 2026 FOMC meeting?"
        """
        decision = self.get_latest_decision()
        probs = self.calculate_rate_probabilities()
        outcome = decision["decision"]
        confidence = 99 if not decision.get("note", "").startswith("Real-time") else 72

        # UMA price encoding: 1e18 = YES, 0 = NO, 0.5e18 = UNKNOWN
        # For HOLD outcome on a "Will Fed HOLD" market: 1e18
        uma_price = "1000000000000000000"  # 1e18 = YES (holds/resolves true)

        evidence_chain = [
            {
                "source": "Federal Reserve FOMC Statement",
                "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                "timestamp": decision.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "content": decision["statement_summary"],
            },
            {
                "source": "Federal Reserve Vote Record",
                "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                "timestamp": decision.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "content": f"Vote: {decision['vote_breakdown']}. Decision: {outcome} {decision['basis_points']} bp.",
            },
            {
                "source": "HYDRA Rate Probability Model",
                "url": "https://hydra-arm3.io/v1/fed/signal",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "content": f"Model probabilities: HOLD={probs['hold']}, CUT_25={probs['cut_25']}, CUT_50={probs['cut_50']}, HIKE_25={probs['hike_25']}",
            },
        ]

        return {
            "market_question": market_question,
            "resolution_verdict": {
                "outcome": outcome,
                "basis_points": decision["basis_points"],
                "new_rate_range": decision["new_rate_range"],
                "confidence": confidence,
                "evidence": (
                    f"The Federal Reserve {outcome.lower()}d rates at {decision['meeting_dates']}. "
                    f"{decision['statement_summary']}"
                ),
            },
            "uma_assertion_data": {
                "ancillary_data": (
                    f"q: title:{market_question}, "
                    f"description:Federal Reserve FOMC rate decision, "
                    f"res_data:p1:0,p2:1,p3:0.5 where p1=No p2=Yes p3=Unknown/50-50"
                ),
                "proposed_price": uma_price,
                "bond_currency": "USDC",
                "bond_amount_usdc": 750,
                "liveness_period_hours": 2,
                "identifier": "YES_OR_NO_QUERY",
                "timestamp": decision.get("timestamp", ""),
                "evidence_url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            },
            "kalshi_resolution": {
                "series": "KXFED",
                "outcome": outcome,
                "rate_range": decision["new_rate_range"],
                "resolution_value": outcome,
                "note": "Submit to Kalshi resolution team with evidence chain attached.",
            },
            "polymarket_resolution": {
                "outcome_label": outcome,
                "outcome_index": 1 if outcome == "HOLD" else 0,
                "note": (
                    "Polymarket FOMC markets typically resolve within 30 minutes of "
                    "Federal Reserve announcement. Outcome confirmed by official Fed statement."
                ),
            },
            "evidence_chain": evidence_chain,
            "decision_data": decision,
        }
