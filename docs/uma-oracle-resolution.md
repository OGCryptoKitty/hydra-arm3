# UMA Optimistic Oracle Resolution Data

HYDRA provides formatted assertion data for the UMA Optimistic Oracle (OOv2), the resolution layer for Polymarket prediction markets.

## The Problem

Asserting a bond to resolve a Polymarket market requires:
1. A factual claim about a real-world event
2. An evidence chain (URLs + timestamps) to defend the assertion during the dispute window
3. Correct formatting for UMA's ancillary data encoding

A failed assertion risks losing the $750+ USDC.e bond. HYDRA provides a $1.00 pre-assertion check.

## UMA Oracle Endpoint

```python
import httpx

# Check resolution before posting bond ($1.00 USDC)
oracle_data = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/oracle/uma",
    json={
        "assertion_claim": "The Federal Reserve held interest rates at the May 2025 FOMC meeting.",
        "bond_currency": "USDC.e",
        "market_question": "Will the Fed hold rates at the May 2025 FOMC meeting?"
    },
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

print(oracle_data["resolved"])           # True/False
print(oracle_data["resolution_value"])   # "Yes" or "No"
print(oracle_data["confidence"])         # 0-100
print(oracle_data["ancillary_data"])     # hex-encoded for OOv2 submission
print(oracle_data["proposed_price"])     # 1e18 (YES) or 0 (NO)
print(oracle_data["evidence_chain"])     # list of {url, title, timestamp, excerpt}
print(oracle_data["bond_recommendation"])  # "proceed" or "do_not_assert"
```

## FOMC-Specific Resolution

For Fed rate decision markets, use the higher-confidence `/v1/fed/resolution` endpoint ($50.00):

```python
fomc_resolution = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/fed/resolution",
    json={
        "market_question": "Will the Fed cut rates by 25bp at the June 2025 FOMC meeting?",
        "include_uma_data": True
    },
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

uma = fomc_resolution["uma_data"]
# uma["ancillary_data"] — ready to submit to UMA OOv2
# uma["evidence_chain"] — Fed statement, press conference transcript, vote record
```

## Chainlink External Adapter

HYDRA also serves as a Chainlink external adapter for regulatory data delivery on-chain:

```python
chainlink_data = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/oracle/chainlink",
    json={
        "data_request": "SEC enforcement action count 2025",
        "job_run_id": "1"
    },
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

# chainlink_data["data"]["result"] — numeric value for on-chain delivery
# chainlink_data["statusCode"] — 200 on success
```

## Market Resolution Assessment

For any prediction market (not just FOMC), use the general resolution endpoint ($1.00):

```python
assessment = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/markets/resolution",
    json={"market_id": "0x<condition_id_or_kalshi_ticker>"},
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

print(assessment["resolved"])
print(assessment["confidence"])
print(assessment["evidence_summary"])
```

## Related

- [FOMC Fed Signals](fomc-fed-signals.md)
- [Polymarket Integration](polymarket-integration.md)
- [x402 Payment Guide](x402-payment-guide.md)
