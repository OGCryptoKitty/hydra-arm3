# HYDRA Arm 3 — Regulatory Intelligence SaaS

A production-ready regulatory compliance analysis API. Pay-per-use in USDC on Base via the **x402** HTTP payment protocol.

## What It Does

| Endpoint | Price | Description |
|---|---|---|
| `POST /v1/regulatory/scan` | $1.00 USDC | Full regulatory risk scan — matches business to applicable regulations, risk score, recommended actions |
| `POST /v1/regulatory/changes` | $0.50 USDC | Recent regulatory changes from SEC, CFTC, FinCEN, OCC, CFPB RSS feeds |
| `POST /v1/regulatory/jurisdiction` | $2.00 USDC | Jurisdiction comparison across US states (WY, DE, NV, NY, TX) and international (EU, UK, SG) |
| `POST /v1/regulatory/query` | $0.50 USDC | Regulatory Q&A — natural language queries answered from structured knowledge base |

Free endpoints: `GET /health`, `GET /pricing`, `GET /docs`

## x402 Payment Flow

```
1. Client → POST /v1/regulatory/scan
                          ↓
2. Server ← 402 Payment Required
   Headers: X-Payment-Required, X-Payment-Amount, X-Payment-Address, X-Payment-Network
   Body:    { payment: { amount_usdc, amount_base_units, wallet_address, chain_id }, retry_instructions }

3. Client → Send 1.00 USDC to 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141 on Base (chain 8453)

4. Client → POST /v1/regulatory/scan
   Header: X-Payment-Proof: 0x<tx_hash>
                          ↓
5. Server verifies tx on Base (checks USDC Transfer event on-chain)
                          ↓
6. Server ← 200 OK + response
   Headers: X-Payment-Verified: true, X-Payment-Tx: 0x...
```

## Quick Start

### Local (Python)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env if needed (defaults work out of the box)

# 3. Start server
uvicorn src.main:app --host 0.0.0.0 --port 8402
```

### Docker

```bash
# Production
docker-compose up

# Development (auto-reload)
docker-compose --profile dev up hydra-arm3-dev
```

The server starts on **port 8402** (HTTP 402 reference).

## Example Usage

### Check pricing (free)
```bash
curl http://localhost:8402/pricing
```

### Regulatory scan with payment
```bash
# Step 1: Get payment instructions
curl -X POST http://localhost:8402/v1/regulatory/scan \
  -H "Content-Type: application/json" \
  -d '{"business_description": "A DeFi lending protocol for US users with governance tokens", "jurisdiction": "US"}'
# Returns 402 with wallet address and amount

# Step 2: Send 1.00 USDC to the wallet on Base
# Step 3: Retry with tx hash
curl -X POST http://localhost:8402/v1/regulatory/scan \
  -H "Content-Type: application/json" \
  -H "X-Payment-Proof: 0x<your_tx_hash>" \
  -d '{"business_description": "A DeFi lending protocol for US users with governance tokens", "jurisdiction": "US"}'
```

### Jurisdiction comparison with payment
```bash
curl -X POST http://localhost:8402/v1/regulatory/jurisdiction \
  -H "Content-Type: application/json" \
  -H "X-Payment-Proof: 0x<your_tx_hash>" \
  -d '{"jurisdictions": ["WY", "DE", "NY", "EU"], "business_type": "crypto"}'
```

### Regulatory Q&A with payment
```bash
curl -X POST http://localhost:8402/v1/regulatory/query \
  -H "Content-Type: application/json" \
  -H "X-Payment-Proof: 0x<your_tx_hash>" \
  -d '{"question": "Do I need a money transmitter license in Wyoming to operate a crypto exchange?"}'
```

## Architecture

```
hydra-arm3/
├── config/
│   └── settings.py          # Environment config, pricing tiers, chain constants
├── src/
│   ├── main.py              # FastAPI app — middleware stack, lifespan, error handlers
│   ├── api/
│   │   └── routes.py        # Route handlers (health, pricing, 4 paid endpoints)
│   ├── models/
│   │   └── schemas.py       # Pydantic request/response models
│   ├── services/
│   │   ├── regulatory.py    # Rule-based regulatory intelligence engine
│   │   └── feeds.py         # RSS feed aggregator (SEC/CFTC/FinCEN/OCC/CFPB)
│   └── x402/
│       ├── middleware.py    # x402 payment middleware (FastAPI BaseHTTPMiddleware)
│       └── verify.py        # On-chain USDC payment verification via Base RPC
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Payment Verification

Payments are verified by:
1. Connecting to Base mainnet via `BASE_RPC_URL`
2. Fetching the transaction receipt for the provided tx hash
3. Parsing ERC-20 `Transfer(address,address,uint256)` events from the USDC contract (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)
4. Confirming the recipient matches `WALLET_ADDRESS` and `value >= required_amount`
5. Caching the used tx hash for 24 hours (replay prevention)

## Regulatory Knowledge Base

Covers:
- **Federal**: Securities Act 1933, Exchange Act 1934, Investment Company Act 1940, Investment Advisers Act 1940, Commodity Exchange Act, Bank Secrecy Act, FinCEN CDD Rule, TILA/Reg Z
- **State**: Wyoming (DAO LLC, SPDI, MTL exemption), Delaware (DGCL), Nevada (Blockchain Act), New York (BitLicense, Martin Act), Texas
- **International**: EU MiCA, EU GDPR/PSD2/MiFID II, UK FCA/FSMA, Singapore MAS/PSA

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `WALLET_ADDRESS` | `0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141` | USDC recipient wallet |
| `BASE_RPC_URL` | `https://mainnet.base.org` | Base L2 RPC endpoint |
| `USDC_CONTRACT_ADDRESS` | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | USDC on Base mainnet |
| `DEBUG` | `false` | Enable verbose logging |
| `PORT` | `8402` | Server port |
| `FEED_CACHE_TTL` | `3600` | Feed cache TTL in seconds |
| `PAYMENT_CACHE_TTL` | `86400` | Used tx hash cache TTL in seconds |

## Disclaimer

This application is for informational purposes only and does not constitute legal advice.
