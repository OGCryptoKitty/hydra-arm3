<p align="center">
  <strong>HYDRA</strong><br>
  Autonomous Regulatory Intelligence API
</p>

<p align="center">
  <a href="https://hydra-api-nlnj.onrender.com/health"><img src="https://img.shields.io/badge/status-live-brightgreen?style=flat-square" alt="Live"></a>
  <a href="https://hydra-api-nlnj.onrender.com/.well-known/x402.json"><img src="https://img.shields.io/badge/x402-55%20endpoints-blue?style=flat-square" alt="x402 Endpoints"></a>
  <a href="https://hydra-api-nlnj.onrender.com/mcp"><img src="https://img.shields.io/badge/MCP-streamable%20HTTP-purple?style=flat-square" alt="MCP Server"></a>
  <a href="https://hydra-api-nlnj.onrender.com/docs"><img src="https://img.shields.io/badge/docs-OpenAPI-orange?style=flat-square" alt="API Docs"></a>
  <img src="https://img.shields.io/badge/chain-Base%20L2-0052FF?style=flat-square" alt="Base L2">
  <img src="https://img.shields.io/badge/token-USDC-2775CA?style=flat-square" alt="USDC">
  <a href="https://render.com/deploy?repo=https://github.com/OGCryptoKitty/hydra-arm3"><img src="https://img.shields.io/badge/deploy-Render-46E3B7?style=flat-square" alt="Deploy to Render"></a>
</p>

---

**HYDRA** is a pay-per-call regulatory intelligence API built for AI agents and prediction market traders. It combines 13 real-time government and market data sources into composite analytical products that do not exist anywhere else -- then sells them for USDC on Base L2 via the x402 payment protocol.

**Live API:** [hydra-api-nlnj.onrender.com](https://hydra-api-nlnj.onrender.com) | **Docs:** [/docs](https://hydra-api-nlnj.onrender.com/docs) | **x402 Manifest:** [/.well-known/x402.json](https://hydra-api-nlnj.onrender.com/.well-known/x402.json) | **MCP Server:** [/mcp](https://hydra-api-nlnj.onrender.com/mcp)

---

## Why HYDRA Exists

Prediction market traders and AI agents need regulatory signals. Right now that means scraping dozens of government RSS feeds, checking FOMC schedules, parsing SEC EDGAR filings, tracking Treasury yield curves, and pulling Kalshi/Polymarket prices -- then correlating all of it manually. HYDRA does this in one API call.

**For prediction market bots:** Get scored regulatory signals with Kelly sizing for Polymarket and Kalshi markets. HYDRA's FOMC model calibrates against Kalshi KXFED contract prices to produce rate probability distributions.

**For AI agents (Claude, GPT, etc.):** Connect via MCP and get structured regulatory data, economic indicators, web extraction, and format conversion -- all paid with USDC micropayments as low as $0.001.

**For compliance teams:** Real-time regulatory pulse across SEC, CFTC, FinCEN, OCC, CFPB, Fed, and Treasury with composite risk scoring.

---

## 13 Real-Time Data Sources

HYDRA pulls live data at request time from authoritative government and market sources:

| # | Source | Data | Update Frequency |
|---|--------|------|------------------|
| 1 | **FRED** (Federal Reserve Economic Data) | Fed funds rate, CPI, PCE, GDP, unemployment, VIX, yield spreads, breakeven inflation | 15 min cache / varies by series |
| 2 | **BLS** (Bureau of Labor Statistics) | Employment situation, CPI detail breakdowns | 15 min cache |
| 3 | **U.S. Treasury** (FiscalData API) | Daily yield curve rates, average interest rates, national debt | 5 min cache |
| 4 | **SEC EDGAR** (EFTS full-text search) | 10-K, 10-Q, 8-K filings, enforcement actions by company/ticker | 5 min cache |
| 5 | **Federal Register** API | New rulemakings, final rules, proposed rules across all agencies | 15 min cache |
| 6 | **FDIC** BankFind API | Bank failures, resolution details, loss estimates | 15 min cache |
| 7 | **SEC** RSS (4 feeds) | Press releases, litigation releases, proposed rules, final rules | 10 min cache |
| 8 | **CFTC** RSS | Press releases, enforcement actions | 10 min cache |
| 9 | **FinCEN** RSS | Advisories, enforcement, rulemakings | 10 min cache |
| 10 | **OCC** RSS | Interpretive letters, enforcement, guidance | 10 min cache |
| 11 | **CFPB** RSS | Consumer finance regulations, enforcement | 10 min cache |
| 12 | **Federal Reserve** RSS (3 feeds) | Monetary policy statements, banking regulation, speeches | 10 min cache |
| 13 | **Treasury** RSS | Press releases, sanctions, tax guidance | 10 min cache |

Plus market data from **Polymarket** (Gamma API) and **Kalshi** (REST API, including KXFED rate contracts).

---

## KXFED-Calibrated Fed Rate Probability Model

HYDRA's Fed intelligence engine produces FOMC rate probability distributions by combining:

1. **Kalshi KXFED contract prices** -- market-implied rate expectations from real-money prediction markets
2. **Economic indicator analysis** -- CPI, Core PCE, unemployment, nonfarm payrolls, GDP, Treasury yields
3. **Fed governor speech analysis** -- dove/hawk scoring of recent FOMC member public statements
4. **Dot plot tracking** -- median year-end rate projections and shifts between meetings
5. **FOMC calendar awareness** -- days to next meeting, blackout period detection

The model outputs `HOLD`, `CUT`, or `HIKE` probabilities with basis point estimates and confidence scores. This is the data product behind the `$5 /v1/fed/signal`, `$25 /v1/fed/decision`, and `$50 /v1/fed/resolution` endpoints.

---

## Quick Start

### Free endpoints (no payment required)

```bash
# Health check
curl -s https://hydra-api-nlnj.onrender.com/health | python3 -m json.tool

# All active regulatory prediction markets (Polymarket + Kalshi)
curl -s https://hydra-api-nlnj.onrender.com/v1/markets | python3 -m json.tool

# Market discovery -- see what HYDRA covers before paying
curl -s https://hydra-api-nlnj.onrender.com/v1/markets/discovery | python3 -m json.tool

# Full pricing table
curl -s https://hydra-api-nlnj.onrender.com/pricing | python3 -m json.tool

# x402 directory of registered services
curl -s https://hydra-api-nlnj.onrender.com/v1/x402/directory | python3 -m json.tool

# Automaton status (treasury, lifecycle, discovery)
curl -s https://hydra-api-nlnj.onrender.com/status | python3 -m json.tool
```

### Triggering a 402 payment challenge

```bash
# Any paid endpoint without payment returns 402 with machine-readable payment instructions
curl -s https://hydra-api-nlnj.onrender.com/v1/check/url?url=https://example.com | python3 -m json.tool
```

Response:
```json
{
  "error": "Payment Required",
  "amount": "0.005",
  "token": "USDC",
  "network": "base",
  "chain_id": 8453,
  "wallet": "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141",
  "instructions": "Send 0.005 USDC to the wallet on Base, then retry with X-Payment-Proof: 0x{tx_hash}"
}
```

### Paying for a call

```bash
# After sending USDC on Base, retry with the transaction hash
curl -s https://hydra-api-nlnj.onrender.com/v1/check/url?url=https://example.com \
  -H "X-Payment-Proof: 0x{your_tx_hash}" | python3 -m json.tool
```

---

## MCP Server (Claude Code, Claude Desktop, 300+ AI Clients)

HYDRA exposes all endpoints as MCP tools via [Model Context Protocol](https://modelcontextprotocol.io) over Streamable HTTP transport.

**Server URL:** `https://hydra-api-nlnj.onrender.com/mcp`

### Claude Code

```bash
claude mcp add --transport http hydra https://hydra-api-nlnj.onrender.com/mcp
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hydra": {
      "url": "https://hydra-api-nlnj.onrender.com/mcp"
    }
  }
}
```

### Any MCP Client

```json
{
  "name": "HYDRA",
  "url": "https://hydra-api-nlnj.onrender.com/mcp",
  "transport": "streamable-http"
}
```

---

## All Endpoints (55 Paid + 12 Free)

### Composite Intelligence -- unique to HYDRA

These products combine multiple data streams into signals that do not exist anywhere else.

| Endpoint | Price | Description |
|----------|-------|-------------|
| `GET /v1/intelligence/alpha` | $5.00 | Composite alpha signal -- regulatory risk + Fed rate probability + prediction market sentiment + RSS momentum |
| `GET /v1/intelligence/pulse` | $0.50 | Hourly regulatory pulse -- aggregated SEC/CFTC/FinCEN/OCC/CFPB/Fed/Treasury with composite risk score |
| `GET /v1/intelligence/risk-score` | $2.00 | Real-time 0-100 risk score for any token or protocol based on regulatory exposure |
| `GET /v1/intelligence/digest` | $1.00 | Daily market + regulatory digest for compliance teams and trading agents |
| `GET /v1/intelligence/economic-snapshot` | $0.50 | Atomic real-time economic data -- FRED, BLS, Treasury yields, Federal Register rulemakings |
| `GET /v1/intelligence/regulatory-pulse-live` | $0.50 | Live regulatory pulse -- SEC EDGAR search, Federal Register API, Congress bill tracker |
| `GET /v1/intelligence/bank-failures` | $0.25 | FDIC bank failure monitor -- recent failures, resolution details, losses |

### Fed Decision Package -- $80M+ volume per FOMC meeting

| Endpoint | Price | Description |
|----------|-------|-------------|
| `POST /v1/fed/signal` | $5.00 | Pre-FOMC signal -- KXFED-calibrated rate probabilities, speech analysis, economic indicators |
| `POST /v1/fed/decision` | $25.00 | Real-time FOMC decision classification -- HOLD/CUT/HIKE within 30 seconds of release |
| `POST /v1/fed/resolution` | $50.00 | FOMC resolution verdict with evidence chain -- formatted for UMA bond assertion |

### Prediction Market Signals -- Polymarket + Kalshi

| Endpoint | Price | Description |
|----------|-------|-------------|
| `GET /v1/markets/feed` | $0.10 | Micro event feed -- last 10 regulatory events matched to prediction markets (high-frequency polling) |
| `GET /v1/markets/events` | $0.50 | Classified regulatory events by agency, type, and affected prediction markets |
| `POST /v1/markets/signal` | $2.00 | Scored signal for one prediction market -- HYDRA probability, expected price impact |
| `POST /v1/markets/signals` | $5.00 | Bulk signals for all active regulatory markets |
| `POST /v1/markets/alpha` | $10.00 | Premium alpha report -- Kelly sizing, entry price, historical analogues, trade verdict |
| `POST /v1/markets/resolution` | $25.00 | Resolution verdict for prediction market settlement with evidence chain |

### Oracle Integration -- on-chain data delivery

| Endpoint | Price | Description |
|----------|-------|-------------|
| `POST /v1/oracle/uma` | $5.00 | UMA Optimistic Oracle assertion data -- evidence chain, proposed price, bond parameters |
| `POST /v1/oracle/chainlink` | $5.00 | Chainlink External Adapter response -- regulatory data formatted for on-chain delivery |

### Regulatory Intelligence -- 1500+ line rule engine

| Endpoint | Price | Description |
|----------|-------|-------------|
| `POST /v1/regulatory/scan` | $2.00 | Full regulatory risk scan against all applicable frameworks with scored impact assessment |
| `GET /v1/regulatory/changes` | $1.00 | Recent classified changes from SEC, CFTC, FinCEN, OCC, CFPB with market impact scores |
| `POST /v1/regulatory/jurisdiction` | $3.00 | Jurisdiction comparison with compliance cost modeling across US states |
| `POST /v1/regulatory/query` | $1.00 | Regulatory Q&A with statutory citations and confidence levels |

### Portfolio Intelligence

| Endpoint | Price | Description |
|----------|-------|-------------|
| `POST /v1/portfolio/scan` | $10.00 | Portfolio-level regulatory risk scan -- up to 20 tokens/protocols with aggregate risk |
| `POST /v1/portfolio/watchlist` | $2.00 | Portfolio regulatory watchlist -- recent agency mentions and alert levels |
| `GET /v1/portfolio/market-brief` | $3.00 | Executive market brief -- regulatory events + Fed signal + prediction markets |
| `POST /v1/orchestrate` | $0.05 | Multi-step task orchestration -- execute up to 10 HYDRA endpoint calls in one request |

### Push Alerts

| Endpoint | Price | Description |
|----------|-------|-------------|
| `POST /v1/alerts/subscribe` | $0.10 | Register for push alerts -- webhook delivery of regulatory events ($0.10 per 100 alerts) |
| `GET /v1/alerts/feed` | $0.05 | Real-time regulatory alert feed -- last 24 hours of detected events |

### x402 Ecosystem Hub

| Endpoint | Price | Description |
|----------|-------|-------------|
| `POST /v1/x402/route` | $0.001 | Intelligent x402 service routing -- find the best service for a capability request |
| `GET /v1/x402/status` | $0.005 | Health and capability check of any x402 service |

### Extraction & Search

| Endpoint | Price | Description |
|----------|-------|-------------|
| `POST /v1/extract/url` | $0.01 | Structured web extraction -- title, headings, text, links, metadata |
| `POST /v1/extract/search` | $0.02 | Web search with structured result extraction |
| `POST /v1/extract/multi` | $0.05 | Batch extraction from up to 5 URLs in parallel |

### Web Checks

| Endpoint | Price | Description |
|----------|-------|-------------|
| `GET /v1/check/url` | $0.005 | URL health -- status code, redirects, response time |
| `GET /v1/check/dns` | $0.005 | DNS records -- A, AAAA, MX, TXT, NS, CNAME |
| `GET /v1/check/ssl` | $0.005 | SSL certificate -- issuer, expiry, SANs, days remaining |
| `GET /v1/check/headers` | $0.003 | HTTP headers with security analysis and score |

### Format Conversion

| Endpoint | Price | Description |
|----------|-------|-------------|
| `POST /v1/convert/html2md` | $0.005 | HTML to Markdown -- headings, lists, links, code, tables |
| `POST /v1/convert/json2csv` | $0.003 | JSON array to CSV with auto-detected headers |
| `POST /v1/convert/csv2json` | $0.003 | CSV text to JSON array |

### Developer Tools

| Endpoint | Price | Description |
|----------|-------|-------------|
| `POST /v1/tools/hash` | $0.001 | SHA-256, SHA-512, MD5, SHA-1, SHA3-256 |
| `POST /v1/tools/encode` | $0.001 | Base64, URL, hex encode/decode |
| `POST /v1/tools/diff` | $0.003 | Unified diff with change stats and similarity |
| `POST /v1/tools/validate/json` | $0.001 | JSON validation with pretty-print |
| `POST /v1/tools/validate/email` | $0.002 | Email format + MX record check |

### Public Data

| Endpoint | Price | Description |
|----------|-------|-------------|
| `GET /v1/data/wikipedia` | $0.01 | Wikipedia article summary with thumbnail |
| `GET /v1/data/arxiv` | $0.02 | arXiv paper search -- authors, abstracts, PDFs |
| `GET /v1/data/edgar` | $0.02 | SEC EDGAR filing search -- 10-K, 10-Q, 8-K |

### Agent Utilities

| Endpoint | Price | Description |
|----------|-------|-------------|
| `GET /v1/util/crypto/price` | $0.001 | Token price, 24h change, market cap |
| `GET /v1/util/gas` | $0.001 | Base L2 gas prices with cost estimates |
| `GET /v1/util/crypto/balance` | $0.001 | ETH and USDC balance on Base |
| `GET /v1/util/tx` | $0.001 | Transaction receipt lookup |
| `GET /v1/util/rss` | $0.002 | RSS/Atom feed to structured JSON |
| `GET /v1/util/scrape` | $0.005 | URL to clean structured text |
| `POST /v1/batch` | $0.01 | Batch up to 5 utility calls |

### Free Endpoints (no payment required)

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Application health and automaton snapshot |
| `GET /status` | Full automaton status -- treasury, yield, lifecycle, discovery |
| `GET /pricing` | Complete pricing table for all endpoints |
| `GET /metrics` | Operational metrics -- uptime, transaction counts, endpoint count |
| `GET /metrics/revenue` | Revenue analytics -- per-endpoint breakdown |
| `GET /v1/markets` | All active regulatory prediction markets (Polymarket + Kalshi) |
| `GET /v1/markets/discovery` | Market discovery -- coverage breadth before purchasing signals |
| `GET /v1/x402/directory` | x402 service directory |
| `GET /v1/x402/stats` | x402 ecosystem statistics |
| `GET /v1/alerts/status` | Alert system status |
| `GET /docs` | Interactive OpenAPI documentation |
| `GET /openapi.json` | OpenAPI 3.1 specification |

---

## x402 Payment Flow

```
1. Call any paid endpoint
   --> 402 Payment Required
   Response includes: amount, wallet, chain_id, token, machine-readable x402 block

2. Send USDC to 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141 on Base (chain 8453)

3. Retry with one of three payment headers:
   - X-Payment-Proof: 0x{tx_hash}     (direct on-chain verification)
   - X-PAYMENT: {x402 payment blob}   (CDP SDK standard flow)
   - Authorization: Payment {mpp}     (MPP session-based micropayments)
   --> 200 OK (payment verified on-chain via Base RPC)
```

HYDRA supports three payment methods simultaneously:
- **x402** (CDP SDK) -- standard facilitator flow for agent wallets
- **X-Payment-Proof** -- direct on-chain tx hash verification (simplest)
- **MPP** (Machine Payments Protocol) -- session-based micropayments via Stripe/Tempo

---

## Architecture

```
src/main.py                          -- FastAPI app, lifespan, MCP mount, all routes
src/api/intelligence_routes.py       -- Composite intelligence products (alpha, pulse, risk, digest)
src/api/fed_routes.py                -- FOMC signal/decision/resolution
src/api/prediction_routes.py         -- Polymarket/Kalshi/oracle endpoints
src/api/routes.py                    -- Core regulatory endpoints (scan, changes, jurisdiction, query)
src/api/portfolio_routes.py          -- Portfolio scan, watchlist, market brief, orchestration
src/api/alert_routes.py              -- Push alert subscription and feed
src/api/utility_routes.py            -- High-volume utilities (scrape, price, gas, tx, batch)
src/api/extract_routes.py            -- Web extraction (url, multi, search)
src/api/check_routes.py              -- Web checks (url health, dns, ssl, headers)
src/api/convert_routes.py            -- Format conversion (html2md, json2csv, csv2json)
src/api/tools_routes.py              -- Developer tools (hash, encode, diff, validate)
src/api/data_routes.py               -- Public data (wikipedia, arxiv, edgar)
src/api/ecosystem_routes.py          -- x402 directory, status, routing
src/services/realtime_data.py        -- FRED, BLS, Treasury, EDGAR, Federal Register, FDIC, Congress
src/services/regulatory.py           -- Rule-based regulatory engine (1500+ lines)
src/services/prediction_markets.py   -- Polymarket Gamma + Kalshi REST clients
src/services/fed_intelligence.py     -- FOMC schedule, rate model, KXFED calibration
src/services/feeds.py                -- 12 RSS sources (SEC, CFTC, FinCEN, OCC, CFPB, Fed, Treasury)
src/runtime/automaton.py             -- 60s heartbeat, survival tiers, yield/remittance checks
src/runtime/treasury_yield.py        -- Aave V3 USDC deposit/withdraw
src/runtime/remittance.py            -- Auto-remit at $5K, $500 reserve
src/runtime/constitution.py          -- OFAC screening, solvency, compliance calendar
src/runtime/lifecycle.py             -- BOOT -> EARNING -> FORMING -> OPERATING -> REMITTING
src/runtime/transaction_log.py       -- Append-only JSONL for tax/audit
src/x402/middleware.py               -- HTTP 402 intercept, payment verification
src/x402/cdp_facilitator.py          -- CDP x402 SDK middleware
src/x402/mpp_integration.py          -- Machine Payments Protocol middleware
config/settings.py                   -- Pricing dict (55 endpoints), wallet, chain config
static/.well-known/                  -- x402.json, mcp.json, agents.json, llms.txt, ai-plugin.json
```

**Key design decisions:**
- **Zero LLM dependency** -- all endpoints are deterministic, rule-based engines. No API keys for core intelligence.
- **Triple payment stack** -- x402 + X-Payment-Proof + MPP coexist. Agents use whichever protocol they support.
- **Autonomous runtime** -- HydraAutomaton heartbeat runs every 60 seconds: balance checks, lifecycle transitions, Aave yield deposits, auto-remittance.
- **Atomic data fetches** -- each data source is fetched live at request time with short TTL caches. No stale batch pipelines.

---

## Discovery Manifests

HYDRA serves 9 machine-readable discovery manifests so agents, crawlers, and directories can find it automatically:

| Protocol | URL |
|----------|-----|
| **x402 Manifest** | [`/.well-known/x402.json`](https://hydra-api-nlnj.onrender.com/.well-known/x402.json) |
| **MCP Manifest** | [`/.well-known/mcp.json`](https://hydra-api-nlnj.onrender.com/.well-known/mcp.json) |
| **MCP Server** | [`/mcp`](https://hydra-api-nlnj.onrender.com/mcp) |
| **A2A Agent Card** | [`/.well-known/agent.json`](https://hydra-api-nlnj.onrender.com/.well-known/agent.json) |
| **Agents Manifest** | [`/.well-known/agents.json`](https://hydra-api-nlnj.onrender.com/.well-known/agents.json) |
| **LLMs.txt** | [`/.well-known/llms.txt`](https://hydra-api-nlnj.onrender.com/.well-known/llms.txt) |
| **AI Plugin** | [`/.well-known/ai-plugin.json`](https://hydra-api-nlnj.onrender.com/.well-known/ai-plugin.json) |
| **OpenAPI** | [`/openapi.json`](https://hydra-api-nlnj.onrender.com/openapi.json) |
| **APIs.json** | [`/apis.json`](https://hydra-api-nlnj.onrender.com/apis.json) |
| **Sitemap** | [`/sitemap.xml`](https://hydra-api-nlnj.onrender.com/sitemap.xml) |

---

## Deploy

### One-Click (Render)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/OGCryptoKitty/hydra-arm3)

Render auto-deploys from `master` branch. The `render.yaml` blueprint configures everything.

### Local

```bash
git clone https://github.com/OGCryptoKitty/hydra-arm3.git
cd hydra-arm3
pip install -r requirements.txt
cp scripts/.env.example .env
uvicorn src.main:app --host 0.0.0.0 --port 8402
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WALLET_ADDRESS` | `0x2F12...7141` | USDC recipient wallet on Base |
| `WALLET_PRIVATE_KEY` | -- | Private key for treasury ops (Aave yield, remittance) |
| `BASE_RPC_URL` | `https://mainnet.base.org` | Base L2 RPC endpoint |
| `FRED_API_KEY` | -- | Optional: enables full FRED series access |
| `HYDRA_STATE_DIR` | `/tmp/hydra-data` | State persistence directory |
| `PORT` | `8402` | Server port |

---

## CI/CD and Automated Operations

HYDRA runs 7 GitHub Actions workflows for autonomous operation:

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| **Keep Alive** | Every 14 min | Ping health endpoint to prevent Render free-tier sleep |
| **Deploy & Verify** | On push + every 6h | Health check, endpoint verification, manifest validation |
| **Autonomous Ops** | On push + every 4h | Full manifest verification, discovery registration, wallet monitoring, downtime alerts |
| **Discovery Register** | On push (API changes) | Re-register with x402 directories after deployment |
| **Repo Setup** | On push (workflow changes) | Set GitHub repository topics and description |
| **Awesome List Submit** | Weekly (Monday noon) | Submit PRs to awesome-mcp-servers and awesome-x402 lists |
| **API Directory Submit** | On push (workflow changes) | Log discovery channel status |

---

## GitHub Topics

This repository uses the following topics for discoverability:

`mcp-server` `mcp` `model-context-protocol` `x402` `prediction-markets` `polymarket` `kalshi` `regulatory-intelligence` `usdc` `base-l2` `fomc` `defi-oracle` `micropayments` `uma-oracle` `chainlink` `a2a` `agent-to-agent` `fastapi` `regulatory-api`

Recommended additional topics: `ai-agent` `fomc-signals` `sec-edgar` `fred-api` `fdic` `regulatory-compliance` `crypto-regulation`

---

## License

Proprietary -- HYDRA Systems LLC
