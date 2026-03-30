# HYDRA Prediction Market Integration — Setup Guide

**Date:** March 29, 2026  
**Files added:** 4 new files  
**Files modified:** 1 existing file  

This document explains exactly what to add to `src/main.py` and `config/settings.py` to activate the prediction market intelligence endpoints.

---

## New Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/services/prediction_markets.py` | ~1835 | Service layer: Polymarket + Kalshi clients, aggregator, event feed, oracle formatters |
| `src/api/prediction_routes.py` | ~1512 | FastAPI router: 3 free + 8 paid endpoints |
| `config/prediction_pricing.py` | ~224 | Pricing config module for prediction market endpoints |
| `prediction_integration_instructions.md` | — | This file |

---

## Step 1 — Update `config/settings.py`

The `PRICING` dict in `config/settings.py` already contains the prediction market entries added in the previous integration pass. **Verify they are present:**

```bash
grep "markets/signals\|markets/feed\|markets/alpha\|oracle/uma" config/settings.py
```

If the entries are missing, add the following block inside the `PRICING` dict in `config/settings.py`, after the existing regulatory entries:

```python
# ── Prediction Market Intelligence ─────────────────────────────
# Free endpoints are NOT in this dict — middleware skips them.
# Only paid endpoints are listed so x402 middleware enforces payment.

"/v1/markets/feed": {
    "amount_usdc": Decimal("0.05"),
    "amount_base_units": 50_000,    # 0.05 USDC * 10^6
    "description": (
        "Micro regulatory event feed — latest 10 events from last hour, pre-matched to "
        "prediction markets. Minimal payload for high-frequency bot polling every 2-5 minutes."
    ),
},
"/v1/markets/signal": {
    "amount_usdc": Decimal("0.10"),
    "amount_base_units": 100_000,   # 0.10 USDC * 10^6
    "description": (
        "Single market deep signal — full HYDRA regulatory analysis for one specific "
        "Polymarket condition_id or Kalshi ticker. Includes historical precedent and risk factors."
    ),
},
"/v1/markets/signals": {
    "amount_usdc": Decimal("0.25"),
    "amount_base_units": 250_000,   # 0.25 USDC * 10^6
    "description": (
        "Prediction market signals — bulk HYDRA regulatory signals for all matching markets "
        "(Polymarket + Kalshi; Fed/SEC/crypto/regulation). Core pre-trade intelligence."
    ),
},
"/v1/markets/events": {
    "amount_usdc": Decimal("0.15"),
    "amount_base_units": 150_000,   # 0.15 USDC * 10^6
    "description": (
        "Regulatory event feed — real-time SEC, CFTC, FinCEN, OCC, CFPB events "
        "matched to active prediction markets with impact assessments."
    ),
},
"/v1/markets/resolution": {
    "amount_usdc": Decimal("1.00"),
    "amount_base_units": 1_000_000,  # 1.00 USDC * 10^6
    "description": (
        "Oracle resolution assessment — HYDRA's verdict on how a market should resolve. "
        "For UMA bond asserters: determines whether posting a $750 USDC.e bond is safe."
    ),
},
"/v1/markets/alpha": {
    "amount_usdc": Decimal("2.00"),
    "amount_base_units": 2_000_000,  # 2.00 USDC * 10^6
    "description": (
        "Full alpha report — regulatory probability, edge vs market price, risk/reward, "
        "optimal entry, similar historical trades, expected resolution timeline. Premium."
    ),
},
"/v1/oracle/uma": {
    "amount_usdc": Decimal("0.50"),
    "amount_base_units": 500_000,   # 0.50 USDC * 10^6
    "description": (
        "UMA Optimistic Oracle formatted assertion data — complete ancillary data, "
        "proposed price, bond details, and evidence chain for submitting to UMA OOv2 on Polygon."
    ),
},
"/v1/oracle/chainlink": {
    "amount_usdc": Decimal("0.50"),
    "amount_base_units": 500_000,   # 0.50 USDC * 10^6
    "description": (
        "Chainlink External Adapter response — regulatory data formatted for on-chain delivery "
        "via Chainlink node operators. Compatible with Chainlink Any API Direct Request model."
    ),
},
```

**Free endpoints are intentionally absent from `PRICING`** — the x402 middleware only enforces payment for paths that appear in this dict. `GET /v1/markets`, `GET /v1/markets/discovery`, and `GET /v1/markets/pricing` resolve freely.

---

## Step 2 — Update `src/main.py`

Three additions are required. Apply them in order.

### 2a. Add the import

Find this block near the top of `src/main.py`:

```python
from src.api.routes import router
from src.api.system_routes import system_router
```

Add the prediction router import on the next line:

```python
from src.api.routes import router
from src.api.system_routes import system_router
from src.api.prediction_routes import prediction_router   # ← ADD THIS
```

### 2b. Register the router on the FastAPI app

Find the router registration section in `src/main.py` (after middleware is added):

```python
# Public + paid regulatory endpoints
app.include_router(router)

# System management endpoints
app.include_router(system_router, prefix="")
```

Add the prediction router immediately after:

```python
# Public + paid regulatory endpoints
app.include_router(router)

# System management endpoints
app.include_router(system_router, prefix="")

# Prediction market intelligence endpoints (free + paid)
app.include_router(prediction_router)              # ← ADD THIS
```

No prefix is needed — all `prediction_router` routes already include `/v1/markets/` or `/v1/oracle/` in their path strings.

### 2c. Add the Prediction Markets tag to OpenAPI docs (optional but recommended)

In `src/main.py`, find the `openapi_tags` list passed to the `FastAPI(...)` constructor:

```python
openapi_tags=[
    {"name": "System", ...},
    {"name": "System Management", ...},
    {"name": "Regulatory Intelligence", ...},
],
```

Add two prediction market tag entries:

```python
openapi_tags=[
    {"name": "System", ...},
    {"name": "System Management", ...},
    {"name": "Regulatory Intelligence", ...},
    {
        "name": "Prediction Markets — Free",
        "description": (
            "Free discovery and pricing endpoints. No payment required. "
            "Designed to attract bot traffic and demonstrate HYDRA's market coverage."
        ),
    },
    {
        "name": "Prediction Markets — Paid",
        "description": (
            "Paid prediction market intelligence — require USDC payment via x402 protocol. "
            "Send USDC to the wallet address on Base (chain 8453), "
            "then include the tx hash in the X-Payment-Proof header."
        ),
    },
    {
        "name": "Prediction Markets — Oracle",
        "description": (
            "Oracle data formatting endpoints — UMA OOv2 and Chainlink External Adapter. "
            "Require USDC payment via x402 protocol."
        ),
    },
],
```

---

## Step 3 — Update `src/main.py` 404 handler (optional)

The existing 404 handler in `src/main.py` lists available endpoints. Update the `available_endpoints` list to include the prediction market routes:

```python
"available_endpoints": [
    "GET  /health",
    "GET  /pricing",
    "POST /v1/regulatory/scan         ($1.00 USDC)",
    "POST /v1/regulatory/changes      ($0.50 USDC)",
    "POST /v1/regulatory/jurisdiction ($2.00 USDC)",
    "POST /v1/regulatory/query        ($0.50 USDC)",
    "--- Prediction Markets ---",
    "GET  /v1/markets                 (FREE)",
    "GET  /v1/markets/discovery       (FREE)",
    "GET  /v1/markets/pricing         (FREE)",
    "GET  /v1/markets/feed            ($0.05 USDC)",
    "POST /v1/markets/signals         ($0.25 USDC)",
    "POST /v1/markets/signal/{id}     ($0.10 USDC)",
    "POST /v1/markets/events          ($0.15 USDC)",
    "POST /v1/markets/resolution      ($1.00 USDC)",
    "POST /v1/markets/alpha           ($2.00 USDC)",
    "POST /v1/oracle/uma              ($0.50 USDC)",
    "POST /v1/oracle/chainlink        ($0.50 USDC)",
    "--- System (localhost/bearer token) ---",
    "POST /system/wallet",
    "GET  /system/remittance/status",
    "POST /system/remittance/execute",
    "GET  /system/transactions",
    "GET  /system/status",
    "POST /system/shutdown",
],
```

---

## Step 4 — x402 Middleware: Parametric Path Matching

The x402 middleware at `src/x402/middleware.py` looks up the incoming request path in `settings.PRICING` to determine the required payment amount.

The `/v1/markets/signal/{market_id}` route sends requests with paths like `/v1/markets/signal/0xabc123...`. The pricing dict key is `/v1/markets/signal` (without the ID suffix).

**Check how your middleware resolves paths:**

```bash
grep -n "path\|PRICING\|lookup\|match" src/x402/middleware.py | head -30
```

If the middleware does **exact** path matching, add this normalization helper inside `middleware.py` before the pricing lookup:

```python
def _normalize_path_for_pricing(path: str) -> str:
    """Strip path parameters from known parametric routes for pricing lookup."""
    # /v1/markets/signal/0xabc123 → /v1/markets/signal
    parametric_prefixes = ["/v1/markets/signal/"]
    for prefix in parametric_prefixes:
        if path.startswith(prefix):
            return prefix.rstrip("/")
    return path
```

Then call it before the pricing lookup:
```python
pricing_key = _normalize_path_for_pricing(request.url.path)
price_info = settings.PRICING.get(pricing_key)
```

If the middleware already uses **prefix matching** (e.g., `path.startswith(key)`), no changes are needed.

---

## Step 5 — Restart and Verify

```bash
# Restart the server
uvicorn src.main:app --host 0.0.0.0 --port 8402 --reload

# 1. Test the free discovery endpoint (should return 200 + market list)
curl http://localhost:8402/v1/markets
curl http://localhost:8402/v1/markets/discovery
curl http://localhost:8402/v1/markets/pricing

# 2. Test a paid endpoint (should return 402 Payment Required)
curl -X POST http://localhost:8402/v1/markets/signals \
     -H "Content-Type: application/json" \
     -d '{"platform": "all", "category": "all"}'
# Expected: HTTP 402 with x402 payment instructions in response body

# 3. Test the alpha endpoint (should return 402)
curl -X POST http://localhost:8402/v1/markets/alpha \
     -H "Content-Type: application/json" \
     -d '{"market_id": "KXFED-25APR30", "position": "yes", "size_usdc": 1000}'
# Expected: HTTP 402

# 4. Check OpenAPI docs — should show Prediction Markets tags
curl http://localhost:8402/docs
```

---

## Endpoint Reference

### Free Endpoints (no payment required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/markets` | All active regulatory markets — title, price, volume only. The traffic hook. |
| GET | `/v1/markets/discovery` | Full discovery with domain metadata, HYDRA coverage guide, and paid endpoint descriptions. |
| GET | `/v1/markets/pricing` | Pricing for all paid endpoints. Bots call this before implementing payment. |

### Paid Endpoints (x402 USDC payment required)

| Method | Path | Price | Description |
|--------|------|-------|-------------|
| GET | `/v1/markets/feed` | $0.05 | Latest 10 events from last hour, matched to markets. Poll every 2-5 min. |
| POST | `/v1/markets/signal/{market_id}` | $0.10 | Deep signal for one market (Polymarket condition_id or Kalshi ticker). |
| POST | `/v1/markets/signals` | $0.25 | Bulk signals for all regulatory markets across both platforms. |
| POST | `/v1/markets/events` | $0.15 | Event feed from SEC/CFTC/FinCEN/OCC/CFPB matched to active markets. |
| POST | `/v1/oracle/uma` | $0.50 | UMA OOv2 formatted assertion data with evidence chain. |
| POST | `/v1/oracle/chainlink` | $0.50 | Chainlink External Adapter response for on-chain delivery. |
| POST | `/v1/markets/resolution` | $1.00 | Oracle-grade resolution assessment. For UMA bond asserters. |
| POST | `/v1/markets/alpha` | $2.00 | **PREMIUM.** Full alpha report: edge, Kelly sizing, historical analogues, verdict. |

### Payment Method

All paid endpoints use the x402 HTTP payment protocol:

1. Bot receives `HTTP 402 Payment Required` on first request
2. Bot reads `X-Payment-Amount` and `X-Payment-Address` from response headers  
3. Bot sends exact USDC amount to `0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141` on Base (chain 8453)
4. Bot retries request with transaction hash in `X-Payment-Proof` header
5. Middleware verifies the transaction on-chain; request proceeds

---

## Verification Script

Run the existing integration verification script to confirm everything wires up correctly:

```bash
cd /path/to/hydra-arm3
python -c "
from src.api.prediction_routes_integration import verify_integration
verify_integration()
"
```

Expected output:
```
✓ src/services/prediction_markets.py — all classes importable
✓ src/api/prediction_routes.py — prediction_router importable
✓ config/settings.py — all 7 prediction market pricing keys present
✓ OracleDataProvider.format_for_chainlink — output format verified
✓ OracleDataProvider.format_for_uma — output format verified
✓ _classify_market_domain — market domain classifier working

ALL CHECKS PASSED — prediction market integration is ready.
```

---

## Revenue Model

At 1,000 bot calls/day across the endpoint mix:

| Endpoint | Calls/day | Price | Revenue/day |
|----------|-----------|-------|-------------|
| `/v1/markets/feed` | 1,000 | $0.05 | $50 |
| `/v1/markets/signals` | 200 | $0.25 | $50 |
| `/v1/markets/signal/*` | 500 | $0.10 | $50 |
| `/v1/markets/events` | 300 | $0.15 | $45 |
| `/v1/markets/alpha` | 50 | $2.00 | $100 |
| `/v1/markets/resolution` | 20 | $1.00 | $20 |
| `/v1/oracle/uma` | 10 | $0.50 | $5 |
| `/v1/oracle/chainlink` | 10 | $0.50 | $5 |
| **Total** | | | **$325/day** |

Conservative estimate for 10 active trading bots = **~$119K/year**. At 100 bots: **~$1.2M/year**.

The free `GET /v1/markets` endpoint is designed to be indexed by bot aggregators and show up in Polymarket/Kalshi developer communities, driving organic discovery.
