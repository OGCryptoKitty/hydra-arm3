# HYDRA — Claude Code Handoff Document
*Generated April 7, 2026. Owner: OGCryptoKitty (GitHub)*

---

## Access & Permissions

| Resource | Details |
|---|---|
| **GitHub repo** | github.com/OGCryptoKitty/hydra-arm3 (private) |
| **Live API** | https://hydra-api-nlnj.onrender.com |
| **Hosting** | Render.com — service name `hydra-api-nlnj` |
| **Render account** | Connected to OGCryptoKitty GitHub |
| **Wallet** | `0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141` on Base L2 |
| **USDC contract** | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` on Base |
| **Chain** | Base (chain ID 8453) |

The owner authorizes Claude Code to make all necessary code changes, push to GitHub, and trigger Render redeployment.

---

## Priority Bug Fixes (in order)

### FIX 1 — Kalshi Market Filter Returns Wrong Markets [CRITICAL]
**File:** `src/services/prediction_markets.py`
**Problem:** `KalshiClient.get_regulatory_markets()` returns sports/entertainment markets (tennis, NBA, hockey) instead of regulatory/political markets.
**Evidence:** Live `GET /v1/markets` returns "Alexander Zverev, Andrey Rublev" markets — not SEC/CFTC/Fed.
**Fix needed:** Debug the Kalshi API response structure. Kalshi's event API returns events with a `category` field and `title`. The keyword filter should match against actual Kalshi categories. Try:
- Use Kalshi's `/events` endpoint with explicit category filters: `category=politics,finance,economics,regulation`
- Or filter by checking if event title/subtitle contains: `fed`, `rate`, `sec`, `cftc`, `regulation`, `crypto`, `stablecoin`, `legislation`, `tariff`, `sanctions`, `fomc`, `inflation`, `cpi`, `gdp`
- Kalshi's API base: `https://api.elections.kalshi.com/trade-api/v2`

### FIX 2 — SurvivalTier Enum Comparison Crashes Heartbeat [MODERATE]
**File:** `src/runtime/automaton.py`
**Problem:** `TypeError: '>=' not supported between instances of 'SurvivalTier' and 'SurvivalTier'` on every heartbeat cycle.
**Fix:** Change `class SurvivalTier(Enum)` to `class SurvivalTier(IntEnum)` and import `from enum import IntEnum`. Also check `Phase` enum in `src/runtime/lifecycle.py` for same issue.

### FIX 3 — x402 Discovery Manifest Not Serving [CRITICAL for discovery]
**File:** `src/main.py`
**Problem:** `GET /.well-known/x402.json` returns 404. The `StaticFiles` mount isn't working.
**Fix option A:** Add an explicit route:
```python
@app.get("/.well-known/x402.json", include_in_schema=False)
async def x402_manifest():
    import json
    manifest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", ".well-known", "x402.json")
    with open(manifest_path) as f:
        return json.load(f)
```
**Fix option B:** Ensure `static/` directory is included in Render build and StaticFiles mount path is correct.

### FIX 4 — Render Running Old Code [URGENT]
**Problem:** Live Render instance shows old pricing (regulatory/scan at $0.50) in error messages. Latest git commit not deployed.
**Fix:** Log into Render dashboard → `hydra-api-nlnj` service → "Manual Deploy" → "Deploy latest commit". Then verify `GET /pricing` shows $2.00 for `/v1/regulatory/scan`.

### FIX 5 — Private Key Missing on Render [MODERATE]
**File:** `src/main.py` lines 131-138
**Problem:** Code tries to load private key from `/home/user/workspace/hydra-bootstrap/wallet.json` — this path doesn't exist on Render. Automaton runs in placeholder/read-only mode.
**Fix:** In Render dashboard → Environment → Add secret env var:
- Key: `WALLET_PRIVATE_KEY`
- Value: the private key from `wallet.json` (locally at `/home/user/workspace/hydra-bootstrap/wallet.json`)

### FIX 6 — Replay Attack: In-Memory Cache Cleared on Restart [SECURITY]
**File:** `src/x402/middleware.py`
**Problem:** Used tx-hash cache lives in memory only. Render free tier restarts frequently. After restart, a used payment tx hash could be replayed.
**Fix:** Persist the used-tx cache to a file:
```python
import json, os
REPLAY_CACHE_FILE = "/tmp/hydra_used_txhashes.json"

def load_replay_cache():
    try:
        with open(REPLAY_CACHE_FILE) as f:
            return set(json.load(f))
    except:
        return set()

def save_replay_cache(cache: set):
    with open(REPLAY_CACHE_FILE, 'w') as f:
        json.dump(list(cache), f)
```

### FIX 7 — Cleanup Dead Code Files [MINOR]
Delete these files that are stale patches, not active modules:
- `src/main_update_patch.py`
- `src/api/prediction_routes_integration.py`

---

## Architecture Overview

```
hydra-arm3/
├── config/
│   ├── settings.py          — pricing dict (15 endpoints, $0.10–$50), wallet, chain
│   └── prediction_pricing.py — prediction market pricing (separate dict)
├── src/
│   ├── main.py              — FastAPI app, lifespan, all router registrations
│   ├── api/
│   │   ├── routes.py        — core regulatory endpoints (scan, changes, jurisdiction, query)
│   │   ├── prediction_routes.py — Polymarket/Kalshi/oracle endpoints (11 endpoints)
│   │   ├── fed_routes.py    — FOMC signal/decision/resolution (3 endpoints, $5–$50)
│   │   └── system_routes.py — wallet mgmt, remittance, status, shutdown
│   ├── services/
│   │   ├── regulatory.py    — rule-based regulatory engine (1507 lines)
│   │   ├── prediction_markets.py — Polymarket Gamma API + Kalshi REST API clients
│   │   ├── fed_intelligence.py — FOMC schedule, rate probability model
│   │   └── feeds.py         — SEC/CFTC/FinCEN RSS aggregator
│   ├── runtime/
│   │   ├── automaton.py     — Conway-style heartbeat loop, survival tiers
│   │   ├── remittance.py    — $5K USDC threshold, auto-remit to receiving wallet
│   │   ├── constitution.py  — OFAC screening, solvency check, compliance calendar
│   │   ├── lifecycle.py     — 5-phase state machine (BOOT→EARNING→FORMING→OPERATING→REMITTING)
│   │   └── transaction_log.py — append-only JSONL for tax records (Form 5472)
│   └── x402/
│       ├── middleware.py    — HTTP 402 intercept, payment verification middleware
│       └── verify.py        — on-chain USDC transfer verification via web3.py
├── static/
│   └── .well-known/
│       └── x402.json        — service discovery manifest (currently not serving — see Fix 3)
├── scripts/
│   ├── twitter_bot.py       — RSS → tweets with HYDRA API CTA
│   └── telegram_bot.py      — /markets, /latest, /pricing Telegram bot
└── render.yaml              — Render deployment config
```

---

## Payment Flow (x402)

1. Client calls any paid endpoint (e.g., `POST /v1/markets/signals`)
2. Server returns `HTTP 402` with payment details:
   - `X-Payment-Required: true`
   - `X-Payment-Amount: 5000000` (5.00 USDC, 6 decimals)
   - `X-Payment-Address: 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141`
   - `X-Payment-Network: base`
   - `X-Payment-Chain-Id: 8453`
3. Client sends USDC on Base to the wallet address
4. Client retries with `X-Payment-Proof: <tx_hash>`
5. Server verifies tx on-chain via `verify_usdc_payment()` in `src/x402/verify.py`
6. If verified: serve response. If not: return 402 again.

---

## Pricing (settings.py)

| Endpoint | Price USDC |
|---|---|
| `/v1/markets/feed` | $0.10 |
| `/v1/markets/events` | $0.50 |
| `/v1/regulatory/changes` | $1.00 |
| `/v1/regulatory/query` | $1.00 |
| `/v1/markets/signal/{id}` | $2.00 |
| `/v1/regulatory/scan` | $2.00 |
| `/v1/regulatory/jurisdiction` | $3.00 |
| `/v1/fed/signal` | $5.00 |
| `/v1/markets/signals` | $5.00 |
| `/v1/oracle/uma` | $5.00 |
| `/v1/oracle/chainlink` | $5.00 |
| `/v1/markets/alpha` | $10.00 |
| `/v1/markets/resolution` | $25.00 |
| `/v1/fed/decision` | $25.00 |
| `/v1/fed/resolution` | $50.00 |

Free: `GET /health`, `GET /pricing`, `GET /docs`, `GET /v1/markets`, `GET /v1/markets/discovery`, `GET /v1/markets/pricing`

---

## Remittance System

- **Trigger:** USDC balance ≥ $5,000 on Base
- **Amount:** Balance minus $500 operating reserve
- **Method:** Direct ERC-20 USDC transfer on Base
- **Privacy:** No memo, no metadata on-chain
- **Config:** `/home/user/workspace/hydra-bootstrap/remittance-config.json` (not in git)
- **Receiving wallet:** Not yet configured — system prompts for address at `GET /system/remittance/status` when threshold is met
- **OFAC:** Every outbound transfer screened against sanctions list
- **Constitution:** 3 immutable laws checked before any transfer — OFAC (legality), $500 floor (solvency), compliance calendar

---

## Current Status

- **API:** Live, HTTP 200 on health
- **Wallet balance:** $0.00 USDC (never transacted)
- **Phase:** FORMING (awaiting $3K for entity formation)
- **Monitors:** Stopped (to be restarted after fixes deployed)
- **Revenue:** $0 (no marketing/discovery yet)
- **Entity formation:** Not yet started — requires $3K USDC seed

---

## After Fixes — Resume Steps

1. Fix all 7 issues above
2. Push to GitHub → Render auto-deploys
3. Verify `GET /v1/markets` returns regulatory markets (not sports)
4. Verify `GET /.well-known/x402.json` returns the manifest
5. Restart wallet monitor and remittance executor crons
6. Post to r/Polymarket, Kalshi Discord, HN, UMA Discord (posts are in `scripts/marketing/community_posts.md`)
7. Send Polymarket Builder Program email (draft in `scripts/marketing/polymarket_builder_email.txt`)
8. Submit x402 ecosystem PR (branch `add-hydra-regulatory-intelligence` is already pushed to OGCryptoKitty/x402)
