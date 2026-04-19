# HYDRA Arm 3 — Regulatory Intelligence SaaS

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/OGCryptoKitty/hydra-arm3)

Production-ready regulatory intelligence API. Pay-per-use in **USDC on Base** via the **x402** HTTP payment protocol. Zero AI dependency — all endpoints are rule-based and deterministic.

**Live:** [hydra-api-nlnj.onrender.com](https://hydra-api-nlnj.onrender.com) | **Docs:** [/docs](https://hydra-api-nlnj.onrender.com/docs) | **x402 Discovery:** [/.well-known/x402.json](https://hydra-api-nlnj.onrender.com/.well-known/x402.json)

## MCP Server

HYDRA exposes all 22 paid + 12 free endpoints as MCP tools via [Model Context Protocol](https://modelcontextprotocol.io).

**Server URL:** `https://hydra-api-nlnj.onrender.com/mcp`
**Transport:** Streamable HTTP
**Manifest:** [/.well-known/mcp.json](https://hydra-api-nlnj.onrender.com/.well-known/mcp.json)

```json
{
  "mcpServers": {
    "hydra": {
      "url": "https://hydra-api-nlnj.onrender.com/mcp"
    }
  }
}
```

### MCP Tools (22 paid + 12 free)

| Tool | Price | Description |
|------|-------|-------------|
| `crypto_price` | $0.001 | Token price, 24h change, market cap |
| `gas_prices` | $0.001 | Base L2 gas prices with cost estimates |
| `wallet_balance` | $0.001 | ETH and USDC balance on Base |
| `tx_status` | $0.001 | Transaction receipt lookup |
| `parse_rss` | $0.002 | RSS/Atom feed to structured JSON |
| `scrape_url` | $0.005 | URL to clean structured text |
| `batch_utility` | $0.01 | Batch up to 5 utility calls |
| `market_feed` | $0.10 | Last 10 regulatory events for prediction markets |
| `market_events` | $0.50 | Classified regulatory events by agency |
| `regulatory_changes` | $1.00 | Recent classified regulatory changes |
| `regulatory_query` | $1.00 | Regulatory Q&A with statutory citations |
| `regulatory_scan` | $2.00 | Full regulatory risk scan |
| `market_signal` | $2.00 | Scored regulatory signal for one market |
| `regulatory_jurisdiction` | $3.00 | Jurisdiction comparison with cost modeling |
| `fed_signal` | $5.00 | Pre-FOMC signal with rate probabilities |
| `market_signals` | $5.00 | Bulk scored signals for all markets |
| `oracle_uma` | $5.00 | UMA Optimistic Oracle assertion data |
| `oracle_chainlink` | $5.00 | Chainlink External Adapter response |
| `alpha_report` | $10.00 | Premium alpha with Kelly sizing |
| `fed_decision` | $25.00 | Real-time FOMC decision classification |
| `market_resolution` | $25.00 | Resolution verdict for market settlement |
| `fed_resolution` | $50.00 | FOMC resolution verdict for oracle submission |

Payment: USDC on Base (chain 8453) via x402 protocol.

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

| Protocol | URL |
|----------|-----|
| **x402 Manifest** | [`/.well-known/x402.json`](https://hydra-api-nlnj.onrender.com/.well-known/x402.json) |
| **MCP Manifest** | [`/.well-known/mcp.json`](https://hydra-api-nlnj.onrender.com/.well-known/mcp.json) |
| **MCP Server** | [`/mcp`](https://hydra-api-nlnj.onrender.com/mcp) |
| **A2A Agent Card** | [`/.well-known/agent.json`](https://hydra-api-nlnj.onrender.com/.well-known/agent.json) |
| **LLMs.txt** | [`/.well-known/llms.txt`](https://hydra-api-nlnj.onrender.com/.well-known/llms.txt) |
| **AI Plugin** | [`/.well-known/ai-plugin.json`](https://hydra-api-nlnj.onrender.com/.well-known/ai-plugin.json) |
| **OpenAPI** | [`/openapi.json`](https://hydra-api-nlnj.onrender.com/openapi.json) |
| **APIs.json** | [`/apis.json`](https://hydra-api-nlnj.onrender.com/apis.json) |
| **Sitemap** | [`/sitemap.xml`](https://hydra-api-nlnj.onrender.com/sitemap.xml) |

## License

Proprietary — HYDRA Systems LLC
