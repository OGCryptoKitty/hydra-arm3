"""
HYDRA Automaton Runtime
=======================
Conway Automaton-compatible persistent runtime for HYDRA.

Exports:
    HydraAutomaton   — Self-sustaining autonomous heartbeat loop
    LifecycleManager — Phase transition manager
    ConstitutionCheck — Three-law compliance validator
"""

from .automaton import HydraAutomaton, get_automaton, set_automaton
from .lifecycle import LifecycleManager
from .constitution import ConstitutionCheck, ValidationResult
from .transaction_log import TransactionLog, TxDirection, TxCategory

__all__ = [
    "HydraAutomaton",
    "get_automaton",
    "set_automaton",
    "LifecycleManager",
    "ConstitutionCheck",
    "ValidationResult",
    "TransactionLog",
    "TxDirection",
    "TxCategory",
]
