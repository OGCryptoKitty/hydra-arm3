"""
distribution.py — HYDRA Distribution Agent Swarm (ROI-prioritized)
==================================================================
Distribution is the binding constraint on HYDRA's treasury: the endpoints
already work, but revenue only arrives when *paying agents discover HYDRA*.
This module organizes distribution into a small set of focused, role-based
agents — coordinated by an orchestrator — and runs them in expected-ROI order.

Design philosophy (explicit, per the mandate):
  - HIGH ROI over volume. Each agent targets channels where agents that can
    actually *pay via x402* are most likely to discover and call HYDRA.
  - Thoughtful priority. Agents run in ROI order; the orchestrator does not
    spray every list — it works the channels that convert to paid calls first.
  - Honest degradation. Network/credentials may be absent; each agent reports
    whether it executed, was a no-op, or needs a credential — never pretends.

These agents wrap (and prioritize) the existing, battle-tested registration
functions in agent_discovery.py and autonomous_marketing.py rather than
duplicating them — one coordinated brain instead of scattered calls.

ROI ranking rationale (where do paying x402 agents actually look first?):
  1. x402 ecosystem registries/marketplaces — agents here are payment-native.
  2. MCP registries — MCP clients can be wired to pay; large, growing surface.
  3. Discoverability (search + LLM manifests) — how autonomous agents find APIs.
  4. Public API directories — broad reach, slower conversion.
  5. Developer content (Dev.to / GitHub) — top-of-funnel, longest lag.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger("hydra.distribution")


class DistributionAgent:
    """
    One focused distribution role. Subclasses (or instances built with an action
    callable) own a single channel category and report a structured result.
    """

    def __init__(
        self,
        name: str,
        role: str,
        priority: int,
        roi_rationale: str,
        action: Callable[[], Any],
        is_async: bool = False,
        requires: Optional[list[str]] = None,
    ) -> None:
        self.name = name
        self.role = role
        self.priority = priority           # lower = higher ROI / runs first
        self.roi_rationale = roi_rationale
        self._action = action
        self._is_async = is_async
        self.requires = requires or []
        self.last_result: dict = {}

    async def run(self) -> dict:
        """Execute the agent's action, capturing success/no-op/credential gaps."""
        started = datetime.now(timezone.utc).isoformat()
        try:
            if self._is_async:
                detail = await self._action()
            else:
                detail = await asyncio.get_event_loop().run_in_executor(None, self._action)
            self.last_result = {
                "agent": self.name,
                "role": self.role,
                "priority": self.priority,
                "executed": True,
                "ran_at": started,
                "detail": detail,
            }
        except Exception as exc:  # noqa: BLE001 — distribution is best-effort, never fatal
            logger.warning("[DIST] %s failed (non-fatal): %s", self.name, exc)
            self.last_result = {
                "agent": self.name,
                "role": self.role,
                "priority": self.priority,
                "executed": False,
                "ran_at": started,
                "error": str(exc)[:200],
                "requires": self.requires,
            }
        return self.last_result


class DistributionOrchestrator:
    """
    Coordinates the distribution agents in ROI-priority order, aggregates a
    report, and exposes status. Run autonomously by the automaton heartbeat.
    """

    def __init__(self, marketing: Optional[Any] = None) -> None:
        # Lazy imports so optional deps / import cycles never break startup.
        from .agent_discovery import (
            register_with_discovery_services,
            ping_search_engines,
            verify_deployment_health,
        )
        if marketing is None:
            from .autonomous_marketing import AutonomousMarketing
            marketing = AutonomousMarketing()
        self._marketing = marketing

        self.agents: list[DistributionAgent] = [
            DistributionAgent(
                name="x402_ecosystem",
                role="Register on x402 registries & agent marketplaces",
                priority=1,
                roi_rationale="Agents here are payment-native — highest conversion to paid calls.",
                action=register_with_discovery_services,
                is_async=True,
            ),
            DistributionAgent(
                name="discoverability",
                role="Search + LLM discoverability (sitemap pings, manifests)",
                priority=3,
                roi_rationale="How autonomous/LLM agents locate APIs; compounding, low cost.",
                action=ping_search_engines,
                is_async=True,
            ),
            DistributionAgent(
                name="self_verification",
                role="Verify discovery manifests & deployment health each cycle",
                priority=2,
                roi_rationale="A broken manifest silently kills discovery — protect the funnel first.",
                action=verify_deployment_health,
                is_async=True,
            ),
            DistributionAgent(
                name="api_directories",
                role="Submit to public API directories (APIs.guru, public-apis, etc.)",
                priority=4,
                roi_rationale="Broad reach, slower conversion; idempotent best-effort.",
                action=self._marketing.submit_to_api_directories,
                requires=["GITHUB_PAT (for PR-based submissions)"],
            ),
            DistributionAgent(
                name="openapi_directories",
                role="Submit OpenAPI spec to API spec directories",
                priority=4,
                roi_rationale="Machine-readable spec surfaces HYDRA to API-indexing agents.",
                action=self._marketing.submit_openapi_to_directories,
            ),
            DistributionAgent(
                name="developer_content",
                role="Dev.to article + GitHub discussions (top-of-funnel)",
                priority=5,
                roi_rationale="Longest lag to revenue; builds durable inbound over time.",
                action=self._run_content,
                requires=["DEVTO_API_KEY", "GITHUB_PAT"],
            ),
        ]
        self.agents.sort(key=lambda a: a.priority)
        self._last_cycle: dict = {}

    def _run_content(self) -> dict:
        """Bundle the slower content channels into one agent action (sync)."""
        out: dict = {}
        for fn_name in ("publish_dev_to_article", "post_github_discussions", "autonomous_seo_content"):
            fn = getattr(self._marketing, fn_name, None)
            if callable(fn):
                try:
                    out[fn_name] = fn()
                except Exception as exc:  # noqa: BLE001
                    out[fn_name] = {"status": "error", "error": str(exc)[:120]}
        return out

    async def run_cycle(self) -> dict:
        """Run all agents in ROI-priority order; return an aggregated report."""
        logger.info("[DIST] Running distribution cycle — %d agents (ROI-ordered).", len(self.agents))
        results = []
        for agent in self.agents:
            results.append(await agent.run())
        executed = sum(1 for r in results if r.get("executed"))
        self._last_cycle = {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "agents_total": len(self.agents),
            "agents_executed": executed,
            "results": results,
        }
        logger.info("[DIST] Cycle complete — %d/%d agents executed.", executed, len(self.agents))
        return self._last_cycle

    def get_status(self) -> dict:
        """ROI-ranked roster + last cycle summary, for /status surfacing."""
        return {
            "strategy": "high-ROI distribution (paying-agent reach over volume)",
            "agents": [
                {
                    "name": a.name,
                    "role": a.role,
                    "priority": a.priority,
                    "roi_rationale": a.roi_rationale,
                    "requires": a.requires,
                    "last_executed": a.last_result.get("executed"),
                }
                for a in self.agents
            ],
            "last_cycle": {
                "ran_at": self._last_cycle.get("ran_at"),
                "agents_executed": self._last_cycle.get("agents_executed"),
                "agents_total": self._last_cycle.get("agents_total"),
            },
        }
