"""
yield_router.py — HYDRA Balanced DeFi Yield Router
==================================================
Routes idle treasury USDC to the best risk-adjusted yield across a whitelist
of audited, overcollateralized lending venues, then compounds.

Design principles (non-negotiable):
  - Overcollateralized / audited venues ONLY. No leverage, no undercollateralized
    ("assume it gets paid") lending — that is principal-loss risk, not yield.
  - A venue is WRITE-ENABLED only after its on-chain pool address has been
    verified. Until then it is a read-only candidate: the router will report its
    APR for comparison but will never send funds to it. This prevents the
    catastrophic failure mode of depositing into a wrong/unverified address.
  - Per-venue exposure caps so a single venue can never hold the whole treasury.

Live venue:
  - Aave V3 (USDC on Base) — verified, write-enabled, delegated to
    TreasuryYieldManager (which already enforces key-controls-wallet + gas checks).

Adding a venue (e.g. Morpho/Moonwell vault, Compound III Comet):
  1. Verify the pool/vault address on https://basescan.org.
  2. Add it to the HYDRA_YIELD_VENUES env var (JSON list) with write_enabled=true:
       [{"name":"compound_v3","kind":"comet","address":"0x...","cap_usdc":"5000"}]
  3. Implement its supply/withdraw adapter here (Aave is the reference adapter).
The router then auto-allocates new deposits to whichever ENABLED venue offers the
best APR with remaining capacity.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("hydra.yield_router")


@dataclass
class Venue:
    """A yield venue in the routing whitelist."""

    name: str
    kind: str                       # "aave" | "comet" | "morpho" | ...
    write_enabled: bool = False     # only true once address is verified + adapter wired
    address: Optional[str] = None
    cap_usdc: Optional[Decimal] = None   # max USDC this venue may hold (None = uncapped)
    note: Optional[str] = None


class YieldRouter:
    """
    Selects the best write-enabled venue for new USDC deposits and reports a
    comparative APR view across all whitelisted venues.

    The Aave V3 position is managed by the supplied TreasuryYieldManager, which
    owns signing and on-chain safety. Additional venues are declared via the
    HYDRA_YIELD_VENUES env var and are read-only until explicitly verified.
    """

    def __init__(self, aave_manager) -> None:
        self._aave = aave_manager
        self.venues: list[Venue] = [
            Venue(
                name="aave_v3",
                kind="aave",
                write_enabled=True,
                address="0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",
                note="Aave V3 USDC lending — verified, live.",
            )
        ]
        self._load_extra_venues()

    def _load_extra_venues(self) -> None:
        """Load additional candidate venues from HYDRA_YIELD_VENUES (JSON)."""
        raw = os.getenv("HYDRA_YIELD_VENUES", "").strip()
        if not raw:
            return
        try:
            for v in json.loads(raw):
                self.venues.append(Venue(
                    name=str(v["name"]),
                    kind=str(v.get("kind", "unknown")),
                    write_enabled=bool(v.get("write_enabled", False)),
                    address=v.get("address"),
                    cap_usdc=Decimal(str(v["cap_usdc"])) if v.get("cap_usdc") else None,
                    note=v.get("note"),
                ))
            logger.info("YieldRouter loaded %d extra venue(s) from env.", len(self.venues) - 1)
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not parse HYDRA_YIELD_VENUES (ignored): %s", exc)

    # ------------------------------------------------------------------
    # APR discovery (read-only — works even in monitor mode)
    # ------------------------------------------------------------------

    def _venue_apr(self, venue: Venue) -> Optional[Decimal]:
        """Return the live supply APR (%) for a venue, or None if unavailable."""
        if venue.kind == "aave":
            return self._aave.get_current_apr()
        # Adapters for additional kinds (comet/morpho/...) plug in here once
        # their address is verified. Until then APR is unknown by design.
        return None

    def _venue_position(self, venue: Venue) -> Decimal:
        """Return current USDC position held in a venue."""
        if venue.kind == "aave":
            return self._aave.get_aave_balance()
        return Decimal("0")

    def compare_aprs(self) -> list[dict]:
        """Comparative APR + position snapshot across all whitelisted venues."""
        rows: list[dict] = []
        for v in self.venues:
            apr = self._venue_apr(v)
            rows.append({
                "name": v.name,
                "kind": v.kind,
                "write_enabled": v.write_enabled,
                "address": v.address,
                "supply_apr_pct": str(apr) if apr is not None else None,
                "position_usdc": str(self._venue_position(v)),
                "cap_usdc": str(v.cap_usdc) if v.cap_usdc is not None else None,
                "note": v.note,
            })
        return rows

    def best_venue(self) -> Optional[Venue]:
        """
        Pick the write-enabled venue with the highest APR that still has
        capacity. Ties / unknown APRs fall back to the first enabled venue
        (Aave), which is always safe.
        """
        enabled = [v for v in self.venues if v.write_enabled]
        if not enabled:
            return None

        def _capacity_ok(v: Venue) -> bool:
            if v.cap_usdc is None:
                return True
            return self._venue_position(v) < v.cap_usdc

        candidates = [v for v in enabled if _capacity_ok(v)] or enabled
        scored = [(self._venue_apr(v) or Decimal("-1"), v) for v in candidates]
        scored.sort(key=lambda t: t[0], reverse=True)
        return scored[0][1]

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def deposit_excess(self, wallet_balance: Decimal) -> Optional[str]:
        """
        Deposit depositable excess USDC into the best write-enabled venue.

        Returns the tx hash on a successful deposit, else None. Respects the
        chosen venue's exposure cap.
        """
        venue = self.best_venue()
        if venue is None:
            logger.info("YieldRouter: no write-enabled venue — skipping deposit.")
            return None

        if venue.kind == "aave":
            depositable = self._aave.get_depositable_amount(wallet_balance)
            if venue.cap_usdc is not None:
                room = venue.cap_usdc - self._venue_position(venue)
                depositable = min(depositable, max(Decimal("0"), room))
            if depositable <= 0:
                return None
            logger.info(
                "YieldRouter → %s (APR %s%%): depositing $%s USDC",
                venue.name, self._venue_apr(venue), f"{depositable:.2f}",
            )
            return await self._aave.deposit_to_aave(depositable)

        logger.warning(
            "YieldRouter: venue %s (%s) has no write adapter — skipping.",
            venue.name, venue.kind,
        )
        return None

    def status(self) -> dict:
        """Router status: active venue, comparative APRs, and enablement state."""
        best = self.best_venue()
        return {
            "strategy": "balanced-defi (overcollateralized, no leverage)",
            "active_venue": best.name if best else None,
            "enabled_venues": [v.name for v in self.venues if v.write_enabled],
            "candidate_venues": [v.name for v in self.venues if not v.write_enabled],
            "venues": self.compare_aprs(),
        }
