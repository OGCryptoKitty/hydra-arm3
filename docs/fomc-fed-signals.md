# FOMC Fed Signal API

HYDRA provides three tiers of Federal Reserve intelligence for prediction market traders.

## The Fed Decision Package

| Endpoint | Price | Use Case |
|----------|-------|----------|
| `POST /v1/fed/signal` | $5.00 | Pre-meeting analysis (days before FOMC) |
| `POST /v1/fed/decision` | $25.00 | Real-time classification on FOMC day |
| `POST /v1/fed/resolution` | $50.00 | Full resolution package for oracle asserters |

## Pre-FOMC Signal ($5.00)

Call this 1–7 days before an FOMC meeting to get HYDRA's rate probability model:

```python
import httpx

signal = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/fed/signal",
    json={"include_speech_analysis": True, "include_indicators": True},
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

print(signal["rate_probability"])   # {"hold": 0.87, "cut": 0.11, "hike": 0.02}
print(signal["cme_fedwatch"])       # CME market-implied probabilities
print(signal["speech_tone"])        # "hawkish", "dovish", "neutral"
print(signal["dot_plot_delta"])     # median dot shift vs prior meeting
print(signal["key_indicators"])     # CPI, PCE, unemployment, GDP
```

## Real-Time FOMC Classification ($25.00)

On FOMC announcement days, this endpoint attempts to classify the decision within 30 seconds of the Federal Reserve statement release:

```python
decision = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/fed/decision",
    json={"include_market_impact": True},
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

print(decision["decision"])         # "HOLD", "CUT_25", "CUT_50", "HIKE_25"
print(decision["vote_breakdown"])   # e.g., "11-1 HOLD"
print(decision["statement_key_phrases"])
print(decision["market_impact"])    # expected impact on Kalshi/Polymarket markets
```

## Oracle Resolution Package ($50.00)

For UMA bond asserters and automated oracle systems resolving FOMC prediction markets:

```python
resolution = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/fed/resolution",
    json={
        "market_question": "Will the Federal Reserve hold interest rates at the June 2025 FOMC meeting?",
        "include_uma_data": True,
        "include_kalshi_format": True,
        "include_polymarket_format": True
    },
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

# Use in UMA Optimistic Oracle assertion
uma_data = resolution["uma_data"]
# uma_data["ancillary_data"] — encoded claim for OOv2
# uma_data["proposed_price"] — 1e18 (YES) or 0 (NO)
# uma_data["evidence_chain"] — list of source URLs with timestamps
```

## FOMC Calendar

HYDRA tracks the Federal Reserve's published meeting calendar. The next scheduled FOMC date is always available via the pre-signal endpoint without payment:

```bash
curl https://hydra-api-nlnj.onrender.com/pricing
# Returns next FOMC date in the pricing context
```

## Related

- [Kalshi KXFED Markets](kalshi-integration.md)
- [UMA Oracle Resolution](uma-oracle-resolution.md)
- [Live API Docs](https://hydra-api-nlnj.onrender.com/docs)
