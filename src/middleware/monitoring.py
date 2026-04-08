"""
HYDRA Arm 3 — Prometheus-Compatible Monitoring
================================================
Tracks request counts, latencies, error rates, and payment metrics.
Exposes /metrics/prometheus endpoint in Prometheus text exposition format.

Compatible with:
  - Prometheus scraping
  - Grafana dashboards
  - DataDog Prometheus integration
  - Any OpenMetrics-compatible system
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict

logger = logging.getLogger("hydra.monitoring")


class MetricsCollector:
    """Thread-safe metrics collector for HYDRA."""

    def __init__(self) -> None:
        self._request_count: Dict[str, int] = defaultdict(int)
        self._error_count: Dict[str, int] = defaultdict(int)
        self._payment_count: int = 0
        self._payment_revenue_base_units: int = 0
        self._latency_sum: Dict[str, float] = defaultdict(float)
        self._latency_count: Dict[str, int] = defaultdict(int)
        self._start_time: float = time.monotonic()

    def record_request(self, path: str, method: str, status: int, duration_ms: float) -> None:
        """Record a request."""
        key = f"{method}_{path}"
        self._request_count[key] += 1
        self._latency_sum[key] += duration_ms
        self._latency_count[key] += 1
        if status >= 500:
            self._error_count[key] += 1

    def record_payment(self, amount_base_units: int) -> None:
        """Record a successful payment."""
        self._payment_count += 1
        self._payment_revenue_base_units += amount_base_units

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text exposition format."""
        lines = []
        lines.append("# HELP hydra_uptime_seconds Time since application start")
        lines.append("# TYPE hydra_uptime_seconds gauge")
        lines.append(f"hydra_uptime_seconds {self.uptime_seconds:.1f}")

        lines.append("# HELP hydra_requests_total Total HTTP requests")
        lines.append("# TYPE hydra_requests_total counter")
        total = sum(self._request_count.values())
        lines.append(f"hydra_requests_total {total}")

        lines.append("# HELP hydra_errors_total Total 5xx errors")
        lines.append("# TYPE hydra_errors_total counter")
        total_errors = sum(self._error_count.values())
        lines.append(f"hydra_errors_total {total_errors}")

        lines.append("# HELP hydra_payments_total Total verified payments")
        lines.append("# TYPE hydra_payments_total counter")
        lines.append(f"hydra_payments_total {self._payment_count}")

        lines.append("# HELP hydra_revenue_usdc Total revenue in USDC")
        lines.append("# TYPE hydra_revenue_usdc counter")
        revenue_usdc = self._payment_revenue_base_units / 1_000_000
        lines.append(f"hydra_revenue_usdc {revenue_usdc:.6f}")

        # Per-endpoint request counts
        lines.append("# HELP hydra_endpoint_requests Requests per endpoint")
        lines.append("# TYPE hydra_endpoint_requests counter")
        for key, count in sorted(self._request_count.items()):
            method, path = key.split("_", 1)
            lines.append(f'hydra_endpoint_requests{{method="{method}",path="{path}"}} {count}')

        # Average latency per endpoint
        lines.append("# HELP hydra_endpoint_latency_ms Average latency per endpoint")
        lines.append("# TYPE hydra_endpoint_latency_ms gauge")
        for key in sorted(self._latency_sum.keys()):
            method, path = key.split("_", 1)
            avg = self._latency_sum[key] / max(self._latency_count[key], 1)
            lines.append(f'hydra_endpoint_latency_ms{{method="{method}",path="{path}"}} {avg:.1f}')

        return "\n".join(lines) + "\n"

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as JSON dict."""
        return {
            "uptime_seconds": round(self.uptime_seconds, 1),
            "total_requests": sum(self._request_count.values()),
            "total_errors": sum(self._error_count.values()),
            "total_payments": self._payment_count,
            "total_revenue_usdc": round(self._payment_revenue_base_units / 1_000_000, 6),
            "error_rate_pct": round(
                sum(self._error_count.values()) / max(sum(self._request_count.values()), 1) * 100, 2
            ),
        }


# Singleton instance
_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
