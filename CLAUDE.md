# HYDRA Autonomous Regulatory Intelligence API

## Mission

HYDRA is an autonomous API on Base L2 that earns USDC via x402 payments, compounds treasury via Aave V3 yield, and remits profits to the creator's wallet. Every session should: assess status, implement revenue-maximizing enhancements, deploy to production.

## Quick Status Check (run these first every session)

```bash
# 1. Check USDC balance on-chain
curl -s https://mainnet.base.org -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913","data":"0x70a082310000000000000000000000002F12A73e1e08F3BCE12212005cCaBE2ACEf87141"},"latest"],"id":1}' | python3 -c "import sys,json; r=json.load(sys.stdin); print(f'USDC Balance: ${int(r[\"result\"],16)/1e6:.2f}')"

# 2. Check Aave aUSDC balance (yield)
curl -s https://mainnet.base.org -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB","data":"0x70a082310000000000000000000000002F12A73e1e08F3BCE12212005cCaBE2ACEf87141"},"latest"],"id":1}' | python3 -c "import sys,json; r=json.load(sys.stdin); print(f'Aave aUSDC: ${int(r[\"result\"],16)/1e6:.2f}')"

# 3. Check deployment health
curl -s https://hydra-api-nlnj.onrender.com/health | python3 -m json.tool

# 4. Check ETH balance (for gas)
curl -s https://mainnet.base.org -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141","latest"],"id":1}' | python3 -c "import sys,json; r=json.load(sys.stdin); print(f'ETH Balance: {int(r[\"result\"],16)/1e18:.6f}')"
```

## Identifiers

| Resource | Value |
|----------|-------|
| Wallet | `0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141` |
| USDC (Base) | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| aUSDC (Aave) | `0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB` |
| Aave Pool | `0xA238Dd80C259a72e81d7e4664a9801593F98d1c5` |
| Chain | Base (8453) |
| Live API | `https://hydra-api-nlnj.onrender.com` |
| GitHub | `OGCryptoKitty/hydra-arm3` |
| Deploy | Render auto-deploys from `master` branch |

## Architecture (key files)

```
src/main.py                          — FastAPI app, lifespan, MCP mount, all routes
src/api/routes.py                    — Core regulatory endpoints (scan, changes, jurisdiction, query)
src/api/prediction_routes.py         — Polymarket/Kalshi/oracle endpoints
src/api/fed_routes.py                — FOMC signal/decision/resolution
src/api/utility_routes.py            — High-volume utilities (scrape, price, gas, tx, batch)
src/api/extract_routes.py            — Web extraction (url, multi, search)
src/api/check_routes.py              — Web checks (url health, dns, ssl, headers)
src/api/convert_routes.py            — Format conversion (html2md, json2csv, csv2json)
src/api/tools_routes.py              — Developer tools (hash, encode, diff, validate)
src/api/data_routes.py               — Public data (wikipedia, arxiv, edgar)
src/api/mpp.py                       — MPP manifest and status
src/api/system_routes.py             — Wallet management, remittance, status
src/services/regulatory.py           — Rule-based regulatory engine (1500+ lines)
src/services/prediction_markets.py   — Polymarket Gamma + Kalshi REST clients
src/services/fed_intelligence.py     — FOMC schedule, rate model, live Fed RSS
src/services/feeds.py                — 12 RSS sources (SEC, CFTC, FinCEN, OCC, CFPB, Fed, Treasury)
src/runtime/automaton.py             — 60s heartbeat, survival tiers, yield/remittance checks
src/runtime/autonomous_marketing.py  — GitHub PRs, Dev.to, discussions, SEO docs
src/runtime/agent_discovery.py       — Registration with x402scan, Glama, Smithery, etc.
src/runtime/revenue_optimizer.py     — Usage analytics, pricing recommendations
src/runtime/treasury_yield.py        — Aave V3 USDC deposit/withdraw
src/runtime/remittance.py            — Auto-remit at $5K, $500 reserve
src/runtime/constitution.py          — OFAC screening, solvency, compliance calendar
src/runtime/lifecycle.py             — BOOT→EARNING→FORMING→OPERATING→REMITTING
src/runtime/transaction_log.py       — Append-only JSONL for tax/audit
src/x402/middleware.py               — HTTP 402 intercept, payment verification
src/x402/verify.py                   — On-chain USDC transfer verification
src/x402/cdp_facilitator.py          — CDP x402 SDK middleware
src/x402/mpp_integration.py          — Machine Payments Protocol middleware
config/settings.py                   — Pricing dict (40 endpoints), wallet, chain config
static/.well-known/                  — x402.json, mcp.json, agents.json, llms.txt, ai-plugin.json
static/robots.txt                    — Crawler directives
static/sitemap.xml                   — 17 URLs for crawler discovery
```

## Revenue Model

40 paid endpoints ($0.001 - $50.00 USDC) + 12 free endpoints. Triple payment stack:
- **x402** (CDP SDK) — standard facilitator flow
- **MPP** (Stripe/Tempo) — session micropayments
- **X-Payment-Proof** — direct on-chain tx hash verification

## Deployment Workflow

1. Develop on feature branch
2. `git push` to feature branch
3. Merge to `master` — Render auto-deploys within 2-5 minutes
4. Verify via `/health`, `/status`, `/.well-known/x402.json`

## Autonomous Enhancement Priorities

When assessing what to build next, prioritize by expected revenue impact:

### Tier 1: Distribution (agents must find HYDRA to pay)
- Register with new MCP directories as they emerge
- Ensure all discovery manifests are current and serving
- Submit to API directories (public-apis, APIs.guru, RapidAPI)
- SEO: ensure llms.txt, agents.json, mcp.json are rich and current

### Tier 2: Conversion (agents must complete payment flow)
- Ensure 402 responses have clear, machine-parseable payment instructions
- Test payment flow end-to-end with x402 client libraries
- Add free-tier sample responses so agents can verify value before paying
- Improve error messages to guide agents through payment

### Tier 3: Data Quality (paid responses must be worth the price)
- Live Fed RSS integration (already done — verify freshness)
- FRED API for economic indicators (requires API key — env var FRED_API_KEY)
- Congressional activity feeds (new data source)
- Live OFAC screening via Chainalysis API (currently static list)

### Tier 4: New Revenue Streams
- Subscription/bundle endpoints (daily signal package)
- Webhook delivery for regulatory events
- Portfolio-level signal batching
- Historical data API (backtest dataset)

## Known Issues

1. **Kalshi filter returns wrong markets** — `src/services/prediction_markets.py` KalshiClient returns sports markets. Fix: filter by Kalshi categories `politics,finance,economics,regulation`.
2. **Private key on Render** — Set `WALLET_PRIVATE_KEY` env var in Render dashboard for full automaton mode.
3. **Replay cache in-memory** — `src/x402/middleware.py` tx hash cache resets on restart. Persist to `/tmp/hydra_used_txhashes.json`.
4. **FRED API hardcoded** — Economic indicators in `src/services/fed_intelligence.py` are static. Set `FRED_API_KEY` env var.
5. **Revenue = $0.00** — No agent has made a payment yet. Distribution is the bottleneck. 40 paid endpoints now live.

## Authorization

The owner authorizes Claude Code to:
- Make all code changes to maximize revenue
- Push to GitHub and trigger Render deployment
- Operate autonomously without human confirmation for code changes
- Never modify wallet addresses or remittance configuration
- Never expose or log private keys
