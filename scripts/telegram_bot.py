#!/usr/bin/env python3
"""
HYDRA Telegram Bot
===================
A Telegram bot that surfaces free regulatory intelligence and promotes
the HYDRA API for deeper analysis.

Commands:
    /start    — Introduction and how to use HYDRA
    /markets  — Active regulatory prediction markets (calls /v1/markets)
    /latest   — Last 5 regulatory events from SEC, CFTC, FinCEN
    /pricing  — HYDRA API pricing table
    /help     — Command list

Requirements:
    pip install python-telegram-bot httpx

Configuration:
    Set BOT_TOKEN environment variable (from @BotFather on Telegram).
    The bot hits the live HYDRA API at https://hydra-api-nlnj.onrender.com.

Run:
    BOT_TOKEN=<your_token> python scripts/telegram_bot.py

Or set BOT_TOKEN in the .env file at the project root.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

# ── Dependency check ─────────────────────────────────────────

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
    )
    from telegram.constants import ParseMode
except ImportError:
    print(
        "python-telegram-bot not installed.\n"
        "Run: pip install python-telegram-bot httpx",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx", file=sys.stderr)
    sys.exit(1)

try:
    import feedparser
except ImportError:
    feedparser = None  # type: ignore

# ── Config ───────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Fill in your BOT_TOKEN from @BotFather, or set the BOT_TOKEN environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN", "REPLACE_WITH_YOUR_BOT_TOKEN")

HYDRA_API_BASE = "https://hydra-api-nlnj.onrender.com"
HYDRA_DOCS_URL = f"{HYDRA_API_BASE}/docs"
HYDRA_PRICING_URL = f"{HYDRA_API_BASE}/pricing"

CTA = (
    "\n\n💰 *Get full analysis, signals, and alpha reports at "
    f"[HYDRA API]({HYDRA_DOCS_URL})* — pay-per-use with USDC via x402"
)

FEED_REGISTRY = {
    "SEC": [
        {"url": "https://www.sec.gov/news/pressreleases.rss", "label": "SEC Press Releases"},
        {"url": "https://www.sec.gov/rss/litigation/litreleases.xml", "label": "SEC Enforcement"},
    ],
    "CFTC": [
        {"url": "https://www.cftc.gov/rss/pressreleases.xml", "label": "CFTC Press Releases"},
    ],
    "FinCEN": [
        {"url": "https://www.fincen.gov/rss.xml", "label": "FinCEN Notices"},
    ],
}

# ── Helpers ──────────────────────────────────────────────────

def _escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    # For MarkdownV1 / HTML mode we skip heavy escaping — using HTML parse mode instead
    return text


async def _fetch_json(url: str, timeout: float = 10.0) -> Any:
    """Fetch JSON from the HYDRA API."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def _parse_date(entry: Any) -> datetime | None:
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


def _fetch_latest_events(n: int = 5) -> list[dict]:
    """Fetch the most recent n regulatory events via direct RSS (no payment needed)."""
    if feedparser is None:
        return []
    items = []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
    for agency, feeds in FEED_REGISTRY.items():
        for feed_config in feeds:
            try:
                parsed = feedparser.parse(feed_config["url"])
                for entry in parsed.entries[:5]:
                    pub = _parse_date(entry)
                    if pub and pub < cutoff:
                        continue
                    title = getattr(entry, "title", "Untitled")
                    link = getattr(entry, "link", None)
                    items.append({
                        "agency": agency,
                        "title": title,
                        "link": link,
                        "published": pub,
                    })
            except Exception as exc:
                logger.warning("Feed fetch failed for %s: %s", feed_config["url"], exc)
    items.sort(
        key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return items[:n]


# ── Command Handlers ─────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — Introduction to HYDRA."""
    text = (
        "<b>HYDRA — Regulatory Intelligence API</b>\n\n"
        "HYDRA monitors SEC, CFTC, Fed, and FinCEN in real time and translates "
        "regulatory events into actionable signals for prediction markets.\n\n"
        "<b>What HYDRA provides:</b>\n"
        "• Scored signals for Polymarket and Kalshi markets\n"
        "• Pre-FOMC analysis and real-time Fed decision classification\n"
        "• Oracle-ready resolution verdicts for UMA and Chainlink\n"
        "• Premium alpha reports with Kelly-sized trade verdicts\n\n"
        "<b>How it works:</b>\n"
        "1. Call any endpoint\n"
        "2. Receive HTTP 402 with exact USDC amount\n"
        "3. Pay USDC on Base and resend — get your data\n\n"
        "<b>Available commands:</b>\n"
        "/markets — Active regulatory prediction markets\n"
        "/latest — Last 5 regulatory events\n"
        "/pricing — Full API pricing table\n"
        "/help — This message\n\n"
        f'💰 <a href="{HYDRA_DOCS_URL}">Full API docs and paid endpoints →</a>'
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — Command list."""
    await cmd_start(update, context)


async def cmd_markets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/markets — Active regulatory prediction markets (free endpoint)."""
    await update.message.reply_text("Fetching active regulatory prediction markets…")

    try:
        data = await _fetch_json(f"{HYDRA_API_BASE}/v1/markets")
    except Exception as exc:
        logger.error("Failed to fetch /v1/markets: %s", exc)
        await update.message.reply_text(
            f"⚠️ Could not fetch market data: {exc}\n\n"
            f'<a href="{HYDRA_DOCS_URL}">Try the API directly →</a>',
            parse_mode=ParseMode.HTML,
        )
        return

    markets = data if isinstance(data, list) else data.get("markets", [])

    if not markets:
        text = (
            "<b>📊 Active Regulatory Prediction Markets</b>\n\n"
            "No open markets found at this time.\n\n"
            f'<a href="{HYDRA_DOCS_URL}">Check the API for the latest data →</a>'
        )
    else:
        lines = ["<b>📊 Active Regulatory Prediction Markets</b>\n"]
        for i, market in enumerate(markets[:10], 1):
            title = market.get("title") or market.get("name") or market.get("question") or "Market"
            platform = market.get("platform") or market.get("source") or ""
            prob = market.get("probability") or market.get("yes_probability")
            line = f"{i}. <b>{title}</b>"
            if platform:
                line += f" <i>({platform})</i>"
            if prob is not None:
                try:
                    pct = float(prob) * 100
                    line += f" — YES: {pct:.0f}%"
                except Exception:
                    pass
            lines.append(line)
        if len(markets) > 10:
            lines.append(f"\n<i>…and {len(markets) - 10} more</i>")
        text = "\n".join(lines)

    cta_html = (
        f'\n\n💰 <a href="{HYDRA_DOCS_URL}">Get full analysis, signals, and alpha reports at HYDRA API</a>'
        " — pay-per-use with USDC via x402"
    )
    await update.message.reply_text(
        text + cta_html,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def cmd_latest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/latest — Last 5 regulatory events from SEC, CFTC, FinCEN."""
    await update.message.reply_text("Fetching latest regulatory events…")

    if feedparser is None:
        await update.message.reply_text(
            "⚠️ feedparser library not available on this server.\n\n"
            f'<a href="{HYDRA_DOCS_URL}">Use the full API for live event data →</a>',
            parse_mode=ParseMode.HTML,
        )
        return

    # Run synchronous feedparser in a thread pool
    loop = asyncio.get_event_loop()
    events = await loop.run_in_executor(None, _fetch_latest_events, 5)

    if not events:
        text = (
            "<b>📰 Latest Regulatory Events</b>\n\n"
            "No recent events found (last 7 days).\n\n"
            f'<a href="{HYDRA_DOCS_URL}">Use the full API for deeper search →</a>'
        )
    else:
        lines = ["<b>📰 Latest Regulatory Events</b>\n"]
        for event in events:
            pub_str = ""
            if event["published"]:
                try:
                    pub_str = f" · {event['published'].strftime('%b %d')}"
                except Exception:
                    pass
            title = event["title"]
            agency = event["agency"]
            if event.get("link"):
                lines.append(f'• <b>{agency}{pub_str}</b>: <a href="{event["link"]}">{title}</a>')
            else:
                lines.append(f"• <b>{agency}{pub_str}</b>: {title}")
        text = "\n".join(lines)

    cta_html = (
        f'\n\n💰 <a href="{HYDRA_DOCS_URL}">Get full analysis, signals, and alpha reports at HYDRA API</a>'
        " — pay-per-use with USDC via x402"
    )
    await update.message.reply_text(
        text + cta_html,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def cmd_pricing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/pricing — HYDRA API pricing table."""
    text = (
        "<b>💲 HYDRA API Pricing (USDC on Base)</b>\n\n"
        "<b>Free</b>\n"
        "• GET /v1/markets — Active prediction markets\n"
        "• GET /health — API status\n\n"
        "<b>Micro Tier ($0.10–$1.00)</b>\n"
        "• GET /v1/markets/feed — $0.10\n"
        "• POST /v1/markets/events — $0.50\n"
        "• POST /v1/regulatory/changes — $1.00\n"
        "• POST /v1/regulatory/query — $1.00\n\n"
        "<b>Standard Tier ($2.00–$5.00)</b>\n"
        "• POST /v1/markets/signal/{id} — $2.00\n"
        "• POST /v1/regulatory/scan — $2.00\n"
        "• POST /v1/regulatory/jurisdiction — $3.00\n"
        "• POST /v1/markets/signals (bulk) — $5.00\n"
        "• POST /v1/oracle/uma — $5.00\n"
        "• POST /v1/oracle/chainlink — $5.00\n"
        "• POST /v1/fed/signal — $5.00\n\n"
        "<b>Premium Tier ($10.00–$50.00)</b>\n"
        "• POST /v1/markets/alpha — $10.00\n"
        "• POST /v1/markets/resolution — $25.00\n"
        "• POST /v1/fed/decision — $25.00\n"
        "• POST /v1/fed/resolution — $50.00\n\n"
        "<b>Payment:</b> USDC · Base · Chain 8453 · x402 protocol\n"
        "<b>Wallet:</b> <code>0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141</code>\n\n"
        f'<a href="{HYDRA_DOCS_URL}">Full API documentation →</a>'
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


# ── Application ──────────────────────────────────────────────

def create_app(token: str) -> Application:
    """Build and return the Telegram bot Application."""
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("markets", cmd_markets))
    app.add_handler(CommandHandler("latest", cmd_latest))
    app.add_handler(CommandHandler("pricing", cmd_pricing))
    return app


def main() -> None:
    token = BOT_TOKEN
    if not token or token == "REPLACE_WITH_YOUR_BOT_TOKEN":
        print(
            "ERROR: BOT_TOKEN not set.\n"
            "1. Create a bot via @BotFather on Telegram\n"
            "2. Set BOT_TOKEN environment variable or update BOT_TOKEN in this file",
            file=sys.stderr,
        )
        sys.exit(1)

    logger.info("Starting HYDRA Telegram Bot…")
    app = create_app(token)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
