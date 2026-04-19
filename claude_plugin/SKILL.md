---
name: hydra-regulatory-intelligence
description: Query HYDRA for real-time regulatory intelligence, prediction market signals, FOMC analysis, and oracle data. Pay-per-call via x402 on Base L2.
when_to_use: When the user asks about regulatory risk, prediction market signals, FOMC rate decisions, SEC/CFTC actions, or needs oracle assertion data for UMA/Chainlink.
allowed-tools:
  - WebFetch
  - Bash
paths:
  - "**"
---

# HYDRA Regulatory Intelligence

Query the HYDRA API for regulatory intelligence and prediction market data.

## Free endpoints (no payment required)

```bash
# Health check
curl -s https://hydra-api-nlnj.onrender.com/health

# Active prediction markets
curl -s https://hydra-api-nlnj.onrender.com/v1/markets

# Full pricing table
curl -s https://hydra-api-nlnj.onrender.com/pricing
```

## Paid endpoints (x402 USDC on Base)

Payment: Send USDC to `0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141` on Base (chain 8453), include tx hash in `X-Payment-Proof` header.

```bash
# Token price ($0.001)
curl -H "X-Payment-Proof: 0x<tx_hash>" \
  "https://hydra-api-nlnj.onrender.com/v1/util/crypto/price?token=$ARGUMENTS"

# Regulatory scan ($2.00)
curl -X POST -H "X-Payment-Proof: 0x<tx_hash>" \
  -H "Content-Type: application/json" \
  -d '{"query": "$ARGUMENTS"}' \
  https://hydra-api-nlnj.onrender.com/v1/regulatory/scan

# FOMC signal ($5.00)
curl -X POST -H "X-Payment-Proof: 0x<tx_hash>" \
  https://hydra-api-nlnj.onrender.com/v1/fed/signal
```

## MCP Server

Add to Claude Desktop or Claude Code:
```bash
claude mcp add --transport http hydra-regulatory https://hydra-api-nlnj.onrender.com/mcp
```
