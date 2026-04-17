# Kalshi Integration Guide

HYDRA normalizes Kalshi's regulatory prediction markets (especially the KXFED rate series) into a consistent schema alongside Polymarket data.

## Kalshi Market Discovery

```bash
curl "https://hydra-api-nlnj.onrender.com/v1/markets"
```

Kalshi markets in the response have:
- `platform`: `"kalshi"`
- `ticker`: Kalshi's ticker format (e.g., `KXFED-25JUN18`)
- `yes_price`: current YES price (0–1)
- `category`: `"fed"`, `"sec"`, `"crypto"`, etc.

## KXFED Series — Fed Rate Markets

Kalshi's KXFED series tracks Fed rate decisions. HYDRA tracks all active KXFED markets and provides:

1. **Signal endpoint** — directional analysis using CME FedWatch data, Fed governor speeches, economic indicators
2. **Resolution assessment** — HOLD/CUT/HIKE verdict with confidence and evidence chain

```bash
# Get signal for specific KXFED market ($0.10 USDC)
curl -X POST https://hydra-api-nlnj.onrender.com/v1/markets/signal/KXFED-25JUN18 \
  -H "X-PAYMENT: 0x<tx_hash>"
```

## Oracle Resolution for Kalshi

After FOMC announcements, use the resolution endpoint to verify resolution direction:

```python
import httpx

resolution = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/fed/resolution",
    json={
        "market_question": "Will the Fed hold rates at the June 2025 FOMC meeting?",
        "include_kalshi_format": True
    },
    headers={"X-PAYMENT": "0x<tx_hash>"}  # $50 USDC
).json()

# Kalshi-formatted resolution
kalshi_data = resolution["kalshi_format"]
print(kalshi_data["ticker"])       # KXFED-25JUN18
print(kalshi_data["resolution"])   # "yes" or "no"
print(kalshi_data["evidence"])     # Fed statement URLs and key quotes
```

## Regulatory Changes Feed

Track regulatory events that affect Kalshi markets:

```python
events = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/markets/events",
    json={"since_hours": 24, "agencies": ["Fed", "SEC", "CFTC"]},
    headers={"X-PAYMENT": "0x<tx_hash>"}  # $0.15 USDC
).json()

for event in events["events"]:
    print(event["title"])
    print(event["matched_markets"])  # which Kalshi/Polymarket markets are affected
    print(event["urgency"])          # "high", "medium", "low"
```

## High-Frequency Bot Polling

For bots that need low-latency event detection, use the micro feed ($0.05 USDC):

```bash
# Returns last 10 regulatory events matched to active markets
curl -X GET https://hydra-api-nlnj.onrender.com/v1/markets/feed \
  -H "X-PAYMENT: 0x<tx_hash>"
```

## Related

- [FOMC Fed Signals](fomc-fed-signals.md) — pre-meeting analysis for KXFED markets
- [Polymarket Integration](polymarket-integration.md)
- [Live API Docs](https://hydra-api-nlnj.onrender.com/docs)
