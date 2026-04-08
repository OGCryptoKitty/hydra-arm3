/**
 * HYDRA Arm 3 — k6 Load Test
 *
 * Tests free and paid endpoints under simulated bot traffic.
 * Run: k6 run k6/load_test.js
 *
 * Stages:
 *   1. Ramp up to 10 VUs over 30s
 *   2. Hold at 10 VUs for 2 minutes (steady state)
 *   3. Spike to 50 VUs for 30s (burst test)
 *   4. Ramp down over 30s
 *
 * Environment variables:
 *   HYDRA_URL  — Base URL (default: http://localhost:8402)
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// Custom metrics
const errorRate = new Rate("hydra_errors");
const paymentRequiredRate = new Rate("hydra_402_rate");
const feedLatency = new Trend("hydra_feed_latency");
const healthLatency = new Trend("hydra_health_latency");

const BASE_URL = __ENV.HYDRA_URL || "http://localhost:8402";

export const options = {
  stages: [
    { duration: "30s", target: 10 },  // Ramp up
    { duration: "2m", target: 10 },   // Steady state
    { duration: "30s", target: 50 },  // Spike
    { duration: "30s", target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<2000"],    // 95th percentile < 2s
    hydra_errors: ["rate<0.05"],          // Error rate < 5%
    hydra_health_latency: ["p(99)<500"],  // Health check < 500ms
  },
};

export default function () {
  const scenario = Math.random();

  if (scenario < 0.4) {
    // 40% — Health check (free, should always work)
    const res = http.get(`${BASE_URL}/health`);
    healthLatency.add(res.timings.duration);
    check(res, {
      "health returns 200": (r) => r.status === 200,
      "health has status ok": (r) => r.json("status") === "ok",
    });
    errorRate.add(res.status >= 500);

  } else if (scenario < 0.65) {
    // 25% — Pricing endpoint (free)
    const res = http.get(`${BASE_URL}/pricing`);
    check(res, {
      "pricing returns 200": (r) => r.status === 200,
    });
    errorRate.add(res.status >= 500);

  } else if (scenario < 0.80) {
    // 15% — Markets feed (paid — expect 402 without payment)
    const res = http.get(`${BASE_URL}/v1/markets/feed`);
    paymentRequiredRate.add(res.status === 402);
    feedLatency.add(res.timings.duration);
    check(res, {
      "feed returns 402 (payment required)": (r) => r.status === 402,
      "feed includes payment instructions": (r) =>
        r.headers["X-Payment-Required"] === "true",
    });
    errorRate.add(res.status >= 500);

  } else if (scenario < 0.90) {
    // 10% — Regulatory scan (paid — expect 402)
    const res = http.post(
      `${BASE_URL}/v1/regulatory/scan`,
      JSON.stringify({
        business_description: "Crypto exchange offering tokenized securities",
        jurisdiction: "US",
      }),
      { headers: { "Content-Type": "application/json" } }
    );
    check(res, {
      "scan returns 402": (r) => r.status === 402,
    });
    errorRate.add(res.status >= 500);

  } else {
    // 10% — Metrics (free)
    const res = http.get(`${BASE_URL}/metrics`);
    check(res, {
      "metrics returns 200": (r) => r.status === 200,
    });
    errorRate.add(res.status >= 500);
  }

  sleep(0.5 + Math.random() * 1.5); // 0.5-2s between requests
}

export function handleSummary(data) {
  const summary = {
    total_requests: data.metrics.http_reqs.values.count,
    avg_latency_ms: Math.round(data.metrics.http_req_duration.values.avg),
    p95_latency_ms: Math.round(data.metrics.http_req_duration.values["p(95)"]),
    error_rate_pct: (data.metrics.hydra_errors.values.rate * 100).toFixed(2),
    payment_402_rate_pct: (
      data.metrics.hydra_402_rate.values.rate * 100
    ).toFixed(2),
  };

  console.log("\n=== HYDRA Load Test Summary ===");
  console.log(JSON.stringify(summary, null, 2));

  return {
    stdout: JSON.stringify(summary, null, 2),
  };
}
