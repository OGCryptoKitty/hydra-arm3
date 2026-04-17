# Polymarket Integration Guide

HYDRA provides a free regulatory market discovery layer over the Polymarket API, plus paid trading signals for prediction market bots.

## Free Market Discovery

Get all active Polymarket regulatory markets in a normalized format:

```bash
curl "https://hydra-api-nlnj.onrender.com/v1/markets?platform=polymarket"
```

Response includes:
- `condition_id` — Polymarket's unique market identifier (0x...)
- `title` — market question
- `yes_price` — current YES token price (0–1)
- `volume_24h` — 24-hour USDC volume
- `end_date` — resolution timestamp
- `category` — regulatory domain (fed/sec/cftc/crypto/regulation)

## Trading Signals for Polymarket Bots

For each Polymarket market, HYDRA provides directional regulatory intelligence:

```python
import httpx

# Step 1: Discover markets (free)
markets = httpx.get("https://hydra-api-nlnj.onrender.com/v1/markets").json()
regulatory_markets = [m for m in markets if m["platform"] == "polymarket"]

# Step 2: Get signal for a specific market ($0.10 USDC via x402)
market_id = regulatory_markets[0]["condition_id"]

# First call returns 402 with payment instructions
resp = httpx.post(f"https://hydra-api-nlnj.onrender.com/v1/markets/signal/{market_id}")
# resp.status_code == 402
# resp.json()["payment"]["amount"] == "100000"  (0.10 USDC in base units)
# resp.json()["payment"]["payTo"] == "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141"

# After paying 0.10 USDC on Base, retry with tx hash:
signal = httpx.post(
    f"https://hydra-api-nlnj.onrender.com/v1/markets/signal/{market_id}",
    headers={"X-PAYMENT": "0x<your_tx_hash>"}
).json()

print(signal["direction"])    # "bullish_yes", "bullish_no", or "neutral"
print(signal["confidence"])   # 0-100
print(signal["analysis"])     # regulatory reasoning
```

## Full Alpha Report

For sizing large positions ($1,000+ USDC), use the alpha endpoint ($2.00):

```python
alpha = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/markets/alpha",
    json={"market_id": condition_id, "position": "yes", "size_usdc": 1000},
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

print(alpha["edge"])           # HYDRA probability vs market price
print(alpha["recommended"])    # True/False
print(alpha["optimal_entry"])  # Price at which the trade has positive EV
```

## x402 Discovery Manifest

HYDRA's full pricing manifest for automated agents:
```
https://hydra-api-nlnj.onrender.com/.well-known/x402.json
```

## Related

- [Kalshi Integration](kalshi-integration.md)
- [x402 Payment Guide](x402-payment-guide.md)
- [Live API Docs](https://hydra-api-nlnj.onrender.com/docs)
