"""
HYDRA Arm 3 — Regulatory Feed Aggregator

Fetches and caches regulatory news, press releases, and rulemaking notices
from SEC, CFTC, FinCEN, OCC, and CFPB official feeds.

Sources:
  SEC  : https://www.sec.gov/news/pressreleases.rss (press releases)
         https://www.sec.gov/rss/litigation/litreleases.xml (enforcement)
         https://www.sec.gov/rss/rules/proposed.xml (proposed rules)
         https://www.sec.gov/rss/rules/final.xml (final rules)
  CFTC : https://www.cftc.gov/rss/pressreleases.xml
  FinCEN: https://www.fincen.gov/rss.xml
  OCC  : https://www.occ.gov/tools/apps/rss/press-release.rss
  CFPB : https://www.consumerfinance.gov/feed/newsroom/
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx
from cachetools import TTLCache

from config.settings import FEED_CACHE_TTL
from src.models.schemas import RegulatoryItem

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Feed registry
# ─────────────────────────────────────────────────────────────

FEED_REGISTRY: dict[str, list[dict[str, str]]] = {
    "SEC": [
        {
            "url": "https://www.sec.gov/news/pressreleases.rss",
            "item_type": "press_release",
            "label": "SEC Press Releases",
        },
        {
            "url": "https://www.sec.gov/rss/litigation/litreleases.xml",
            "item_type": "enforcement",
            "label": "SEC Litigation Releases",
        },
        {
            "url": "https://www.sec.gov/rss/rules/proposed.xml",
            "item_type": "proposed_rule",
            "label": "SEC Proposed Rules",
        },
        {
            "url": "https://www.sec.gov/rss/rules/final.xml",
            "item_type": "final_rule",
            "label": "SEC Final Rules",
        },
    ],
    "CFTC": [
        {
            "url": "https://www.cftc.gov/rss/pressreleases.xml",
            "item_type": "press_release",
            "label": "CFTC Press Releases",
        },
    ],
    "FinCEN": [
        {
            "url": "https://www.fincen.gov/rss.xml",
            "item_type": "notice",
            "label": "FinCEN News",
        },
    ],
    "OCC": [
        {
            "url": "https://www.occ.gov/tools/apps/rss/press-release.rss",
            "item_type": "press_release",
            "label": "OCC Press Releases",
        },
    ],
    "CFPB": [
        {
            "url": "https://www.consumerfinance.gov/feed/newsroom/",
            "item_type": "press_release",
            "label": "CFPB Newsroom",
        },
    ],
    "FederalReserve": [
        {
            "url": "https://www.federalreserve.gov/feeds/press_monetary.xml",
            "item_type": "monetary_policy",
            "label": "Federal Reserve Monetary Policy",
        },
        {
            "url": "https://www.federalreserve.gov/feeds/press_bcreg.xml",
            "item_type": "banking_regulation",
            "label": "Federal Reserve Banking Regulation",
        },
        {
            "url": "https://www.federalreserve.gov/feeds/speeches.xml",
            "item_type": "speech",
            "label": "Federal Reserve Speeches",
        },
    ],
    "Treasury": [
        {
            "url": "https://home.treasury.gov/system/files/feed/press.xml",
            "item_type": "press_release",
            "label": "U.S. Treasury Press Releases",
        },
    ],
}

# ─────────────────────────────────────────────────────────────
# Cache: stores parsed feed items keyed by agency
# ─────────────────────────────────────────────────────────────

_feed_cache: TTLCache = TTLCache(maxsize=20, ttl=FEED_CACHE_TTL)


def _parse_date(entry: Any) -> str | None:
    """Extract ISO date string from a feedparser entry."""
    # feedparser provides published_parsed as a struct_time
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    if hasattr(entry, "published") and entry.published:
        try:
            dt = parsedate_to_datetime(entry.published)
            return dt.isoformat()
        except Exception:
            return entry.published
    return None


def _truncate_summary(text: str, max_chars: int = 500) -> str:
    """Strip HTML tags and truncate summary text."""
    # Very light HTML strip — avoids importing lxml
    import re
    clean = re.sub(r"<[^>]+>", " ", text or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_chars:
        clean = clean[:max_chars].rsplit(" ", 1)[0] + "…"
    return clean


def _fetch_feed(feed_url: str, item_type: str, agency: str) -> list[RegulatoryItem]:
    """Fetch and parse a single RSS/Atom feed, returning RegulatoryItem list."""
    items: list[RegulatoryItem] = []
    try:
        # feedparser handles redirects and most encoding issues internally
        parsed = feedparser.parse(feed_url)
        if parsed.bozo and not parsed.entries:
            logger.warning("Feed parsing error for %s: %s", feed_url, parsed.bozo_exception)
            return items

        for entry in parsed.entries:
            title = getattr(entry, "title", "Untitled")
            link = getattr(entry, "link", None)
            summary_raw = (
                getattr(entry, "summary", None)
                or getattr(entry, "description", None)
                or getattr(entry, "content", [{}])[0].get("value", "")
                if hasattr(entry, "content") and entry.content
                else ""
            )
            summary = _truncate_summary(summary_raw)
            published = _parse_date(entry)

            items.append(
                RegulatoryItem(
                    title=title,
                    agency=agency,
                    published=published,
                    summary=summary or title,
                    url=link,
                    item_type=item_type,
                )
            )
    except Exception as exc:
        logger.error("Failed to fetch feed %s: %s", feed_url, exc)
    return items


def _cutoff_date(days: int) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(days=days)


def _filter_by_days(items: list[RegulatoryItem], days: int) -> list[RegulatoryItem]:
    """Filter items to those published within the last `days` days."""
    cutoff = _cutoff_date(days)
    filtered = []
    for item in items:
        if item.published:
            try:
                pub = datetime.fromisoformat(item.published)
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if pub >= cutoff:
                    filtered.append(item)
            except Exception:
                # If we can't parse the date, include the item
                filtered.append(item)
        else:
            # No date info — include it
            filtered.append(item)
    return filtered


def get_agency_items(agency_name: str, days: int = 30) -> list[RegulatoryItem]:
    """
    Fetch regulatory items for an agency, with caching.

    Parameters
    ----------
    agency_name : str
        One of: SEC, CFTC, FinCEN, OCC, CFPB
    days : int
        Number of days back to include

    Returns
    -------
    list[RegulatoryItem]
        Filtered list of recent items
    """
    cache_key = agency_name.upper()

    if cache_key not in _feed_cache:
        feeds = FEED_REGISTRY.get(cache_key, [])
        all_items: list[RegulatoryItem] = []

        for feed_config in feeds:
            items = _fetch_feed(
                feed_config["url"],
                feed_config["item_type"],
                cache_key,
            )
            all_items.extend(items)
            logger.info("Fetched %d items from %s", len(items), feed_config["label"])

        # Sort by published date descending
        def sort_key(item: RegulatoryItem) -> str:
            return item.published or "0000-00-00"

        all_items.sort(key=sort_key, reverse=True)
        _feed_cache[cache_key] = all_items
        logger.info("Cached %d items for agency %s", len(all_items), cache_key)

    cached = _feed_cache[cache_key]
    return _filter_by_days(cached, days)


def get_all_agencies_items(days: int = 30) -> dict[str, list[RegulatoryItem]]:
    """Fetch items for all agencies."""
    result: dict[str, list[RegulatoryItem]] = {}
    for agency in FEED_REGISTRY:
        result[agency] = get_agency_items(agency, days)
    return result


def get_data_sources(agency_name: str) -> list[str]:
    """Return the source URLs for a given agency."""
    feeds = FEED_REGISTRY.get(agency_name.upper(), [])
    return [f["url"] for f in feeds]


def invalidate_cache(agency_name: str | None = None) -> None:
    """Invalidate feed cache for a specific agency or all agencies."""
    if agency_name:
        _feed_cache.pop(agency_name.upper(), None)
    else:
        _feed_cache.clear()
