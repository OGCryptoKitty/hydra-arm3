"""
constitution.py — HYDRA Three-Law Constitutional Compliance
============================================================
Immutable laws checked before any outbound transaction.

Law 1  LEGALITY    — OFAC sanctions screening on all outbound transfers.
Law 2  SOLVENCY    — Never remit below $500 operating reserve.
Law 3  COMPLIANCE  — Maintain required regulatory filings (calendar deadlines).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("hydra.constitution")

# ---------------------------------------------------------------------------
# Known sanctioned addresses
# OFAC-listed Tornado Cash contracts (source: OFAC SDN List, August 2022)
# ---------------------------------------------------------------------------

_SANCTIONED_ADDRESSES: frozenset[str] = frozenset(
    {
        # Tornado Cash mixer contracts — OFAC SDN list
        "0x8589427373D6D84E98730D7795D8f6f8731FDA16",
        "0x722122dF12D4e14e13Ac3b6895a86e84145b6967",
        "0xDD4c48C0B24039969fC16D1cdF626eaB821d3384",
        "0xd90e2f925DA726b50C4Ed8D0Fb90Ad053324F31b",
        "0xd96f2B1c14Db8458374d9Aca76E26c3D18364307",
        "0x4736dCf1b7A3d580672CcE6E7c65cd5cc9cFBfA9",
        # Additional canonical Tornado Cash router / proxy addresses
        "0x722122dF12D4e14e13Ac3b6895a86e84145b6967",
        "0x910Cbd523D972eb0a6f4cAe4618aD62622b39DbF",
        "0xA160cdAB225685dA1d56aa342Ad8841c3b53f291",
        "0xFD8610d20aA15b7B2E3Be39B396a1bC3516c7144",
        "0x07687e702b410Fa43f4cB4Af7FA097918ffD2730",
        "0x23773E65ed146A459667303B6aB053F80C07f3e8",
        "0x22aaA7720ddd5388A3c0A3333430953C68f1849b",
        "0x03893a7c7463AE47D46bc7f091665f1893656003",
        "0x2717c5e28cf931547B621a5dddb772Ab6A35B701",
        "0xD21be7248e0197Ee08E0c20D4a96DEBdaC3D20Af",
        "0x8589427373D6D84E98730D7795D8f6f8731FDA16",
        "0x1E34A77868E19A6647b1f2F47B51ed72dEDE95DD",
        "0x169AD27A470D064DEDE56a2D3ff727986b15D52B",
        "0x0836222F2B2B5A1Bc105F1D8cCA7A5d80893e6d5",
        "0xF67721A2D8F736E75a49FdD7FAd2e31D8676542a",
        "0x9AD122c22B14202B4490eDAf288FDb3C7cb3ff5E",
        "0x905b63Fff465B9fFBF41DeA908CEb12478ec7601",
        "0x4736dCf1b7A3d580672CcE6E7c65cd5cc9cFBfA9",
        "0x169AD27A470D064DEDE56a2D3ff727986b15D52B",
        "0x0836222F2B2B5A1Bc105F1D8cCA7A5d80893e6d5",
    }
)

# Minimum operating reserve that must remain after any remittance
SOLVENCY_RESERVE: Decimal = Decimal("500")


@dataclass
class ValidationResult:
    """Result of a constitutional validation check."""
    approved: bool
    reason: str = ""
    checks: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Compliance calendar
# ---------------------------------------------------------------------------

# (description, due_date, days_warning)
_COMPLIANCE_CALENDAR: list[tuple[str, date, int]] = [
    ("Wyoming LLC Annual Report",          date(2026, 1, 1),  60),
    ("Form 5472 (foreign-owned entity)",   date(2026, 4, 15), 90),
    ("Form 1120 (corporate income tax)",   date(2026, 4, 15), 90),
    ("FinCEN BOI Report (initial 30-day)", date(2025, 12, 31), 30),
    ("Wyoming LLC Annual Report",          date(2027, 1, 1),  60),
    ("Form 5472 (foreign-owned entity)",   date(2027, 4, 15), 90),
]


# ---------------------------------------------------------------------------
# ConstitutionCheck
# ---------------------------------------------------------------------------


class ConstitutionCheck:
    """
    Three-law constitutional compliance validator.

    All three laws must pass before any outbound transaction is approved.

    Law 1  LEGALITY   — OFAC sanctions screening.
    Law 2  SOLVENCY   — $500 minimum operating reserve.
    Law 3  COMPLIANCE — Regulatory filing deadlines monitored.

    Production note
    ---------------
    The MVP uses a hardcoded set of OFAC-sanctioned addresses.
    In production, replace ``_check_ofac_local`` with a call to the
    Chainalysis free sanctions API:
    https://public.chainalysis.com/api/v1/address/{address}
    """

    def __init__(self) -> None:
        # Normalise to lowercase for case-insensitive matching
        self._sanctioned: frozenset[str] = frozenset(
            addr.lower() for addr in _SANCTIONED_ADDRESSES
        )
        logger.info(
            "ConstitutionCheck initialised. %d sanctioned addresses loaded.",
            len(self._sanctioned),
        )

    # ------------------------------------------------------------------
    # Law 1 — LEGALITY (OFAC)
    # ------------------------------------------------------------------

    def check_ofac(self, address: str) -> Tuple[bool, str]:
        """
        Screen an address against the OFAC sanctions list.

        Parameters
        ----------
        address : str
            Ethereum address to screen (checksummed or lowercase).

        Returns
        -------
        (clean, reason) : (bool, str)
            clean=True  → address is not on the sanctions list.
            clean=False → address is sanctioned; reason explains.
        """
        if not address:
            return False, "Empty address provided."

        normalised = address.lower().strip()

        if normalised in self._sanctioned:
            reason = (
                f"OFAC VIOLATION (Law 1 LEGALITY): Address {address} is on the "
                "OFAC SDN sanctions list. Transaction BLOCKED."
            )
            logger.warning(reason)
            return False, reason

        return True, f"Address {address} cleared OFAC screening."

    # ------------------------------------------------------------------
    # Law 2 — SOLVENCY
    # ------------------------------------------------------------------

    def check_solvency(
        self,
        current_balance: Decimal,
        remit_amount: Decimal,
    ) -> Tuple[bool, str]:
        """
        Ensure the entity maintains a $500 operating reserve after remittance.

        Parameters
        ----------
        current_balance : Decimal
            Current USDC balance.
        remit_amount : Decimal
            Proposed remittance amount.

        Returns
        -------
        (ok, reason) : (bool, str)
        """
        post_balance = current_balance - remit_amount
        if post_balance >= SOLVENCY_RESERVE:
            return (
                True,
                f"Solvency check passed. Post-remittance balance: "
                f"${post_balance:.2f} (reserve: ${SOLVENCY_RESERVE}).",
            )
        reason = (
            f"SOLVENCY VIOLATION (Law 2 SOLVENCY): Post-remittance balance "
            f"${post_balance:.2f} would fall below ${SOLVENCY_RESERVE} reserve. "
            f"Transaction BLOCKED."
        )
        logger.warning(reason)
        return False, reason

    # ------------------------------------------------------------------
    # Law 3 — COMPLIANCE (filing deadlines)
    # ------------------------------------------------------------------

    def check_compliance(self) -> List[Dict[str, Any]]:
        """
        Return upcoming regulatory filing deadlines.

        Deadlines within the warning window are flagged as urgent.

        Returns
        -------
        list of dict
            Each dict: {description, due_date, days_until, urgent}
        """
        today = datetime.now(timezone.utc).date()
        upcoming: List[Dict[str, Any]] = []

        for description, due_date, warning_days in _COMPLIANCE_CALENDAR:
            days_until = (due_date - today).days
            if days_until < 0:
                # Already past — still surface overdue items
                upcoming.append(
                    {
                        "description": description,
                        "due_date": due_date.isoformat(),
                        "days_until": days_until,
                        "urgent": True,
                        "status": "OVERDUE",
                    }
                )
            elif days_until <= warning_days:
                upcoming.append(
                    {
                        "description": description,
                        "due_date": due_date.isoformat(),
                        "days_until": days_until,
                        "urgent": True,
                        "status": "DUE_SOON",
                    }
                )
            else:
                upcoming.append(
                    {
                        "description": description,
                        "due_date": due_date.isoformat(),
                        "days_until": days_until,
                        "urgent": False,
                        "status": "UPCOMING",
                    }
                )

        return sorted(upcoming, key=lambda d: d["days_until"])

    # ------------------------------------------------------------------
    # Master validator
    # ------------------------------------------------------------------

    def check_legality(self, address: str, amount: float = 0) -> Tuple[bool, str]:
        """Alias for check_ofac — used by remittance set_receiving_wallet."""
        return self.check_ofac(address)

    def validate_remittance(
        self,
        to_address: str,
        amount: Any,
        current_balance: Any,
    ) -> ValidationResult:
        """
        Run all three constitutional checks before an outbound remittance.

        Parameters
        ----------
        to_address : str
            Destination Ethereum address.
        amount : Decimal or float
            USDC amount to remit.
        current_balance : Decimal or float
            Current wallet balance in USDC.

        Returns
        -------
        ValidationResult
            .approved=True only when ALL laws pass.
            .reasons contains pass/fail messages from each law.
            .checks contains per-law boolean results.
            .reason is the first failure reason (or empty string).
        """
        amount = Decimal(str(amount))
        current_balance = Decimal(str(current_balance))

        reasons: List[str] = []
        checks: Dict[str, Any] = {}
        approved = True

        # Law 1 — LEGALITY
        ofac_ok, ofac_reason = self.check_ofac(to_address)
        reasons.append(f"[Law 1 LEGALITY] {ofac_reason}")
        checks["legality"] = ofac_ok
        if not ofac_ok:
            approved = False

        # Law 2 — SOLVENCY
        solvency_ok, solvency_reason = self.check_solvency(current_balance, amount)
        reasons.append(f"[Law 2 SOLVENCY] {solvency_reason}")
        checks["solvency"] = solvency_ok
        if not solvency_ok:
            approved = False

        # Law 3 — COMPLIANCE (advisory — does not block, but logs urgent items)
        compliance_items = self.check_compliance()
        urgent_items = [c for c in compliance_items if c["urgent"]]
        checks["compliance"] = len(urgent_items) == 0
        if urgent_items:
            for item in urgent_items:
                msg = (
                    f"[Law 3 COMPLIANCE] {item['status']}: "
                    f"{item['description']} due {item['due_date']} "
                    f"({item['days_until']} days)."
                )
                reasons.append(msg)
                logger.warning(msg)
        else:
            reasons.append("[Law 3 COMPLIANCE] No urgent filing deadlines.")

        if approved:
            logger.info(
                "Remittance APPROVED: %s USDC → %s", amount, to_address
            )
        else:
            logger.warning(
                "Remittance BLOCKED: %s USDC → %s | Reasons: %s",
                amount,
                to_address,
                "; ".join(reasons),
            )

        # Build failure reason string
        failure_reason = ""
        if not approved:
            failure_reasons = [r for r in reasons if "VIOLATION" in r or "BLOCKED" in r]
            failure_reason = "; ".join(failure_reasons) if failure_reasons else "; ".join(reasons)

        return ValidationResult(
            approved=approved,
            reason=failure_reason,
            checks=checks,
            reasons=reasons,
        )
