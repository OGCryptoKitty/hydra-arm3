# HYDRA — Registry & Directory Submissions

Ready-to-paste issue bodies and registration steps for all distribution channels.

---

## 1. x402-payment-harness — Listing Request

**Repo**: `rplryan/x402-payment-harness`
**Action**: Open new issue

**Title**: `Add HYDRA Regulatory Intelligence to x402 ecosystem examples`

**Body**:
```
HYDRA is a live x402-native API on Base L2 with 22 paid endpoints ($0.001 - $50.00 USDC).

**Live API**: https://hydra-api-nlnj.onrender.com
**x402 Manifest**: https://hydra-api-nlnj.onrender.com/.well-known/x402.json
**MCP Server**: https://hydra-api-nlnj.onrender.com/mcp
**GitHub**: https://github.com/OGCryptoKitty/hydra-arm3

Payment config:
- Network: Base (chain 8453)
- Token: USDC (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)
- Wallet: 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141
- Facilitator: https://x402.org/facilitator

HYDRA uses x402-payment-harness for agent payment demos. Would be great to be listed
as an ecosystem example of a production x402 service.
```

---

## 2. awesome-x402 — Listing Request

**Repo**: `xpaysh/awesome-x402`
**Action**: Open new issue

**Title**: `Add HYDRA Regulatory Intelligence — live x402 API with 22 endpoints`

**Body**:
```
**HYDRA Regulatory Intelligence** — Autonomous regulatory intelligence API for prediction markets.

- 22 paid x402 endpoints ($0.001 - $50.00 USDC on Base L2)
- SEC, CFTC, Fed, FinCEN monitoring
- Polymarket/Kalshi signal generation
- UMA and Chainlink oracle data
- MCP server for 300+ AI clients

**Links**:
- API: https://hydra-api-nlnj.onrender.com
- x402 manifest: https://hydra-api-nlnj.onrender.com/.well-known/x402.json
- Docs: https://hydra-api-nlnj.onrender.com/docs
- GitHub: https://github.com/OGCryptoKitty/hydra-arm3

Suggested category: **Services / APIs** or **Finance / Regulatory**
```

---

## 3. gold-402 — Listing Request

**Repo**: `Haustorium12/gold-402`
**Action**: Open new issue

**Title**: `Add HYDRA Regulatory Intelligence to gold-402 directory`

**Body**:
```
HYDRA is a production x402 API on Base L2 providing regulatory intelligence for prediction markets.

**Endpoints**: 22 paid ($0.001 - $50.00 USDC) + 12 free
**Payment**: x402 + MPP + direct X-Payment-Proof
**Network**: Base (chain 8453), USDC
**Wallet**: 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141

**API**: https://hydra-api-nlnj.onrender.com
**x402 manifest**: https://hydra-api-nlnj.onrender.com/.well-known/x402.json
**MCP server**: https://hydra-api-nlnj.onrender.com/mcp
**GitHub**: https://github.com/OGCryptoKitty/hydra-arm3

Categories: Regulatory, Prediction Markets, Oracle Data, DeFi
```

---

## 4. x402scan.com — Direct Registration

**URL**: https://www.x402scan.com/resources/register

Submit `https://hydra-api-nlnj.onrender.com` via the web form. The validator fetches a paid endpoint, verifies the 402 response includes valid x402 schema, and auto-indexes.

---

## 5. EntRoute / x402 Discovery API — Programmatic Registration

**Endpoint**: `POST https://x402-discovery-api.onrender.com/register`

Register each HYDRA endpoint individually:

```bash
# Regulatory scan ($2.00)
curl -X POST https://x402-discovery-api.onrender.com/register \
  -H "Content-Type: application/json" \
  -d '{"name":"HYDRA Regulatory Scan","url":"https://hydra-api-nlnj.onrender.com/v1/regulatory/scan","price_usd":2.00,"category":"data","description":"Regulatory risk scoring for crypto/DeFi","network":"base-mainnet"}'

# Fed signal ($5.00)
curl -X POST https://x402-discovery-api.onrender.com/register \
  -H "Content-Type: application/json" \
  -d '{"name":"HYDRA Fed Signal","url":"https://hydra-api-nlnj.onrender.com/v1/fed/signal","price_usd":5.00,"category":"data","description":"Pre-FOMC signal with rate probabilities","network":"base-mainnet"}'

# Crypto price ($0.001)
curl -X POST https://x402-discovery-api.onrender.com/register \
  -H "Content-Type: application/json" \
  -d '{"name":"HYDRA Crypto Price","url":"https://hydra-api-nlnj.onrender.com/v1/util/crypto/price","price_usd":0.001,"category":"data","description":"Token price, 24h change, market cap","network":"base-mainnet"}'
```

---

## 6. Glama.ai — Submit GitHub Repository

**URL**: https://glama.ai/mcp/servers

Submit the GitHub repo URL: `https://github.com/OGCryptoKitty/hydra-arm3`

Glama auto-indexes all MCP tools from the repo. After indexing, "claim" the server to access analytics.

---

## 7. PulseMCP — Submit MCP Server

**URL**: https://www.pulsemcp.com (use Submit button in nav)

Submit your MCP server URL: `https://hydra-api-nlnj.onrender.com/mcp`

PulseMCP has 12,650+ servers. One of the largest hand-reviewed directories.

---

## 8. Smithery.ai — Publish MCP Server

**URL**: https://smithery.ai/new (sign in to publish)

Or via CLI:
```bash
npm install -g @smithery/cli
smithery mcp publish https://hydra-api-nlnj.onrender.com/mcp -n OGCryptoKitty/hydra-regulatory
```

---

## 9. x402.org Ecosystem — PR to Coinbase x402

**Repo**: `coinbase/x402`

Fork, add `app/ecosystem/partners-data/hydra-regulatory/metadata.json`:
```json
{
  "name": "HYDRA Regulatory Intelligence",
  "description": "Autonomous regulatory intelligence API with 22 x402 micropayment endpoints",
  "websiteUrl": "https://hydra-api-nlnj.onrender.com",
  "category": "Services/Endpoints"
}
```

---

## 10. APIs.guru — Submit OpenAPI Spec

**URL**: https://apis.guru/add-api

Submit: `https://hydra-api-nlnj.onrender.com/openapi.json`

---

## Priority Order

| # | Channel | Effort | Impact |
|---|---------|--------|--------|
| 1 | x402scan | 2 min | High — auto-indexes on valid 402 |
| 2 | EntRoute Discovery API | 5 min | High — 350+ verified x402 endpoints |
| 3 | Glama.ai | 5 min | High — 21K+ MCP servers |
| 4 | PulseMCP | 5 min | High — 12K+ MCP servers |
| 5 | Smithery.ai | 15 min | Medium — 7K+ tools |
| 6 | x402.org ecosystem PR | 30 min | Medium — official Coinbase listing |
| 7 | APIs.guru | 10 min | Low — general API directory |
