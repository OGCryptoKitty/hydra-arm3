# HYDRA Arm 3 — Regulatory Intelligence SaaS

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/OGCryptoKitty/hydra-arm3)

Production-ready regulatory intelligence API. Pay-per-use in **USDC on Base** via the **x402** HTTP payment protocol. Zero AI dependency — all endpoints are rule-based and deterministic.

**Live:** [hydra-api-nlnj.onrender.com](https://hydra-api-nlnj.onrender.com) | **Docs:** [/docs](https://hydra-api-nlnj.onrender.com/docs) | **x402 Discovery:** [/.well-known/x402.json](https://hydra-api-nlnj.onrender.com/.well-known/x402.json)

## Endpoints &amp; Pricing

### Regulatory Intelligence
| Method | Endpoint | Price | Description |
|--------|----------|-------|-------------|
| POST | `/v1/regulatory/scan` | $2.00 | Full regulatory risk scan with scored impact assessment |
| POST | `/v1/regulatory/changes` | $1.00 | SEC, CFTC, FinCEN, OCC, CFPB classified filings |
| POST | `/v1/regulatory/jurisdiction` | $3.00 | Jurisdiction comparison across US states + international |
| POST | `/v1/regulatory/query` | $1.00 | Regulatory Q&amp;A with statutory citations |

### Prediction Market Signals
| Method | Endpoint | Price | Description |
|--------|----------|-------|-------------|
| GET | `/v1/markets` | FREE | All active regulatory prediction markets |
| GET | `/v1/markets/discovery` | FREE | Market discovery with HYDRA domain coverage |
| GET | `/v1/markets/pricing` | FREE | Endpoint pricing for bots |
| GET | `/v1/markets/feed` | $0.10 | High-frequency micro event feed (bot polling) |
| POST | `/v1/markets/events` | $0.50 | Classified regulatory events matched to markets |
| POST | `/v1/markets/signal/{id}` | $2.00 | Deep signal for one prediction market |
| POST | `/v1/markets/signals` | $5.00 | Bulk signals for all active markets |
| POST | `/v1/markets/alpha` | $10.00 | Premium alpha report with Kelly sizing |
| POST | `/v1/markets/resolution` | $25.00 | Oracle-grade resolution verdict |

### Fed Decision Package
| Method | Endpoint | Price | Description |
|--------|----------|-------|-------------|
| POST | `/v1/fed/signal` | $5.00 | Pre-FOMC signal with rate probability model |
| POST | `/v1/fed/decision` | $25.00 | Real-time FOMC decision classification |
| POST | `/v1/fed/resolution` | $50.00 | FOMC resolution verdict for oracles (UMA/Chainlink) |

### Oracle Integration
| Method | Endpoint | Price | Description |
|--------|----------|-------|-------------|
| POST | `/v1/oracle/uma` | $5.00 | UMA Optimistic Oracle assertion data |
| POST | `/v1/oracle/chainlink` | $5.00 | Chainlink External Adapter format |

### Free System Endpoints
`GET /health` · `GET /pricing` · `GET /docs` · `GET /openapi.json` · `GET /metrics` · `GET /metrics/revenue`

## x402 Payment Flow

```
1. POST /v1/regulatory/scan → 402 Payment Required
   Response includes: amount, wallet, chain_id, x402 machine-readable block

2. Send USDC to 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141 on Base (chain 8453)

3. POST /v1/regulatory/scan + Header: X-Payment-Proof: 0x{tx_hash}
   → 200 OK (payment verified on-chain via Base RPC)
```

All payments are **final**. USDC on Base L2 is a permissionless transfer with no clawback.

## Bot Integration

```bash
# 1. Discover markets (free)
curl https://hydra-api-nlnj.onrender.com/v1/markets/discovery

# 2. Check pricing (free)
curl https://hydra-api-nlnj.onrender.com/v1/markets/pricing

# 3. Poll feed every 5 min ($0.10 each)
curl -H "X-Payment-Proof: 0x..." https://hydra-api-nlnj.onrender.com/v1/markets/feed

# 4. Get signals before trading ($5.00)
curl -X POST -H "X-Payment-Proof: 0x..." -H "Content-Type: application/json" \
  -d '{"platform":"all","category":"all"}' \
  https://hydra-api-nlnj.onrender.com/v1/markets/signals
```

## Deploy

### One-Click (Render)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/OGCryptoKitty/hydra-arm3)

The `render.yaml` blueprint auto-configures everything. After connecting, every push to master auto-deploys.

### Local

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn src.main:app --host 0.0.0.0 --port 8402
```

### Docker

```bash
docker-compose up
```

## Architecture

- **FastAPI** async API with x402 payment middleware
- **Web3.py** on-chain USDC payment verification via Base RPC
- **HydraAutomaton** — autonomous heartbeat (balance checks, lifecycle, remittance, keepalive)
- **ConstitutionCheck** — three-law compliance (OFAC, solvency, filing deadlines)
- **TransactionLog** — append-only JSONL audit trail for tax compliance
- **Rule-based engines** — all endpoints are deterministic, zero LLM dependency

## Market Coverage

- **Polymarket**: ~110 active regulation markets
- **Kalshi**: Fed funds rate (KXFED), crypto market structure, GENIUS Act, SEC
- **UMA Optimistic Oracle**: Assertion data for bond posting
- **Chainlink**: External Adapter format for on-chain delivery

## Payment Verification

1. Fetch transaction receipt from Base mainnet RPC
2. Parse ERC-20 `Transfer` events from USDC contract
3. Confirm recipient = treasury wallet, amount >= required
4. Cache tx hash for 24h (replay prevention)
5. Attach `X-Payment-Verified: true` header to response

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WALLET_ADDRESS` | `0x2F12...141` | USDC recipient wallet |
| `BASE_RPC_URL` | `https://mainnet.base.org` | Base L2 RPC |
| `HYDRA_STATE_DIR` | `/tmp/hydra-data` | State persistence directory |
| `PORT` | `8402` | Server port |
| `DEBUG` | `false` | Verbose logging |

## Discovery

- **AI Plugins**: `/.well-known/ai-plugin.json` (ChatGPT, Claude, Copilot)
- **x402 Protocol**: `/.well-known/x402.json`
- **OpenAPI**: `/openapi.json`
- **APIs.json**: `/static/apis.json`

## License

Proprietary — HYDRA Systems LLC
