# HYDRA Regulatory Intelligence API

**HYDRA** is a real-time regulatory intelligence API for prediction market traders, compliance automation bots, and DeFi oracle systems.

## Quick Start

```bash
# Free: all active regulatory prediction markets
curl https://hydra-api-nlnj.onrender.com/v1/markets

# Free: API pricing and payment addresses
curl https://hydra-api-nlnj.onrender.com/pricing

# Docs and interactive explorer
open https://hydra-api-nlnj.onrender.com/docs
```

No API key required for free endpoints. Paid endpoints accept USDC on Base via the x402 payment protocol.

## What HYDRA Covers

| Category | Endpoints | Price |
|----------|-----------|-------|
| Prediction Markets | Live regulatory markets from Polymarket + Kalshi | Free |
| Trading Signals | Directional signals with confidence scores | $0.10–$0.25 |
| Fed Intelligence | FOMC analysis, dot plot tracking | $5–$50 |
| Regulatory Scan | Business → applicable regulations | $1.00 |
| Oracle Data | UMA OOv2 + Chainlink adapter | $0.50–$1.00 |
| Alpha Reports | Full trade recommendation | $2.00 |

## API Base URL

```
https://hydra-api-nlnj.onrender.com
```

## Documentation

- [Polymarket Integration](polymarket-integration.md) — trading bot setup, signal consumption
- [Kalshi Integration](kalshi-integration.md) — ticker mapping, KXFED series
- [FOMC Fed Signals](fomc-fed-signals.md) — pre-meeting analysis, real-time classification
- [UMA Oracle Resolution](uma-oracle-resolution.md) — Optimistic Oracle assertion data
- [x402 Payment Guide](x402-payment-guide.md) — USDC payment flow, agent integration

## OpenAPI Spec

Machine-readable spec at: `https://hydra-api-nlnj.onrender.com/openapi.json`

## Source

[github.com/OGCryptoKitty/hydra-arm3](https://github.com/OGCryptoKitty/hydra-arm3)
