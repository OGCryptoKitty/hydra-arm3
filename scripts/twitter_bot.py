#!/usr/bin/env python3
"""
HYDRA Twitter/X Bot
====================
Fetches the latest regulatory events from SEC, CFTC, and FinCEN RSS feeds,
formats them as tweet-length posts, and saves ready-to-post tweets to
scripts/pending_tweets.json.

Supports optional live posting via Twitter API v2 (tweepy).
Default mode: dry-run — generates and saves tweets without posting.

Usage:
    python scripts/twitter_bot.py                  # dry-run, saves to pending_tweets.json
    python scripts/twitter_bot.py --post           # post via Twitter API v2 (needs credentials)
    python scripts/twitter_bot.py --count 10       # generate up to 10 tweets (default: 7)

Twitter API v2 credentials (set via environment variables or .env file):
    TWITTER_BEARER_TOKEN
    TWITTER_API_KEY
    TWITTER_API_SECRET
    TWITTER_ACCESS_TOKEN
    TWITTER_ACCESS_TOKEN_SECRET
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

try:
    import feedparser
except ImportError:
    print("feedparser not installed. Run: pip install feedparser", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────

HYDRA_API_URL = "https://hydra-api-nlnj.onrender.com"
HYDRA_DOCS_URL = f"{HYDRA_API_URL}/docs"

OUTPUT_PATH = Path(__file__).parent / "pending_tweets.json"

MAX_TWEET_LEN = 280

# RSS feeds — same registry as src/services/feeds.py
FEED_REGISTRY: dict[str, list[dict[str, str]]] = {
    "SEC": [
        {"url": "https://www.sec.gov/news/pressreleases.rss", "item_type": "Press Release"},
        {"url": "https://www.sec.gov/rss/litigation/litreleases.xml", "item_type": "Enforcement"},
        {"url": "https://www.sec.gov/rss/rules/proposed.xml", "item_type": "Proposed Rule"},
        {"url": "https://www.sec.gov/rss/rules/final.xml", "item_type": "Final Rule"},
    ],
    "CFTC": [
        {"url": "https://www.cftc.gov/rss/pressreleases.xml", "item_type": "Press Release"},
    ],
    "FinCEN": [
        {"url": "https://www.fincen.gov/rss.xml", "item_type": "Notice"},
    ],
}

AGENCY_EMOJI: dict[str, str] = {
    "SEC": "🏛️",
    "CFTC": "📋",
    "FinCEN": "🏦",
    "FED": "🏦",
    "OCC": "🏦",
}

# Keywords that increase tweet priority (regulatory relevance to prediction markets)
HIGH_PRIORITY_KEYWORDS = [
    "crypto", "bitcoin", "ethereum", "digital asset", "stablecoin",
    "defi", "exchange", "enforcement", "fraud", "settlement",
    "final rule", "proposed rule", "rulemaking", "FOMC", "federal funds",
    "interest rate", "derivatives", "futures", "options", "market manipulation",
]

CTA_SUFFIX = f" | Full regulatory analysis: {HYDRA_DOCS_URL} | #Polymarket #Kalshi #regulation"


# ──────────────────────────────────────────────────────────────
# Feed parsing
# ──────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    clean = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", clean).strip()


def _parse_date(entry: Any) -> datetime | None:
    """Extract a UTC datetime from a feedparser entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    if hasattr(entry, "published") and entry.published:
        try:
            return parsedate_to_datetime(entry.published).astimezone(timezone.utc)
        except Exception:
            pass
    return None


def fetch_recent_items(days: int = 3) -> list[dict]:
    """
    Fetch regulatory items from all registered feeds published within
    the last `days` days. Returns a list of dicts sorted by date descending.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    items: list[dict] = []

    for agency, feeds in FEED_REGISTRY.items():
        for feed_config in feeds:
            url = feed_config["url"]
            item_type = feed_config["item_type"]
            logger.info("Fetching %s %s feed…", agency, item_type)
            try:
                parsed = feedparser.parse(url)
                if parsed.bozo and not parsed.entries:
                    logger.warning("Feed parse error for %s: %s", url, parsed.bozo_exception)
                    continue
                for entry in parsed.entries:
                    pub = _parse_date(entry)
                    if pub and pub < cutoff:
                        continue  # too old
                    title = _strip_html(getattr(entry, "title", "Untitled"))
                    link = getattr(entry, "link", None)
                    items.append({
                        "agency": agency,
                        "item_type": item_type,
                        "title": title,
                        "link": link,
                        "published": pub.isoformat() if pub else None,
                        "published_dt": pub,
                    })
            except Exception as exc:
                logger.error("Failed to fetch %s: %s", url, exc)

    # Sort by date descending (most recent first); None dates go last
    items.sort(
        key=lambda x: x["published_dt"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return items


# ──────────────────────────────────────────────────────────────
# Tweet formatting
# ──────────────────────────────────────────────────────────────

def _priority_score(item: dict) -> int:
    """Score an item by how prediction-market-relevant it is."""
    text = (item["title"] + " " + item["item_type"]).lower()
    score = 0
    for kw in HIGH_PRIORITY_KEYWORDS:
        if kw.lower() in text:
            score += 1
    # Enforcement actions are high priority
    if "enforcement" in item["item_type"].lower():
        score += 2
    # Final rules are higher priority than proposed
    if "final rule" in item["item_type"].lower():
        score += 1
    return score


def format_tweet(item: dict) -> str:
    """
    Format a regulatory item as a tweet (≤280 chars).
    Template: {emoji} {AGENCY} {EVENT_TYPE}: {headline} | {CTA}
    """
    emoji = AGENCY_EMOJI.get(item["agency"], "🏛️")
    prefix = f"{emoji} {item['agency']} {item['item_type'].upper()}: "

    # Reserve space for the CTA suffix
    suffix = CTA_SUFFIX
    max_headline = MAX_TWEET_LEN - len(prefix) - len(suffix) - 1

    headline = item["title"]
    if len(headline) > max_headline:
        headline = headline[: max_headline - 1].rsplit(" ", 1)[0] + "…"

    return f"{prefix}{headline}{suffix}"


def generate_tweets(items: list[dict], count: int = 7) -> list[dict]:
    """
    Select the most prediction-market-relevant items and format them as tweets.
    Returns a list of tweet dicts with text, source metadata, and timestamp.
    """
    # Sort by priority score (ties broken by recency — already sorted)
    scored = sorted(items, key=_priority_score, reverse=True)
    selected = scored[:count]

    tweets = []
    for item in selected:
        tweet_text = format_tweet(item)
        tweets.append({
            "text": tweet_text,
            "char_count": len(tweet_text),
            "agency": item["agency"],
            "item_type": item["item_type"],
            "source_title": item["title"],
            "source_url": item["link"],
            "published": item["published"],
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "posted": False,
            "post_result": None,
        })

    return tweets


# ──────────────────────────────────────────────────────────────
# Twitter API v2 posting (tweepy)
# ──────────────────────────────────────────────────────────────

def post_tweet_via_tweepy(tweet_text: str) -> dict:
    """
    Post a single tweet via Twitter API v2 using tweepy.
    Requires environment variables:
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
    """
    try:
        import tweepy  # type: ignore
    except ImportError:
        return {"success": False, "error": "tweepy not installed. Run: pip install tweepy"}

    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        return {
            "success": False,
            "error": (
                "Missing Twitter credentials. Set TWITTER_API_KEY, TWITTER_API_SECRET, "
                "TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET environment variables."
            ),
        }

    try:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        response = client.create_tweet(text=tweet_text)
        tweet_id = response.data.get("id") if response.data else None
        return {
            "success": True,
            "tweet_id": tweet_id,
            "url": f"https://twitter.com/i/web/status/{tweet_id}" if tweet_id else None,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def load_existing_tweets() -> list[dict]:
    """Load existing pending_tweets.json if it exists."""
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH) as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_tweets(tweets: list[dict]) -> None:
    """Save tweets to pending_tweets.json."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(tweets, f, indent=2, default=str)
    logger.info("Saved %d tweets to %s", len(tweets), OUTPUT_PATH)


def run(post_live: bool = False, count: int = 7, days: int = 3) -> None:
    """
    Main execution:
    1. Fetch recent regulatory items
    2. Generate formatted tweets
    3. Either save (dry-run) or post via Twitter API and save results
    """
    logger.info("HYDRA Twitter Bot — fetching last %d days of regulatory events", days)

    items = fetch_recent_items(days=days)
    logger.info("Fetched %d total items across all agencies", len(items))

    if not items:
        logger.warning("No items found in the last %d days. Try increasing --days.", days)
        return

    tweets = generate_tweets(items, count=count)
    logger.info("Generated %d tweets", len(tweets))

    if post_live:
        logger.info("Live posting mode — posting to Twitter API v2")
        for tweet in tweets:
            result = post_tweet_via_tweepy(tweet["text"])
            tweet["posted"] = result.get("success", False)
            tweet["post_result"] = result
            if result.get("success"):
                logger.info("Posted: %s", tweet["text"][:80])
            else:
                logger.error("Failed to post: %s", result.get("error"))
    else:
        logger.info("Dry-run mode — tweets NOT posted. Use --post to post live.")

    # Merge with any existing pending tweets (new ones first)
    existing = load_existing_tweets()
    # Deduplicate by source_title
    existing_titles = {t.get("source_title") for t in existing}
    new_tweets = [t for t in tweets if t.get("source_title") not in existing_titles]
    combined = new_tweets + existing

    save_tweets(combined)

    # Print preview
    print(f"\n{'='*60}")
    print(f"  HYDRA Twitter Bot — {len(new_tweets)} new tweets generated")
    print(f"{'='*60}\n")
    for i, tweet in enumerate(new_tweets, 1):
        print(f"[{i}] ({tweet['char_count']} chars) {tweet['agency']} {tweet['item_type']}")
        print(f"    {tweet['text']}")
        if tweet.get("posted"):
            print(f"    ✓ Posted: {tweet.get('post_result', {}).get('url', 'unknown')}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="HYDRA Twitter Bot — generates regulatory event tweets for Polymarket/Kalshi audience"
    )
    parser.add_argument(
        "--post",
        action="store_true",
        default=False,
        help="Post tweets live via Twitter API v2 (requires credentials in env)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=7,
        help="Number of tweets to generate (default: 7, max: 10)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="How many days back to fetch events (default: 3)",
    )
    args = parser.parse_args()
    run(post_live=args.post, count=min(args.count, 10), days=args.days)
