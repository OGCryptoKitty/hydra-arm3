# HYDRA — 402-Native Paid Work Engine

## Mission

HYDRA is an autonomous API on Base L2 that earns USDC via x402 micropayments,
compounds treasury via Aave V3 yield, and remits profits to the creator's wallet.
It exposes **74 paid endpoints** (regulatory intelligence, Fed/FOMC signals,
prediction-market alpha, live market data, web utilities, dev tools) plus free
discovery/status endpoints, all payable per-call from $0.001 USDC.

Every session should: assess status → implement revenue-maximizing enhancements →
deploy to production.

## Quick Status Check (run these first every session)

```bash
# 1. Check USDC balance on-chain
curl -s https://mainnet.base.org -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913","data":"0x70a082310000000000000000000000002F12A73e1e08F3BCE12212005cCaBE2ACEf87141"},"latest"],"id":1}' | python3 -c "import sys,json; r=json.load(sys.stdin); print(f'USDC Balance: ${int(r[\"result\"],16)/1e6:.2f}')"

# 2. Check Aave aUSDC balance (yield)
curl -s https://mainnet.base.org -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB","data":"0x70a082310000000000000000000000002F12A73e1e08F3BCE12212005cCaBE2ACEf87141"},"latest"],"id":1}' | python3 -c "import sys,json; r=json.load(sys.stdin); print(f'Aave aUSDC: ${int(r[\"result\"],16)/1e6:.2f}')"

# 3. Check deployment health (includes automaton snapshot)
curl -s https://hydra-api-nlnj.onrender.com/health | python3 -m json.tool

# 4. Check ETH balance (for gas)
curl -s https://mainnet.base.org -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141","latest"],"id":1}' | python3 -c "import sys,json; r=json.load(sys.stdin); print(f'ETH Balance: {int(r[\"result\"],16)/1e18:.6f}')"

# 5. Full automaton + capitalism-model status
curl -s https://hydra-api-nlnj.onrender.com/status | python3 -m json.tool

# 6. Revenue metrics (per-endpoint breakdown)
curl -s https://hydra-api-nlnj.onrender.com/metrics/revenue | python3 -m json.tool
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
| App version | `2.0.0` (see `config/settings.py:APP_VERSION`) |
| Python | 3.11 (Render pins `3.11.6`; Docker uses `python:3.11-slim`) |

## Local Development

```bash
pip install -r requirements.txt
cp .env.example .env                       # then edit as needed
uvicorn src.main:app --host 0.0.0.0 --port 8402 --reload
# or
docker-compose up

# Smoke checks (no payment required):
curl localhost:8402/health
curl localhost:8402/pricing
curl localhost:8402/.well-known/x402.json
open  localhost:8402/docs                  # interactive OpenAPI UI
```

There is **no test suite** in this repo. Validate changes by importing the app
and exercising endpoints locally, e.g. `python -c "import src.main"` to catch
import-time errors, then curl the affected routes. Keep `config.settings.PRICING`
in sync whenever you add or rename a paid endpoint — the x402 middleware reads
prices from there, and `/metrics`, `/pricing`, and the 404 handler enumerate it.

### Environment variables

| Var | Purpose | Default / notes |
|-----|---------|-----------------|
| `WALLET_ADDRESS` | Receiving wallet for USDC | hard-coded default; **never change** |
| `WALLET_PRIVATE_KEY` | Enables Aave yield + auto-remittance (set in Render dashboard, `sync:false`) | unset → automaton runs read-only |
| `BASE_RPC_URL` | Base L2 RPC | `https://mainnet.base.org` (3 fallbacks in settings) |
| `HYDRA_STATE_DIR` | Persisted state (replay cache, alerts, tx log) | `/tmp/hydra-data` |
| `FRED_API_KEY` | FRED economic series in `realtime_data.py` | unset → those series return empty |
| `BLS_API_KEY` / `CONGRESS_API_KEY` | BLS + congress.gov data | optional, raise rate limits |
| `ANTHROPIC_API_KEY` | Enables LLM-augmented responses (`/metrics` reports `llm_enabled`) | optional |
| `BALANCE_PHRASE` | Auth phrase for internal `_balance_router` monitoring | optional |
| `PORT` / `HOST` / `DEBUG` | Server config | `8402` / `0.0.0.0` / `false` |
| `FEED_CACHE_TTL` / `PAYMENT_CACHE_TTL` | Cache TTLs (s) | `600` / `86400` |

## Architecture (key files)

```
src/main.py                          — FastAPI app: lifespan, MCP mount, middleware stack,
                                       static/.well-known routes, /health /status /metrics
config/settings.py                   — PRICING dict (74 paid endpoints), wallet, chain, cache config
config/prediction_pricing.py         — Prediction-market tier pricing helpers

── API routers (each included in main.py) ──
src/api/routes.py                    — Core regulatory endpoints (scan, changes, jurisdiction, query)
src/api/prediction_routes.py         — Polymarket/Kalshi feed, events, signal(s), alpha, oracle, resolution
src/api/fed_routes.py                — FOMC signal / decision / resolution (highest-value category)
src/api/utility_routes.py            — High-volume utilities (scrape, crypto price, rss, gas, tx, batch)
src/api/extract_routes.py            — Web extraction (url, multi, search)
src/api/check_routes.py              — Web checks (url health, dns, ssl, headers)
src/api/convert_routes.py            — Format conversion (html2md, json2csv, csv2json)
src/api/tools_routes.py              — Developer tools (hash, encode, diff, validate json/email)
src/api/data_routes.py               — Public data (wikipedia, arxiv, edgar)
src/api/market_data_routes.py        — Live market data (CoinGecko, DeFi Llama, Binance, DexScreener,
                                       mempool.space, Treasury, fear/greed, gas, forex, snapshot)
src/api/intelligence_routes.py       — Composite products (pulse, alpha, risk-score, digest,
                                       economic-snapshot, regulatory-pulse-live, bank-failures)
src/api/portfolio_routes.py          — Portfolio scan/watchlist/market-brief + /v1/orchestrate
src/api/ecosystem_routes.py          — x402 ecosystem hub (/v1/x402/status, /v1/x402/route)
src/api/alert_routes.py              — Push-alert subscribe/feed/status (webhook delivery)
src/api/mpp.py                       — MPP (Machine Payments Protocol) manifest + status
src/api/system_routes.py             — Wallet mgmt, remittance, status (+ internal _balance_router)

── Services (data engines) ──
src/services/regulatory.py           — Rule-based regulatory engine (1500+ lines)
src/services/prediction_markets.py   — Polymarket Gamma + Kalshi REST clients (category-filtered)
src/services/fed_intelligence.py     — FOMC schedule, rate model, live Fed RSS
src/services/feeds.py                — RSS sources (SEC, CFTC, FinCEN, OCC, CFPB, Fed, Treasury)
src/services/live_market_data.py     — CoinGecko/DeFi Llama/Binance/DexScreener/mempool/ECB (no API key)
src/services/realtime_data.py        — FRED, BLS, Treasury yield curve, SEC EDGAR EFTS,
                                       Federal Register, congress.gov (atomic, live at request time)

── Runtime (autonomous loops) ──
src/runtime/automaton.py             — 60s heartbeat, survival tiers, yield/remittance checks
src/runtime/alert_engine.py          — Monitors feeds, pushes webhook alerts to subscribers
src/runtime/autonomous_marketing.py  — GitHub PRs, Dev.to, discussions, SEO docs
src/runtime/agent_discovery.py       — Registration with x402scan, Glama, Smithery, Bazaar, etc.
src/runtime/revenue_optimizer.py     — Usage analytics, pricing recommendations
src/runtime/treasury_yield.py        — Aave V3 USDC deposit/withdraw
src/runtime/remittance.py            — Auto-remit at $5K surplus, $500 operating reserve
src/runtime/constitution.py          — OFAC screening, solvency, compliance calendar
src/runtime/lifecycle.py             — BOOT→EARNING→FORMING→OPERATING→REMITTING
src/runtime/transaction_log.py       — Append-only JSONL for tax/audit

── Payment layer (middleware, order matters) ──
src/x402/middleware.py               — X-Payment-Proof intercept; file-backed replay cache
src/x402/verify.py                   — On-chain USDC transfer verification
src/x402/cdp_facilitator.py          — CDP x402 SDK middleware (standard X-PAYMENT header)
src/x402/mpp_integration.py          — Machine Payments Protocol middleware (Authorization: Payment)

── Shared ──
src/models/schemas.py                — Pydantic request/response schemas + enums (Agency, etc.)
src/utils/url_validation.py          — SSRF guard (is_safe_url) — use for any user-supplied URL

── Discovery / static ──
static/.well-known/x402.json         — x402 service discovery manifest
static/.well-known/mcp.json          — MCP discovery manifest
static/.well-known/agents.json       — agents.json workflow manifest
static/.well-known/agent.json        — Google A2A Agent Card (also served at /agent-card.json)
static/.well-known/ai-plugin.json    — OpenAI/ChatGPT plugin manifest
static/.well-known/llms.txt          — agent SEO manifest
static/apis.json / robots.txt / sitemap.xml / favicon.svg
index.html                           — HTML landing page served at /
```

## Payment / x402 Flow

Three coexisting payment paths (a request can satisfy any one):

1. **X-Payment-Proof** (HYDRA-native, `src/x402/middleware.py`) — caller sends USDC
   on Base directly to the wallet, then replays the tx hash in the `X-Payment-Proof`
   header. `verify.py` confirms the on-chain ERC-20 Transfer for the exact amount.
   Replay protection is **file-backed** at `$HYDRA_STATE_DIR/used_txhashes.json`
   (survives Render restarts) with a 24h TTL cache.
2. **x402 / CDP facilitator** (`cdp_facilitator.py`) — standard `X-PAYMENT` header
   via the CDP SDK; auto-registers HYDRA on Bazaar / x402list.fun / x402search.
   Degrades gracefully if the SDK isn't installed.
3. **MPP** (`mpp_integration.py`) — `Authorization: Payment` session micropayments
   (Stripe/Tempo). Degrades gracefully if `pympp` isn't installed.

Unpaid requests to a priced path return **HTTP 402** with machine-parseable
`X-Payment-*` headers describing amount, token, wallet, network, and endpoint.
Prices live in `config.settings.PRICING` (keyed by route path).

## Revenue Model

**74 paid endpoints** ($0.001 – $50.00 USDC) plus free discovery/status endpoints
(`/`, `/health`, `/status`, `/metrics`, `/metrics/revenue`, `/pricing`, `/docs`,
`/v1/markets` discovery, `/.well-known/*`, `/mcp`). Endpoint families:

| Family | Price range | Examples |
|--------|-------------|----------|
| Developer tools | $0.001–0.003 | hash, encode, diff, validate |
| Web checks / convert | $0.003–0.005 | url/dns/ssl/headers, html2md, csv↔json |
| Utilities | $0.001–0.01 | crypto price, gas, tx, scrape, rss, batch |
| Live market data | $0.001–0.05 | CoinGecko, DeFi Llama, Binance, DexScreener, mempool, Treasury |
| Extraction / public data | $0.01–0.05 | extract url/multi/search, wikipedia, arxiv, edgar |
| Composite intelligence | $0.25–5.00 | pulse, risk-score, digest, economic-snapshot, bank-failures |
| Regulatory | $1.00–3.00 | scan, changes, jurisdiction, query |
| Prediction markets | $0.10–10.00 | feed, events, signal(s), alpha |
| Fed / FOMC | $5.00–50.00 | signal, decision, resolution |
| Oracle / resolution | $5.00–25.00 | uma, chainlink, markets/resolution |
| Portfolio | $2.00–10.00 | scan, watchlist, market-brief |

## Autonomous Runtime

On startup (`lifespan` in `main.py`) HYDRA initialises ConstitutionCheck,
TransactionLog, LifecycleManager, RemittanceManager, then launches the
**HydraAutomaton** heartbeat as a background asyncio task:

- **60s heartbeat** (`automaton.py`) — reads USDC balance, computes survival tier
  (CRITICAL / MINIMAL / VIABLE / FUNDED / SURPLUS), advances lifecycle phase.
- **Treasury yield** (`treasury_yield.py`) — once the balance is VIABLE ($500+),
  deposits the excess above the $500 operating reserve into **Aave V3 USDC** to
  compound yield; withdraws automatically before any remittance. **Live only when
  `WALLET_PRIVATE_KEY` is set AND it derives to the treasury wallet** — the manager
  verifies `Account.from_key(pk).address == WALLET_ADDRESS` at init and refuses all
  on-chain writes otherwise (placeholder/zero/wrong key ⇒ monitor-only, no doomed
  broadcasts). An ETH gas pre-flight (`MIN_GAS_ETH`) blocks deposits when the wallet
  can't pay gas; USDC approval is a one-time max approval to save gas on compounding.
- **Auto-remittance** — at **$5,000** surplus, remits (balance − **$500** reserve)
  to the receiving wallet (`remittance.py`).
- Without a treasury-controlling `WALLET_PRIVATE_KEY` the automaton runs **read-only**
  (monitor + live APR reporting only).

### Operating treasury yield (Aave V3)

Yield status and live APR surface on the public `/status` (`capitalism_models` →
`treasury_yield`) and the authenticated `/system/yield/status`. Operator controls
(localhost or `Authorization: Bearer <sha256(pk+"hydra-system")>`):

```bash
curl localhost:8402/system/yield/status                       # APR, principal, accrued yield, mode
curl -X POST localhost:8402/system/yield/deposit              # deposit all depositable excess
curl -X POST localhost:8402/system/yield/deposit  -d '{"amount_usdc":"250"}' -H 'Content-Type: application/json'
curl -X POST localhost:8402/system/yield/withdraw             # withdraw entire Aave position
```

To go live in production: set `WALLET_PRIVATE_KEY` (the key controlling
`WALLET_ADDRESS`) in the Render dashboard (`sync:false`) and keep a little ETH on
Base in the wallet for gas. The heartbeat then auto-deposits idle USDC every cycle.

## Deployment Workflow

1. Develop on a feature branch.
2. `git push -u origin <branch>`.
3. Merge to `master` — **Render auto-deploys** within 2–5 minutes (`render.yaml`,
   `autoDeploy: true`, `healthCheckPath: /health`).
4. Verify via `/health`, `/status`, `/.well-known/x402.json`, `/metrics/revenue`.

GitHub Actions (`.github/workflows/`) automate the rest:
- `keepalive.yml` — pings `/health` every 14 min (Render free tier sleeps).
- `deploy-verify.yml` — every 6h: wakes service, triggers deploy hook, verifies endpoints.
- `hydra-autonomous.yml` — every 4h: health check + autonomous ops.
- `discovery-register.yml` — on deploy: registers with discovery services.
- `awesome-list-submit.yml` / `api-directory-submit.yml` — weekly distribution PRs.
- `repo-setup.yml` — sets repo topics/description.

## Autonomous Enhancement Priorities

Prioritize by expected revenue impact:

### Tier 1: Distribution (agents must find HYDRA to pay)
- Register with new MCP / x402 directories as they emerge.
- Keep all discovery manifests current and serving (`/.well-known/*`, `/mcp`).
- Submit to API directories (public-apis, APIs.guru, RapidAPI).

### Tier 2: Conversion (agents must complete payment flow)
- Keep 402 responses' `X-Payment-*` headers clear and machine-parseable.
- Test the payment flow end-to-end with x402 client libraries.
- Provide free-tier samples so agents can verify value before paying.

### Tier 3: Data Quality (paid responses must be worth the price)
- Verify live Fed RSS freshness; wire `FRED_API_KEY` for full economic series.
- Add congressional / Federal Register depth (`realtime_data.py`).
- Live OFAC screening via Chainalysis (currently static in `constitution.py`).

### Tier 4: New Revenue Streams
- Subscription/bundle endpoints (daily signal package).
- Expand webhook alert delivery (`alert_engine.py`).
- Historical / backtest dataset API.

## Known Issues / Notes

1. **`/metrics` reports `remittance_threshold_usdc: "1000"`** but the actual
   trigger in `remittance.py` is **$5,000** (`REMITTANCE_THRESHOLD`). The metrics
   string is cosmetic/stale — fix the literal in `main.py` if surfacing it to users.
2. **`WALLET_PRIVATE_KEY` required for full automaton** — set it in the Render
   dashboard (`sync:false`). Without it, yield + auto-remittance are disabled.
3. **`FRED_API_KEY` unset → empty economic series** in `realtime_data.py`; the
   app logs this as a production blocker at startup but still serves.
4. **Revenue bottleneck is distribution, not capability** — 74 paid endpoints are
   live; focus Tier-1 work on getting paying agents to discover HYDRA.
5. *(Resolved)* Replay cache is now file-backed (`used_txhashes.json`), and the
   Kalshi client now filters by category buckets (regulation/crypto/politics/finance/…).

## Conventions

- **SSRF**: route any user-supplied URL through `src.utils.url_validation.is_safe_url`
  before fetching (extract/check/scrape routes already do).
- **Pricing is the source of truth**: add the route to `config.settings.PRICING`
  (with `amount_usdc`, `amount_base_units`, `description`) when adding a paid endpoint,
  or it won't be gated, priced, or listed.
- **Routers**: define an `APIRouter` with `tags=[...]`, full `/v1/...` paths on the
  routes, and include it in `main.py`. New OpenAPI tags go in the `openapi_tags` list.
- **Graceful degradation**: optional SDKs (x402, pympp, fastapi-mcp) must never crash
  startup — guard imports and log a warning, mirroring the existing middleware adders.
- **Never** modify wallet addresses or remittance configuration; **never** log or
  expose private keys.

## Authorization

The owner authorizes Claude Code to:
- Make all code changes to maximize revenue
- Push to GitHub and trigger Render deployment
- Operate autonomously without human confirmation for code changes
- Never modify wallet addresses or remittance configuration
- Never expose or log private keys
