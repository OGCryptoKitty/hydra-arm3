"""
transaction_log.py — Append-Only Transaction Log (Tax Compliance)
==================================================================
Immutable JSONL audit trail for all inbound and outbound USDC flows.

Privacy guarantee
-----------------
Records wallet addresses ONLY. The log NEVER stores:
    - Natural person names
    - Identity documents
    - Email addresses
    - IP addresses
    - Any personally identifiable information (PII)

Schema per record::

    {
        "timestamp":           str   ISO-8601 UTC,
        "tx_hash":             str   0x-prefixed transaction hash,
        "direction":           str   "inbound" | "outbound",
        "category":            str   see below,
        "amount_usdc":         str   decimal string (6dp precision),
        "counterparty_address":str   checksummed Ethereum address,
        "note":                str   optional memo (no PII),
    }

Categories
----------
    Inbound  : "x402-revenue"
    Outbound : "member-distribution" | "operating-expense"
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hydra.transaction_log")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STATE_DIR: Path = Path(
    os.getenv("HYDRA_STATE_DIR", os.getenv("HYDRA_BOOTSTRAP_DIR", "/tmp/hydra-data"))
)
LOG_FILE: Path = _STATE_DIR / "transactions.jsonl"

INBOUND_CATEGORIES = frozenset({"x402-revenue"})
OUTBOUND_CATEGORIES = frozenset({"member-distribution", "operating-expense"})


# ---------------------------------------------------------------------------
# Enums (used by system_routes.py, remittance.py)
# ---------------------------------------------------------------------------


class TxDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class TxCategory(str, Enum):
    X402_REVENUE = "x402-revenue"
    MEMBER_DISTRIBUTION = "member-distribution"
    OPERATING_EXPENSE = "operating-expense"


# ---------------------------------------------------------------------------
# TransactionLog
# ---------------------------------------------------------------------------


class TransactionLog:
    """
    Append-only JSONL transaction log for USDC flows.

    Each write is a single atomic ``append`` to the log file.
    Reads are full-file scans with optional filters.

    Parameters
    ----------
    log_file : Path, optional
        Override the default log file path (useful for testing).
    """

    def __init__(self, log_file: Optional[Path] = None) -> None:
        self._log_file: Path = log_file or LOG_FILE
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info("TransactionLog initialised at %s", self._log_file)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, record: Dict[str, Any]) -> None:
        """Atomically append a single JSON record to the log file."""
        line = json.dumps(record, ensure_ascii=False)
        try:
            with self._log_file.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            logger.error("Failed to write transaction log: %s", exc)
            raise

    def _build_record(
        self,
        tx_hash: str,
        amount_usdc: Decimal,
        counterparty_address: str,
        direction: str,
        category: str,
        note: str = "",
    ) -> Dict[str, Any]:
        """Construct a log record dict. Never includes PII."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tx_hash": tx_hash,
            "direction": direction,
            "category": category,
            "amount_usdc": str(amount_usdc.quantize(Decimal("0.000001"))),
            "counterparty_address": counterparty_address,
            "note": note,
        }

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    def log_inbound(
        self,
        tx_hash: str,
        amount_usdc: Decimal,
        from_address: str,
        category: str = "x402-revenue",
        note: str = "",
    ) -> None:
        """
        Record an inbound payment.

        Parameters
        ----------
        tx_hash : str
            On-chain transaction hash.
        amount_usdc : Decimal
            Amount received in USDC.
        from_address : str
            Counterparty Ethereum address (no PII).
        category : str
            Default "x402-revenue".
        note : str, optional
            Brief memo — must NOT contain any PII.
        """
        if category not in INBOUND_CATEGORIES:
            logger.warning(
                "Non-standard inbound category '%s' — accepted but not canonical.",
                category,
            )
        record = self._build_record(
            tx_hash=tx_hash,
            amount_usdc=amount_usdc,
            counterparty_address=from_address,
            direction="inbound",
            category=category,
            note=note,
        )
        self._append(record)
        logger.info(
            "LOG INBOUND | %s USDC | category=%s | from=%s | tx=%s",
            amount_usdc,
            category,
            from_address,
            tx_hash,
        )

    def log_outbound(
        self,
        tx_hash: str,
        amount_usdc: Decimal,
        to_address: str,
        category: str,
        note: str = "",
    ) -> None:
        """
        Record an outbound payment.

        Parameters
        ----------
        tx_hash : str
            On-chain transaction hash.
        amount_usdc : Decimal
            Amount sent in USDC.
        to_address : str
            Counterparty Ethereum address (no PII).
        category : str
            Must be "member-distribution" or "operating-expense".
        note : str, optional
            Brief memo — must NOT contain any PII.
        """
        if category not in OUTBOUND_CATEGORIES:
            raise ValueError(
                f"Invalid outbound category '{category}'. "
                f"Must be one of: {sorted(OUTBOUND_CATEGORIES)}"
            )
        record = self._build_record(
            tx_hash=tx_hash,
            amount_usdc=amount_usdc,
            counterparty_address=to_address,
            direction="outbound",
            category=category,
            note=note,
        )
        self._append(record)
        logger.info(
            "LOG OUTBOUND | %s USDC | category=%s | to=%s | tx=%s",
            amount_usdc,
            category,
            to_address,
            tx_hash,
        )

    # ------------------------------------------------------------------
    # Read / filter API
    # ------------------------------------------------------------------

    def get_transactions(
        self,
        year: Optional[int] = None,
        direction: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Read and optionally filter transactions from the log.

        Parameters
        ----------
        year : int, optional
            Filter to a specific calendar year (UTC timestamp).
        direction : str, optional
            "inbound" or "outbound".
        category : str, optional
            Exact category string match.

        Returns
        -------
        list of dict
            Matching transaction records.
        """
        if not self._log_file.exists():
            return []

        results: List[Dict[str, Any]] = []
        try:
            with self._log_file.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record: Dict[str, Any] = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed log line: %r", line[:120])
                        continue

                    # Year filter
                    if year is not None:
                        ts_str = record.get("timestamp", "")
                        try:
                            ts_year = datetime.fromisoformat(ts_str).year
                        except (ValueError, TypeError):
                            continue
                        if ts_year != year:
                            continue

                    # Direction filter
                    if direction is not None and record.get("direction") != direction:
                        continue

                    # Category filter
                    if category is not None and record.get("category") != category:
                        continue

                    results.append(record)
        except OSError as exc:
            logger.error("Error reading transaction log: %s", exc)

        return results

    # ------------------------------------------------------------------
    # Tax summary
    # ------------------------------------------------------------------

    def generate_tax_summary(self, year: int) -> Dict[str, Any]:
        """
        Compute annual tax summary figures from the log.

        Parameters
        ----------
        year : int
            Calendar year (UTC).

        Returns
        -------
        dict
            Keys:
                total_revenue         — sum of all inbound USDC
                total_distributions   — sum of member-distribution outbound
                total_expenses        — sum of operating-expense outbound
                net_income            — total_revenue - total_expenses
                transaction_count     — total records in the year
                year                  — the year summarised
        """
        records = self.get_transactions(year=year)
        total_revenue = Decimal("0")
        total_distributions = Decimal("0")
        total_expenses = Decimal("0")

        for record in records:
            try:
                amount = Decimal(record["amount_usdc"])
            except (KeyError, ValueError):
                logger.warning("Skipping record with invalid amount: %s", record.get("tx_hash"))
                continue

            direction = record.get("direction")
            category = record.get("category")

            if direction == "inbound":
                total_revenue += amount
            elif direction == "outbound":
                if category == "member-distribution":
                    total_distributions += amount
                elif category == "operating-expense":
                    total_expenses += amount

        net_income = total_revenue - total_expenses

        summary = {
            "year": year,
            "total_revenue": str(total_revenue.quantize(Decimal("0.01"))),
            "total_distributions": str(total_distributions.quantize(Decimal("0.01"))),
            "total_expenses": str(total_expenses.quantize(Decimal("0.01"))),
            "net_income": str(net_income.quantize(Decimal("0.01"))),
            "transaction_count": len(records),
        }
        logger.info("Tax summary for %d: %s", year, summary)
        return summary

    # ------------------------------------------------------------------
    # Extended API (used by system_routes, remittance, metrics)
    # ------------------------------------------------------------------

    def get_entries(
        self,
        direction: Optional[TxDirection] = None,
        category: Optional[TxCategory] = None,
        year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Filter transactions using typed enums. Wraps get_transactions."""
        return self.get_transactions(
            year=year,
            direction=direction.value if direction else None,
            category=category.value if category else None,
        )

    def get_full_summary(self) -> Dict[str, Any]:
        """
        Compute an all-time financial summary across all records.

        Returns dict with keys:
            total_revenue_usdc, total_distributions_usdc,
            total_expenses_usdc, net_profit_usdc, transaction_count,
            revenue_by_endpoint.
        """
        records = self.get_transactions()
        total_revenue = Decimal("0")
        total_distributions = Decimal("0")
        total_expenses = Decimal("0")
        revenue_by_endpoint: Dict[str, Dict[str, Any]] = {}

        for record in records:
            try:
                amount = Decimal(record["amount_usdc"])
            except (KeyError, ValueError):
                continue

            direction = record.get("direction")
            category = record.get("category")

            if direction == "inbound":
                total_revenue += amount
                endpoint = record.get("note", "")
                if endpoint:
                    ep_data = revenue_by_endpoint.setdefault(
                        endpoint, {"revenue_usdc": Decimal("0"), "calls": 0}
                    )
                    ep_data["revenue_usdc"] += amount
                    ep_data["calls"] += 1
            elif direction == "outbound":
                if category == "member-distribution":
                    total_distributions += amount
                elif category == "operating-expense":
                    total_expenses += amount

        # Serialize Decimals in revenue_by_endpoint
        serialized_endpoints = {}
        for ep, data in revenue_by_endpoint.items():
            serialized_endpoints[ep] = {
                "revenue_usdc": str(data["revenue_usdc"].quantize(Decimal("0.01"))),
                "calls": data["calls"],
            }

        return {
            "total_revenue_usdc": str(total_revenue.quantize(Decimal("0.01"))),
            "total_distributions_usdc": str(total_distributions.quantize(Decimal("0.01"))),
            "total_expenses_usdc": str(total_expenses.quantize(Decimal("0.01"))),
            "net_profit_usdc": str((total_revenue - total_expenses).quantize(Decimal("0.01"))),
            "transaction_count": len(records),
            "revenue_by_endpoint": serialized_endpoints,
        }

    def log(
        self,
        tx_hash: str,
        direction: TxDirection,
        category: TxCategory,
        amount_usdc: float,
        counterparty_address: str,
        note: str = "",
        timestamp: Optional[str] = None,
    ) -> None:
        """Generic log method accepting TxDirection/TxCategory enums."""
        amount_dec = Decimal(str(amount_usdc))
        if direction == TxDirection.INBOUND:
            self.log_inbound(
                tx_hash=tx_hash,
                amount_usdc=amount_dec,
                from_address=counterparty_address,
                category=category.value,
                note=note,
            )
        else:
            self.log_outbound(
                tx_hash=tx_hash,
                amount_usdc=amount_dec,
                to_address=counterparty_address,
                category=category.value,
                note=note,
            )
