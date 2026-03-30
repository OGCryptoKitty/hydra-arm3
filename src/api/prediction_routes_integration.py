"""
HYDRA Arm 3 — Prediction Market Integration Patch

This file shows exactly what lines to add to src/main.py and confirms
what was already added to config/settings.py to wire in the prediction
market routes.

HOW TO APPLY
============

Step 1: The config/settings.py changes are ALREADY APPLIED.
        Verify with: grep "markets/signals" config/settings.py

Step 2: Apply the src/main.py changes described below.
        Three changes required (shown as diffs).

Step 3: Verify import resolution.
        Run: python -c "from src.api.prediction_routes import prediction_router; print('OK')"

Step 4: Restart the server.
        uvicorn src.main:app --host 0.0.0.0 --port 8402 --reload

--------------------------------------------------------------------
CHANGE 1 — Add import at the top of src/main.py
--------------------------------------------------------------------

Find this existing line in src/main.py:
    from src.api.routes import router
    from src.api.system_routes import system_router

Add the prediction router import immediately after:
    from src.api.prediction_routes import prediction_router

--------------------------------------------------------------------
CHANGE 2 — Register the prediction router on the FastAPI app
--------------------------------------------------------------------

In src/main.py, find the section where routers are included.
It will look like:
    app.include_router(router)
    app.include_router(system_router, prefix="/system", ...)

Add the prediction router include:
    app.include_router(prediction_router)

IMPORTANT: No prefix is needed — all prediction_router routes
already include /v1/markets/ or /v1/oracle/ in their path strings.

--------------------------------------------------------------------
CHANGE 3 — x402 Middleware: ensure /v1/markets/signal/* is covered
--------------------------------------------------------------------

The X402PaymentMiddleware in src/x402/middleware.py looks up the
incoming path in settings.PRICING to determine the required payment.

The /v1/markets/signal/{market_id} path is a parametric route.
The middleware must match it against the "/v1/markets/signal" key.

Check src/x402/middleware.py for how path matching works.
If it does exact matching, add this logic to normalize parametric paths:

    # Add this helper near the top of middleware.py path resolution:
    def _normalize_path_for_pricing(path: str) -> str:
        \"\"\"Strip path parameters for pricing lookup.\"\"\"
        # /v1/markets/signal/0xabc123 → /v1/markets/signal
        import re
        # Strip trailing segments after known prefixes
        parametric_prefixes = [
            "/v1/markets/signal/",
        ]
        for prefix in parametric_prefixes:
            if path.startswith(prefix):
                return prefix.rstrip("/")
        return path

If the middleware already uses prefix matching (check the code),
no changes are needed — it will automatically match.

--------------------------------------------------------------------
COMPLETE src/main.py DIFF (for reference)
--------------------------------------------------------------------

--- src/main.py (original excerpt)
+++ src/main.py (patched excerpt)

@@ IMPORTS SECTION @@
 from src.api.routes import router
 from src.api.system_routes import system_router
+from src.api.prediction_routes import prediction_router
 from src.runtime.automaton import HydraAutomaton

@@ ROUTER REGISTRATION SECTION @@
 # (find where app.include_router is called, typically in lifespan or at module level)
 app.include_router(router)
 app.include_router(system_router, prefix="/system", ...)
+app.include_router(prediction_router)

--------------------------------------------------------------------
VERIFICATION CHECKLIST
--------------------------------------------------------------------

After applying changes, verify these endpoints are accessible:

    curl http://localhost:8402/v1/markets/discovery
    # Expected: 200 OK with JSON containing "markets" array
    # This is the FREE endpoint — no payment required

    curl http://localhost:8402/v1/markets/pricing
    # Expected: 200 OK with JSON listing all prediction market endpoints

    curl -X POST http://localhost:8402/v1/markets/signals \\
         -H "Content-Type: application/json" \\
         -d '{"platform": "all", "category": "all"}'
    # Expected: 402 Payment Required (x402 middleware intercepted)
    # This confirms the middleware is correctly protecting paid endpoints

    curl http://localhost:8402/v1/markets/feed
    # Expected: 402 Payment Required
    # Even the cheapest endpoint ($0.05) requires payment proof

    curl http://localhost:8402/docs
    # Expected: OpenAPI docs now show "Prediction Markets" tag with all endpoints

--------------------------------------------------------------------
SETTINGS VERIFICATION
--------------------------------------------------------------------

The following entries are NOW in config/settings.py PRICING dict:

    "/v1/markets/signals"    → $0.25 USDC (250,000 base units)
    "/v1/markets/signal"     → $0.10 USDC (100,000 base units)  [prefix match for /{market_id}]
    "/v1/markets/events"     → $0.15 USDC (150,000 base units)
    "/v1/markets/resolution" → $1.00 USDC (1,000,000 base units)
    "/v1/oracle/uma"         → $0.50 USDC (500,000 base units)
    "/v1/oracle/chainlink"   → $0.50 USDC (500,000 base units)
    "/v1/markets/feed"       → $0.05 USDC (50,000 base units)

NOT in PRICING (free endpoints, middleware must skip):
    "/v1/markets/discovery"  → FREE
    "/v1/markets/pricing"    → FREE

--------------------------------------------------------------------
NEW FILES CREATED
--------------------------------------------------------------------

src/services/prediction_markets.py   (1,836 lines — service layer)
    Classes:
      PolymarketClient        — Gamma + CLOB API client
      KalshiClient            — Kalshi v2 API client (public endpoints)
      PredictionMarketAggregator — combines both platforms
      RegulatoryEventFeed     — event feed with market matching
      OracleDataProvider      — UMA / Chainlink / API3 formatters

    Module-level singletons (use these in route handlers):
      get_aggregator()        → PredictionMarketAggregator
      get_event_feed()        → RegulatoryEventFeed
      get_oracle_provider()   → OracleDataProvider

src/api/prediction_routes.py   (1,039 lines — FastAPI router)
    Router: prediction_router
    Free:   GET /v1/markets/discovery, GET /v1/markets/pricing
    Paid:   POST /v1/markets/signals ($0.25)
            POST /v1/markets/signal/{market_id} ($0.10)
            POST /v1/markets/events ($0.15)
            POST /v1/markets/resolution ($1.00)
            POST /v1/oracle/uma ($0.50)
            POST /v1/oracle/chainlink ($0.50)
            GET  /v1/markets/feed ($0.05)

config/settings.py   (MODIFIED — pricing entries added)

--------------------------------------------------------------------
DEPENDENCIES (already present in HYDRA codebase)
--------------------------------------------------------------------

The prediction market integration uses only packages already in use:
    httpx       — async HTTP client (already imported in feeds.py)
    cachetools  — TTLCache (already in feeds.py)
    fastapi     — router, HTTPException, Request (already in routes.py)
    pydantic    — BaseModel, Field (already in schemas.py)

No new pip packages required.

--------------------------------------------------------------------
API EXTERNAL RATE LIMITS
--------------------------------------------------------------------

Polymarket Gamma API (https://gamma-api.polymarket.com):
    Free tier: 1,000 requests/hour
    PolymarketClient makes at most ~12 requests per get_regulatory_markets() call
    With 5-minute TTL cache, max ~144 calls/hour at maximum bot traffic

Kalshi API (https://api.elections.kalshi.com/trade-api/v2):
    Rate limits not publicly specified; implement backoff (already handled)
    KalshiClient fetches up to 5 pages of 200 markets + 4 series lookups per call
    With 5-minute TTL cache: safe for production bot traffic

--------------------------------------------------------------------
REVENUE MODEL SUMMARY
--------------------------------------------------------------------

Bot usage pattern and projected revenue at 1,000 bot calls/day:

    /v1/markets/feed      × 1,000/day × $0.05 = $50/day
    /v1/markets/signals   ×   200/day × $0.25 = $50/day
    /v1/markets/signal/*  ×   500/day × $0.10 = $50/day
    /v1/markets/events    ×   300/day × $0.15 = $45/day
    /v1/markets/resolution ×   20/day × $1.00 = $20/day
    /v1/oracle/uma        ×   10/day  × $0.50 =  $5/day
    /v1/oracle/chainlink  ×   10/day  × $0.50 =  $5/day
                                    TOTAL = ~$225/day = ~$82K/year

Discovery endpoint (free) drives top-of-funnel traffic. Conservative
estimate for 10 active trading bots; 100+ bots achieves $820K+/year.
"""

# ─────────────────────────────────────────────────────────────
# Programmatic patch — can be run directly to verify imports work
# ─────────────────────────────────────────────────────────────


def verify_integration() -> None:
    """
    Run this to verify the prediction market integration is correctly wired.
    Usage: python -c "from src.api.prediction_routes_integration import verify_integration; verify_integration()"
    """
    import sys
    errors: list[str] = []

    # 1. Check service layer imports
    try:
        from src.services.prediction_markets import (  # noqa: F401
            PolymarketClient,
            KalshiClient,
            PredictionMarketAggregator,
            RegulatoryEventFeed,
            OracleDataProvider,
            get_aggregator,
            get_event_feed,
            get_oracle_provider,
        )
        print("✓ src/services/prediction_markets.py — all classes importable")
    except ImportError as exc:
        errors.append(f"✗ prediction_markets.py import failed: {exc}")

    # 2. Check router imports
    try:
        from src.api.prediction_routes import prediction_router  # noqa: F401
        print("✓ src/api/prediction_routes.py — prediction_router importable")
    except ImportError as exc:
        errors.append(f"✗ prediction_routes.py import failed: {exc}")

    # 3. Check settings
    try:
        import config.settings as settings
        required_keys = [
            "/v1/markets/signals",
            "/v1/markets/signal",
            "/v1/markets/events",
            "/v1/markets/resolution",
            "/v1/oracle/uma",
            "/v1/oracle/chainlink",
            "/v1/markets/feed",
        ]
        missing = [k for k in required_keys if k not in settings.PRICING]
        if missing:
            errors.append(f"✗ settings.PRICING missing keys: {missing}")
        else:
            print(f"✓ config/settings.py — all {len(required_keys)} prediction market pricing keys present")
    except Exception as exc:
        errors.append(f"✗ settings check failed: {exc}")

    # 4. Check OracleDataProvider produces valid Chainlink format
    try:
        from src.services.prediction_markets import OracleDataProvider
        provider = OracleDataProvider()
        result = provider.format_for_chainlink({
            "jobRunID": "test-1",
            "data": {"result": 1, "value": "YES"},
        })
        assert result["jobRunID"] == "test-1"
        assert result["statusCode"] == 200
        assert "result" in result["data"]
        print("✓ OracleDataProvider.format_for_chainlink — output format verified")
    except Exception as exc:
        errors.append(f"✗ Chainlink format check failed: {exc}")

    # 5. Check UMA formatter
    try:
        from src.services.prediction_markets import OracleDataProvider
        provider = OracleDataProvider()
        result = provider.format_for_uma(
            market_question="Will the SEC approve a spot Solana ETF by June 30, 2026?",
            resolution_data={
                "resolved": True,
                "resolution_value": "Yes",
                "confidence": 75,
                "evidence_summary": "SEC issued approval order on March 28, 2026.",
                "sources": ["sec.gov/litigation/"],
            },
        )
        assert result["uma_version"] == "OOv2"
        assert result["proposed_price"] == 1_000_000_000_000_000_000  # 1e18 = Yes
        assert "ancillary_data_hex" in result
        print("✓ OracleDataProvider.format_for_uma — output format verified")
    except Exception as exc:
        errors.append(f"✗ UMA format check failed: {exc}")

    # 6. Check market classifier
    try:
        from src.services.prediction_markets import _classify_market_domain
        assert _classify_market_domain("Will the Fed cut rates in April 2026?") == "fed_rate"
        assert _classify_market_domain("Will SEC approve spot Solana ETF?") in ("crypto_etf", "sec_enforcement")
        assert _classify_market_domain("Will GENIUS Act pass in 2026?") == "crypto_legislation"
        print("✓ _classify_market_domain — market domain classifier working")
    except Exception as exc:
        errors.append(f"✗ Domain classifier check failed: {exc}")

    print()
    if errors:
        print(f"FAILED — {len(errors)} error(s):")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED — prediction market integration is ready.")
        print()
        print("Next steps:")
        print("  1. Add 'from src.api.prediction_routes import prediction_router' to src/main.py")
        print("  2. Add 'app.include_router(prediction_router)' to src/main.py")
        print("  3. Restart server: uvicorn src.main:app --host 0.0.0.0 --port 8402")
        print("  4. Test: curl http://localhost:8402/v1/markets/discovery")


if __name__ == "__main__":
    verify_integration()
