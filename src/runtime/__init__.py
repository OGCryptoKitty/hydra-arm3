"""
HYDRA Automaton Runtime
=======================
Conway Automaton-compatible persistent runtime for HYDRA.

Exports:
    HydraAutomaton   — Self-sustaining autonomous heartbeat loop
    LifecycleManager — Phase transition manager
    ConstitutionCheck — Three-law compliance validator
"""

from .automaton import HydraAutomaton
from .lifecycle import LifecycleManager
from .constitution import ConstitutionCheck

__all__ = [
    "HydraAutomaton",
    "LifecycleManager",
    "ConstitutionCheck",
]
