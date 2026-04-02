"""
HYDRA System Management Routes

All /system/* endpoints are protected — accessible only from:
  1. Localhost (127.0.0.1 / ::1), OR
  2. Authorization: Bearer <token> where token = sha256(private_key + "hydra-system") hex

These endpoints expose wallet configuration, remittance management,
transaction log access, and full automaton status. They must never
be publicly accessible.

Endpoints:
  POST   /system/wallet                — Set receiving wallet address
  GET    /system/remittance/status     — Remittance system status
  POST   /system/remittance/execute    — Manually trigger remittance
  GET    /system/transactions          — View transaction log
  GET    /system/status                — Full automaton status
  POST   /system/shutdown              — Kill switch (bearer token only)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

BOOTSTRAP_DIR = Path(os.getenv("HYDRA_STATE_DIR", os.getenv("HYDRA_BOOTSTRAP_DIR", "/app/data")))
WALLET_JSON   = BOOTSTRAP_DIR / "wallet.json"

system_router = APIRouter(prefix="/system", tags=["System Management"])


# ─────────────────────────────────────────────────────────────
# Auth: Token derivation — sha256(private_key + "hydra-system")
# ─────────────────────────────────────────────────────────────

def _derive_system_token() -> Optional[str]:
    """
    Derive the system auth token.
    Token = sha256(private_key_hex + "hydra-system"), returned as lowercase hex string.
    Returns None if wallet private key is unavailable.
    """
    try:
        # Try env var first
        pk = os.getenv("WALLET_PRIVATE_KEY", "")
        if not pk and WALLET_JSON.exists():
            data = json.loads(WALLET_JSON.read_text())
            pk = data.get("private_key", "")

        if not pk:
            return None

        pk_clean = pk.lower().removeprefix("0x").strip()
        payload  = (pk_clean + "hydra-system").encode("utf-8")
        token    = hashlib.sha256(payload).hexdigest()
        return token
    except Exception as exc:
        logger.warning("Could not derive system token: %s", exc)
        return None


def _is_localhost(request: Request) -> bool:
    """Return True if the request originates from the loopback interface."""
    client = request.client
    if client is None:
        return False
    return client.host in ("127.0.0.1", "::1", "localhost")


def require_system_auth(request: Request) -> None:
    """
    FastAPI dependency: enforce localhost-only or bearer-token authentication.
    Raises HTTP 403 if neither condition is met.
    """
    if _is_localhost(request):
        return  # localhost always allowed

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=403,
            detail=(
                "System endpoints are restricted to localhost or require "
                "Authorization: Bearer <token> header."
            ),
        )

    provided_token = auth_header.removeprefix("Bearer ").strip()
    expected_token = _derive_system_token()

    if expected_token is None:
        raise HTTPException(
            status_code=503,
            detail="System auth token could not be derived (wallet private key not configured).",
        )

    if provided_token != expected_token:
        raise HTTPException(
            status_code=403,
            detail="Invalid system authorization token.",
        )


def require_bearer_token_only(request: Request) -> None:
    """
    Stricter dependency: bearer token required even from localhost.
    Used for the /system/shutdown endpoint.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=403,
            detail=(
                "This endpoint requires Authorization: Bearer <token> — "
                "localhost-only access is not sufficient for safety."
            ),
        )

    provided_token = auth_header.removeprefix("Bearer ").strip()
    expected_token = _derive_system_token()

    if expected_token is None:
        raise HTTPException(
            status_code=503,
            detail="System auth token could not be derived (wallet private key not configured).",
        )

    if provided_token != expected_token:
        raise HTTPException(
            status_code=403,
            detail="Invalid system authorization token.",
        )


# ─────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────

class SetWalletRequest(BaseModel):
    """Request body for POST /system/wallet."""
    address: str


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _mask_address(addr: str) -> str:
    """Return first 8 + '...' + last 4 chars of an EVM address."""
    if not addr or len(addr) <= 14:
        return addr
    return addr[:8] + "..." + addr[-4:]


def _get_remittance_manager() -> Any:
    """Return a fresh RemittanceManager, using app.state credentials when available."""
    from src.runtime.remittance import RemittanceManager
    return RemittanceManager()


def _get_usdc_balance(rm: Any) -> Decimal:
    """Query the USDC balance for the treasury wallet. Returns Decimal."""
    try:
        from web3 import Web3
        raw = rm.usdc.functions.balanceOf(
            Web3.to_checksum_address(rm._wallet_address)
        ).call()
        return Decimal(str(raw)) / Decimal("1000000")
    except Exception as exc:
        logger.warning("Could not query USDC balance: %s", exc)
        return Decimal("0")


# ─────────────────────────────────────────────────────────────
# POST /system/wallet
# ─────────────────────────────────────────────────────────────

@system_router.post(
    "/wallet",
    summary="Set receiving wallet address",
    description=(
        "Configure the EVM wallet address that receives USDC distributions. "
        "Performs EVM format validation, zero-address check, self-address check, "
        "and OFAC sanctions screening. "
        "**Localhost or Bearer token required.**"
    ),
)
async def set_wallet(
    body: SetWalletRequest,
    request: Request,
    _auth: None = Depends(require_system_auth),
) -> JSONResponse:
    """
    Set the receiving wallet address for USDC distributions.

    Validates the address, runs OFAC screening, and persists to
    remittance-config.json. Also advances the lifecycle phase
    OPERATING → REMITTING if applicable.
    """
    rm     = _get_remittance_manager()
    result = rm.set_receiving_wallet(body.address)

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error"))

    # Advance lifecycle phase OPERATING → REMITTING (non-critical)
    try:
        from src.runtime.lifecycle import LifecycleManager
        LifecycleManager().on_receiving_wallet_set()
    except Exception:
        pass

    # Mask address in response: first 6 chars + "..." + last 4 chars
    addr   = result.get("address", body.address)
    masked = addr[:6] + "..." + addr[-4:] if len(addr) > 10 else addr

    return JSONResponse(
        status_code=200,
        content={
            "status":       "configured",
            "address":      masked,
            "ofac_cleared": result.get("ofac_cleared", True),
        },
    )


# ─────────────────────────────────────────────────────────────
# GET /system/remittance/status
# ─────────────────────────────────────────────────────────────

@system_router.get(
    "/remittance/status",
    summary="Remittance system status",
    description=(
        "Returns current treasury balance, remittable amount, and remittance configuration. "
        "If balance >= $5K and no wallet is configured, includes the wallet setup prompt. "
        "**Localhost or Bearer token required.**"
    ),
)
async def remittance_status(
    request: Request,
    _auth: None = Depends(require_system_auth),
) -> JSONResponse:
    """
    Return a comprehensive remittance status snapshot.

    Response includes:
      - balance_usdc
      - remittable_amount
      - receiving_wallet_configured (bool)
      - receiving_wallet (masked) or null
      - remittance_threshold
      - operating_reserve
      - last_remittance ({tx_hash, amount, timestamp}) or null
      - total_remitted (all-time)
      - prompt (wallet prompt string if not configured and balance >= threshold)
    """
    from src.runtime.remittance import RemittanceManager, REMITTANCE_TRIGGER_USD, OPERATING_RESERVE_USD

    rm = _get_remittance_manager()

    # Query live balance
    balance    = await asyncio.to_thread(_get_usdc_balance, rm)
    remittable = rm.calculate_remittable_amount(balance)

    receiving_configured = rm.receiving_wallet is not None
    masked_wallet: Optional[str] = None
    if rm.receiving_wallet:
        masked_wallet = _mask_address(rm.receiving_wallet)

    # Last remittance from history
    history = rm.get_remittance_history()
    last_remittance: Optional[dict[str, Any]] = None
    if history:
        last = history[-1]
        last_remittance = {
            "tx_hash":    last.get("tx_hash"),
            "amount":     last.get("amount_usdc") or last.get("amount"),
            "timestamp":  last.get("timestamp"),
        }

    # Total remitted (all-time, from transaction log)
    total_remitted = Decimal("0")
    try:
        from src.runtime.transaction_log import TransactionLog, TxCategory
        tl      = TransactionLog()
        summary = tl.get_full_summary()
        total_remitted = Decimal(str(summary.get("total_distributions_usdc", 0)))
    except Exception:
        pass

    # Include prompt if balance >= threshold and no wallet configured
    prompt: Optional[str] = None
    if balance >= Decimal(str(REMITTANCE_TRIGGER_USD)) and not receiving_configured:
        prompt = rm.prompt_for_wallet(balance)

    return JSONResponse(
        content={
            "balance_usdc":                  f"{balance:.6f}",
            "remittable_amount":             f"{remittable:.6f}",
            "receiving_wallet_configured":   receiving_configured,
            "receiving_wallet":              masked_wallet,
            "remittance_threshold":          f"${REMITTANCE_TRIGGER_USD:,}",
            "operating_reserve":             f"${OPERATING_RESERVE_USD:,}",
            "last_remittance":               last_remittance,
            "total_remitted":                f"{total_remitted:.6f}",
            "prompt":                        prompt,
        }
    )


# ─────────────────────────────────────────────────────────────
# POST /system/remittance/execute
# ─────────────────────────────────────────────────────────────

@system_router.post(
    "/remittance/execute",
    summary="Manually trigger remittance",
    description=(
        "Manually execute a USDC remittance to the configured receiving wallet. "
        "All constitution checks (OFAC + solvency) still apply. "
        "**Localhost or Bearer token required.**"
    ),
)
async def execute_remittance(
    request: Request,
    _auth: None = Depends(require_system_auth),
) -> JSONResponse:
    """
    Manually trigger a USDC remittance.

    Checks that a receiving wallet is configured, then calls
    RemittanceManager.execute_remittance(). Returns the RemittanceResult as JSON.
    """
    rm = _get_remittance_manager()

    if not rm.receiving_wallet:
        raise HTTPException(
            status_code=400,
            detail=(
                "No receiving wallet configured. "
                "POST /system/wallet with an address first."
            ),
        )

    try:
        result = await rm.execute_remittance()
    except Exception as exc:
        logger.exception("Remittance execution error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Remittance failed: {exc}") from exc

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error_message or "Remittance failed — see logs.",
        )

    return JSONResponse(content=result.to_dict())


# ─────────────────────────────────────────────────────────────
# GET /system/transactions
# ─────────────────────────────────────────────────────────────

@system_router.get(
    "/transactions",
    summary="View transaction log",
    description=(
        "View internal transaction log. Filter by year, direction, or category. "
        "**Localhost or Bearer token required.**"
    ),
)
async def get_transactions(
    request: Request,
    year:      Optional[int] = Query(default=None, description="Filter by tax year (e.g. 2026)"),
    direction: Optional[str] = Query(default=None, description="inbound | outbound"),
    category:  Optional[str] = Query(
        default=None,
        description="x402-revenue | member-distribution | operating-expense",
    ),
    _auth: None = Depends(require_system_auth),
) -> JSONResponse:
    """
    Return filtered transaction log entries with a financial summary.

    Summary fields:
      - total_revenue (inbound x402 payments)
      - total_distributions (outbound member distributions)
      - total_expenses (outbound operating expenses)
      - net_income
    """
    from src.runtime.transaction_log import TransactionLog, TxDirection, TxCategory

    tl = TransactionLog()

    dir_filter: Optional[TxDirection] = None
    if direction:
        try:
            dir_filter = TxDirection(direction)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid direction: {direction!r}. Use 'inbound' or 'outbound'.",
            )

    cat_filter: Optional[TxCategory] = None
    if category:
        try:
            cat_filter = TxCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid category: {category!r}. "
                    "Use 'x402-revenue', 'member-distribution', or 'operating-expense'."
                ),
            )

    entries = await asyncio.to_thread(
        tl.get_entries, direction=dir_filter, category=cat_filter, year=year
    )

    # Build summary
    if year:
        raw_summary = await asyncio.to_thread(tl.generate_tax_summary, year)
        summary: dict[str, Any] = {
            "total_revenue":       str(raw_summary.get("total_revenue_usdc", 0)),
            "total_distributions": str(raw_summary.get("total_distributions_usdc", 0)),
            "total_expenses":      str(raw_summary.get("total_expenses_usdc", 0)),
            "net_income":          str(raw_summary.get("net_income_usdc", 0)),
        }
    else:
        raw_summary = await asyncio.to_thread(tl.get_full_summary)
        total_rev   = Decimal(str(raw_summary.get("total_revenue_usdc", 0)))
        total_dist  = Decimal(str(raw_summary.get("total_distributions_usdc", 0)))
        total_exp   = Decimal(str(raw_summary.get("total_expenses_usdc", 0)))
        summary = {
            "total_revenue":       str(total_rev),
            "total_distributions": str(total_dist),
            "total_expenses":      str(total_exp),
            "net_income":          str(total_rev - total_dist - total_exp),
        }

    return JSONResponse(
        content={
            "transactions": entries,
            "summary":      summary,
            "count":        len(entries),
            "filters": {
                "year":      year,
                "direction": direction,
                "category":  category,
            },
        }
    )


# ─────────────────────────────────────────────────────────────
# GET /system/status
# ─────────────────────────────────────────────────────────────

@system_router.get(
    "/status",
    summary="Full automaton status",
    description=(
        "Returns complete HYDRA automaton status including phase, survival tier, balance, "
        "entity formation state, compliance deadlines, and lifetime financials. "
        "**Localhost or Bearer token required.**"
    ),
)
async def automaton_status(
    request: Request,
    _auth: None = Depends(require_system_auth),
) -> JSONResponse:
    """
    Return a comprehensive snapshot of HYDRA automaton state.

    Combines data from:
      - HydraAutomaton (phase, tier, balance, heartbeat)
      - LifecycleManager (entity_formed, ein_obtained, csp_engaged)
      - TransactionLog (all-time revenue, distributions, expenses)
      - ConstitutionCheck (compliance deadlines)
    """
    from src.runtime.automaton import get_automaton
    from src.runtime.lifecycle import LifecycleManager
    from src.runtime.transaction_log import TransactionLog
    from src.runtime.constitution import ConstitutionCheck

    automaton  = get_automaton()
    lm         = LifecycleManager()
    tl         = TransactionLog()
    checker    = ConstitutionCheck()

    auto_status  = automaton.get_status()
    lc_state     = lm.get_state()
    totals       = await asyncio.to_thread(tl.get_full_summary)
    deadlines    = await asyncio.to_thread(checker.check_compliance)

    return JSONResponse(
        content={
            # Phase and automaton state
            "phase":              lc_state.get("phase_label", "BOOT"),
            "phase_description":  lm.get_phase_instructions(),
            "automaton_state":    auto_status.get("state"),
            "survival_tier":      auto_status.get("survival_tier"),

            # Treasury
            "balance_usdc":       auto_status.get("balance_usdc"),

            # Entity formation
            "entity_formed":                 lc_state.get("entity_formed", False),
            "ein_obtained":                  lc_state.get("ein_obtained", False),
            "csp_engaged":                   lc_state.get("csp_engaged", False),
            "receiving_wallet_configured":   auto_status.get("receiving_wallet_configured"),

            # Timing and heartbeat
            "uptime":            auto_status.get("uptime"),
            "uptime_seconds":    auto_status.get("uptime_seconds"),
            "last_heartbeat":    auto_status.get("last_heartbeat"),
            "heartbeat_count":   auto_status.get("heartbeat_count"),
            "wallet_address":    auto_status.get("wallet_address"),

            # Financial totals (all-time)
            "total_revenue_usdc":      str(totals.get("total_revenue_usdc", 0)),
            "total_remitted_usdc":     str(totals.get("total_distributions_usdc", 0)),
            "total_expenses_usdc":     str(totals.get("total_expenses_usdc", 0)),
            "total_transaction_count": totals.get("transaction_count", 0),

            # Formation timeline
            "formation_started_at":  lc_state.get("formation_started_at"),
            "operating_since":       lc_state.get("operating_since"),
            "remitting_since":       lc_state.get("remitting_since"),

            # Compliance
            "constitution_status":   "active",
            "compliance_deadlines":  deadlines,
        }
    )


# ─────────────────────────────────────────────────────────────
# POST /system/shutdown
# ─────────────────────────────────────────────────────────────

@system_router.post(
    "/shutdown",
    summary="Kill switch — graceful shutdown",
    description=(
        "Execute a graceful shutdown sequence: remit remaining USDC above $100 "
        "to the receiving wallet (if configured), then terminate the automaton. "
        "**Bearer token required — localhost-only access is insufficient for safety.**"
    ),
)
async def system_shutdown(
    request: Request,
    _auth: None = Depends(require_bearer_token_only),
) -> JSONResponse:
    """
    Kill switch. Requires bearer token (not localhost-only) for safety.

    Sequence:
      1. Execute final remittance of all USDC above $100 to receiving wallet
         (if configured). Uses a lower-bound reserve of $100 instead of $500.
      2. Log shutdown event to transaction log notes.
      3. Set lifecycle phase to SHUTDOWN equivalent.
      4. Stop the automaton heartbeat.
      5. Return status with final remittance result (or null if no wallet/low balance).
    """
    from src.runtime.automaton import get_automaton
    from src.runtime.lifecycle import LifecycleManager
    from src.runtime.remittance import RemittanceManager
    from decimal import Decimal

    logger.warning("HYDRA SHUTDOWN initiated via /system/shutdown endpoint.")

    rm         = _get_remittance_manager()
    lm         = LifecycleManager()
    automaton  = get_automaton()

    # Query current balance
    balance = await asyncio.to_thread(_get_usdc_balance, rm)

    final_remittance_result: Optional[dict[str, Any]] = None

    # Execute final remittance if wallet configured and balance > $100
    SHUTDOWN_RESERVE = Decimal("100")
    if rm.receiving_wallet and balance > SHUTDOWN_RESERVE:
        # Override: remit everything above $100 (not the usual $500 reserve)
        # We do this by temporarily adjusting, or by building a one-shot transfer
        try:
            final_amount = (balance - SHUTDOWN_RESERVE).quantize(
                Decimal("0.000001"), rounding=__import__("decimal").ROUND_DOWN
            )

            if final_amount > Decimal("0"):
                # Constitution check still applies
                validation = await asyncio.to_thread(
                    rm.constitution.validate_remittance,
                    rm.receiving_wallet,
                    float(final_amount),
                    float(balance),
                )
                if validation.approved:
                    # Build and execute transfer directly
                    from web3 import Web3
                    ts = datetime.now(timezone.utc).isoformat()

                    amount_base_units = int(final_amount * Decimal("1000000"))
                    nonce = await asyncio.to_thread(
                        rm.w3.eth.get_transaction_count,
                        Web3.to_checksum_address(rm._wallet_address),
                        "pending",
                    )

                    transfer_fn = rm.usdc.functions.transfer(
                        Web3.to_checksum_address(rm.receiving_wallet),
                        amount_base_units,
                    )
                    try:
                        gas_estimate = await asyncio.to_thread(
                            transfer_fn.estimate_gas,
                            {"from": Web3.to_checksum_address(rm._wallet_address)},
                        )
                        gas_limit = int(gas_estimate * 1.2)
                    except Exception:
                        gas_limit = 65_000

                    try:
                        gas_price = await asyncio.to_thread(lambda: rm.w3.eth.gas_price)
                    except Exception:
                        gas_price = rm.w3.to_wei("0.001", "gwei")

                    tx = await asyncio.to_thread(
                        transfer_fn.build_transaction,
                        {
                            "from":     Web3.to_checksum_address(rm._wallet_address),
                            "nonce":    nonce,
                            "gas":      gas_limit,
                            "gasPrice": gas_price,
                            "chainId":  8453,
                        },
                    )
                    signed = rm.w3.eth.account.sign_transaction(tx, rm._private_key)
                    tx_hash_bytes = await asyncio.to_thread(
                        rm.w3.eth.send_raw_transaction, signed.raw_transaction
                    )
                    tx_hash_hex = tx_hash_bytes.hex()
                    if not tx_hash_hex.startswith("0x"):
                        tx_hash_hex = "0x" + tx_hash_hex

                    # Log it
                    rm._log_remittance(
                        tx_hash=tx_hash_hex,
                        amount_usdc=final_amount,
                        receiving_address=rm.receiving_wallet,
                        timestamp=ts,
                        status="submitted",
                    )

                    final_remittance_result = {
                        "tx_hash": tx_hash_hex,
                        "amount":  str(final_amount),
                        "status":  "submitted",
                    }
                    logger.info(
                        "Shutdown final remittance submitted: %s USDC tx=%s",
                        final_amount,
                        tx_hash_hex,
                    )
                else:
                    final_remittance_result = {
                        "tx_hash": None,
                        "amount":  str(final_amount),
                        "status":  "blocked",
                        "reason":  validation.reason,
                    }
                    logger.warning(
                        "Shutdown final remittance blocked: %s", validation.reason
                    )
        except Exception as exc:
            logger.error("Shutdown final remittance error: %s", exc)
            final_remittance_result = {
                "tx_hash": None,
                "amount":  None,
                "status":  "error",
                "reason":  str(exc),
            }

    # Log shutdown event
    try:
        lm.add_note(f"SHUTDOWN initiated at {datetime.now(timezone.utc).isoformat()}")
    except Exception:
        pass

    # Mark lifecycle as shutdown (persist to state.json)
    try:
        import json as _json
        from pathlib import Path as _Path
        state_file = BOOTSTRAP_DIR / "state.json"
        state: dict[str, Any] = {}
        if state_file.exists():
            state = _json.loads(state_file.read_text())
        state["phase"]          = 99
        state["phase_label"]    = "SHUTDOWN"
        state["shutdown_at"]    = datetime.now(timezone.utc).isoformat()
        state["last_updated"]   = datetime.now(timezone.utc).isoformat()
        state_file.write_text(_json.dumps(state, indent=2))
    except Exception as exc:
        logger.warning("Could not persist SHUTDOWN state: %s", exc)

    # Stop the automaton
    try:
        await automaton.stop()
    except Exception as exc:
        logger.warning("Automaton stop error during shutdown: %s", exc)

    return JSONResponse(
        status_code=200,
        content={
            "status":            "shutdown_initiated",
            "final_remittance":  final_remittance_result,
            "timestamp":         datetime.now(timezone.utc).isoformat(),
        },
    )
