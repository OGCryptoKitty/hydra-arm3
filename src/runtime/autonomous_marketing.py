"""
autonomous_marketing.py — HYDRA Fully Autonomous Marketing Engine
=================================================================
Zero-human-involvement marketing system. Executes all discovery
and distribution channels programmatically.

Channels:
  - API directories (GitHub PRs to public-apis + APIs.guru)
  - Dev.to article publication
  - GitHub Discussions on relevant repos
  - SEO-optimized docs pages pushed to GitHub
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import subprocess

import httpx

logger = logging.getLogger("hydra.marketing")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HYDRA_API_BASE = "https://hydra-api-nlnj.onrender.com"
# GitHub API via the Perplexity proxy (required for token auth to work)
GITHUB_API_BASE = "https://git-agent-proxy.perplexity.ai/api/v3"
GITHUB_GRAPHQL_URL = "https://git-agent-proxy.perplexity.ai/api/graphql"
GITHUB_USER = "OGCryptoKitty"
HYDRA_REPO = "OGCryptoKitty/hydra-arm3"
DEV_TO_API_KEY = os.environ.get("DEV_TO_API_KEY", "")


def _get_github_token() -> str:
    """Retrieve GitHub token from gh CLI or environment."""
    # Try GH_ENTERPRISE_TOKEN first (set by api_credentials=["github"])
    token = os.environ.get("GH_ENTERPRISE_TOKEN", "")
    if token:
        return token
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return token
    # Fall back to gh CLI
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return ""


GITHUB_TOKEN = _get_github_token()

MARKETING_LOG = Path("/home/user/workspace/hydra-bootstrap/marketing_log.jsonl")


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------


def _log_action(action: str, result: str, details: Optional[Dict] = None) -> None:
    """Append a marketing action record to the JSONL log."""
    MARKETING_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "result": result,
        "details": details or {},
    }
    with MARKETING_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    logger.info("[MARKETING] %s → %s", action, result)


# ---------------------------------------------------------------------------
# AutonomousMarketing
# ---------------------------------------------------------------------------


class AutonomousMarketing:
    """
    Fully autonomous marketing engine for HYDRA.

    All methods are idempotent where possible and require zero
    human interaction. GitHub operations use the OGCryptoKitty
    token from the GITHUB_TOKEN environment variable.
    """

    def __init__(self) -> None:
        self.github_headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "HYDRA-AutonomousMarketing/1.0",
        }
        self.http_timeout = 30.0

    # ------------------------------------------------------------------
    # Method 1: submit_to_api_directories()
    # ------------------------------------------------------------------

    def submit_to_api_directories(self) -> Dict[str, Any]:
        """
        Submit HYDRA to API directories via programmatic channels.

        Channels implemented:
          1. public-apis/public-apis — GitHub PR (Finance category)
          2. APIs.guru/openapi-directory — GitHub PR with OpenAPI spec
          3. Dev.to article (handled separately in publish_dev_to_article)

        Returns dict of submission results keyed by directory name.
        """
        results: Dict[str, Any] = {}

        # 1. public-apis GitHub PR
        try:
            result = self._submit_public_apis_pr()
            results["public_apis"] = result
            _log_action("submit_public_apis_pr", result.get("status", "unknown"), result)
        except Exception as exc:  # noqa: BLE001
            logger.error("public-apis PR failed: %s", exc)
            results["public_apis"] = {"status": "error", "error": str(exc)}
            _log_action("submit_public_apis_pr", "error", {"error": str(exc)})

        # 2. APIs.guru GitHub PR
        try:
            result = self._submit_apis_guru_pr()
            results["apis_guru"] = result
            _log_action("submit_apis_guru_pr", result.get("status", "unknown"), result)
        except Exception as exc:  # noqa: BLE001
            logger.error("APIs.guru PR failed: %s", exc)
            results["apis_guru"] = {"status": "error", "error": str(exc)}
            _log_action("submit_apis_guru_pr", "error", {"error": str(exc)})

        return results

    def _submit_public_apis_pr(self) -> Dict[str, Any]:
        """
        Fork public-apis/public-apis, add HYDRA to the Finance section,
        and open a pull request.
        """
        upstream_owner = "public-apis"
        upstream_repo = "public-apis"
        fork_owner = GITHUB_USER
        fork_repo = upstream_repo

        with httpx.Client(headers=self.github_headers, timeout=self.http_timeout) as client:
            # Step 1: Fork the repo (idempotent)
            fork_resp = client.post(
                f"{GITHUB_API_BASE}/repos/{upstream_owner}/{upstream_repo}/forks",
                json={"default_branch_only": True},
            )
            if fork_resp.status_code not in (202, 200):
                # Fork may already exist
                fork_check = client.get(f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}")
                if fork_check.status_code != 200:
                    return {
                        "status": "error",
                        "error": f"Fork failed: {fork_resp.status_code} {fork_resp.text[:200]}",
                    }
            logger.info("Fork exists or created: %s/%s", fork_owner, fork_repo)

            # Allow fork to propagate
            time.sleep(5)

            # Step 2: Get current README.md SHA + content from fork
            file_resp = client.get(
                f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}/contents/README.md",
                params={"ref": "master"},
            )
            if file_resp.status_code != 200:
                return {
                    "status": "error",
                    "error": f"Could not get README.md: {file_resp.status_code}",
                }

            file_data = file_resp.json()
            current_sha = file_data["sha"]
            current_content = base64.b64decode(file_data["content"]).decode("utf-8")

            # Check if HYDRA already present
            if "HYDRA" in current_content or "hydra-api-nlnj" in current_content:
                return {"status": "already_present", "message": "HYDRA already in public-apis list"}

            # Step 3: Find Finance section and insert HYDRA entry
            hydra_entry = (
                "| [HYDRA Regulatory Intelligence](https://hydra-api-nlnj.onrender.com) "
                "| Real-time SEC, CFTC, Fed, FinCEN monitoring for prediction markets. "
                "Pays via USDC x402. "
                "| `apiKey` (x402/USDC) | Yes | Unknown |"
            )

            # Find the Finance section header and first entry after it
            finance_marker = "## Finance"
            if finance_marker not in current_content:
                # Try alternate markers
                for marker in ["### Finance", "| Finance |", "Finance\n"]:
                    if marker in current_content:
                        finance_marker = marker
                        break

            if finance_marker in current_content:
                idx = current_content.index(finance_marker)
                # Find next table row after the header
                next_pipe = current_content.index("|", idx + len(finance_marker))
                # Find the end of this line
                next_newline = current_content.index("\n", next_pipe)
                insert_pos = next_newline + 1
                new_content = (
                    current_content[:insert_pos]
                    + hydra_entry + "\n"
                    + current_content[insert_pos:]
                )
            else:
                # Append to end if section not found
                new_content = current_content + f"\n{hydra_entry}\n"

            # Step 4: Create a branch on the fork
            branch_name = "add-hydra-regulatory-api"

            # Get master SHA for branch base
            ref_resp = client.get(
                f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}/git/refs/heads/master"
            )
            if ref_resp.status_code != 200:
                return {"status": "error", "error": f"Could not get master ref: {ref_resp.status_code}"}

            master_sha = ref_resp.json()["object"]["sha"]

            # Create branch (ignore 422 if already exists)
            branch_resp = client.post(
                f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}/git/refs",
                json={"ref": f"refs/heads/{branch_name}", "sha": master_sha},
            )
            if branch_resp.status_code not in (201, 422):
                logger.warning("Branch creation: %s", branch_resp.status_code)

            # Step 5: Update file on branch
            new_content_b64 = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
            update_resp = client.put(
                f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}/contents/README.md",
                json={
                    "message": "Add HYDRA Regulatory Intelligence API to Finance category",
                    "content": new_content_b64,
                    "sha": current_sha,
                    "branch": branch_name,
                },
            )
            if update_resp.status_code not in (200, 201):
                return {
                    "status": "error",
                    "error": f"File update failed: {update_resp.status_code} {update_resp.text[:300]}",
                }

            # Step 6: Open PR
            pr_resp = client.post(
                f"{GITHUB_API_BASE}/repos/{upstream_owner}/{upstream_repo}/pulls",
                json={
                    "title": "Add HYDRA Regulatory Intelligence API (Finance)",
                    "body": (
                        "Adding **HYDRA Regulatory Intelligence** to the Finance category.\n\n"
                        "HYDRA provides real-time regulatory monitoring from SEC, CFTC, Fed, "
                        "and FinCEN, aggregated for prediction market traders and compliance bots. "
                        "Free discovery endpoint returns live Polymarket + Kalshi regulatory markets. "
                        "Paid signal endpoints accept USDC via the x402 HTTP payment protocol.\n\n"
                        "- Live API: https://hydra-api-nlnj.onrender.com\n"
                        "- Docs: https://hydra-api-nlnj.onrender.com/docs\n"
                        "- OpenAPI: https://hydra-api-nlnj.onrender.com/openapi.json\n"
                    ),
                    "head": f"{fork_owner}:{branch_name}",
                    "base": "master",
                },
            )

            if pr_resp.status_code == 201:
                pr_url = pr_resp.json()["html_url"]
                return {"status": "pr_created", "url": pr_url}
            elif pr_resp.status_code == 422:
                # PR already exists
                pr_data = pr_resp.json()
                return {"status": "pr_exists", "message": str(pr_data)}
            else:
                return {
                    "status": "error",
                    "error": f"PR creation failed: {pr_resp.status_code} {pr_resp.text[:300]}",
                }

    def _submit_apis_guru_pr(self) -> Dict[str, Any]:
        """
        Fork APIs-guru/openapi-directory, add HYDRA's OpenAPI spec,
        and open a pull request.
        """
        upstream_owner = "APIs-guru"
        upstream_repo = "openapi-directory"
        fork_owner = GITHUB_USER
        fork_repo = upstream_repo

        with httpx.Client(headers=self.github_headers, timeout=self.http_timeout) as client:
            # Fetch live OpenAPI spec from HYDRA
            try:
                spec_resp = httpx.get(f"{HYDRA_API_BASE}/openapi.json", timeout=30.0)
                openapi_spec = spec_resp.json()
            except Exception as exc:  # noqa: BLE001
                return {"status": "error", "error": f"Could not fetch OpenAPI spec: {exc}"}

            # Step 1: Fork
            fork_resp = client.post(
                f"{GITHUB_API_BASE}/repos/{upstream_owner}/{upstream_repo}/forks",
                json={"default_branch_only": False},
            )
            if fork_resp.status_code not in (202, 200):
                fork_check = client.get(f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}")
                if fork_check.status_code != 200:
                    return {
                        "status": "error",
                        "error": f"Fork failed: {fork_resp.status_code}",
                    }
            time.sleep(5)

            # Step 2: Get default branch
            repo_info = client.get(f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}")
            if repo_info.status_code != 200:
                return {"status": "error", "error": "Could not get fork repo info"}
            default_branch = repo_info.json().get("default_branch", "main")

            # Step 3: Get default branch SHA
            ref_resp = client.get(
                f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}/git/refs/heads/{default_branch}"
            )
            if ref_resp.status_code != 200:
                return {"status": "error", "error": f"Could not get ref: {ref_resp.status_code}"}
            base_sha = ref_resp.json()["object"]["sha"]

            # Step 4: Create branch
            branch_name = "add-hydra-arm3-api"
            branch_resp = client.post(
                f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}/git/refs",
                json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
            )
            if branch_resp.status_code not in (201, 422):
                logger.warning("Branch create status: %s", branch_resp.status_code)

            # Step 5: Add OpenAPI spec file
            # APIs.guru structure: APIs/{provider}/{version}/openapi.yaml
            # We'll add as hydra-api-nlnj.onrender.com/v1/openapi.yaml
            spec_path = "APIs/onrender.com/hydra-arm3/v1.0.0/openapi.json"
            spec_content = json.dumps(openapi_spec, indent=2)
            spec_b64 = base64.b64encode(spec_content.encode("utf-8")).decode("utf-8")

            # Check if file already exists
            existing = client.get(
                f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}/contents/{spec_path}",
                params={"ref": branch_name},
            )

            file_payload: Dict[str, Any] = {
                "message": "Add HYDRA Arm 3 Regulatory Intelligence API spec",
                "content": spec_b64,
                "branch": branch_name,
            }
            if existing.status_code == 200:
                file_payload["sha"] = existing.json()["sha"]

            create_resp = client.put(
                f"{GITHUB_API_BASE}/repos/{fork_owner}/{fork_repo}/contents/{spec_path}",
                json=file_payload,
            )
            if create_resp.status_code not in (200, 201):
                return {
                    "status": "error",
                    "error": f"File create failed: {create_resp.status_code} {create_resp.text[:300]}",
                }

            # Step 6: Open PR
            pr_resp = client.post(
                f"{GITHUB_API_BASE}/repos/{upstream_owner}/{upstream_repo}/pulls",
                json={
                    "title": "Add HYDRA Arm 3 — Regulatory Intelligence API (x402/USDC)",
                    "body": (
                        "## New API: HYDRA Arm 3 — Regulatory Intelligence\n\n"
                        "HYDRA is a production API that aggregates regulatory intelligence "
                        "from SEC, CFTC, Fed, FinCEN, and OCC for prediction market traders "
                        "and compliance automation.\n\n"
                        "**Key details:**\n"
                        "- Base URL: `https://hydra-api-nlnj.onrender.com`\n"
                        "- Payment: x402 (USDC on Base, chain ID 8453)\n"
                        "- Free endpoints: `/v1/markets`, `/health`, `/pricing`\n"
                        "- OpenAPI spec: https://hydra-api-nlnj.onrender.com/openapi.json\n"
                        "- Category: FinTech / Regulatory Compliance / Prediction Markets\n\n"
                        "The spec is valid OpenAPI 3.1.0 generated by FastAPI.\n"
                    ),
                    "head": f"{fork_owner}:{branch_name}",
                    "base": default_branch,
                },
            )

            if pr_resp.status_code == 201:
                return {"status": "pr_created", "url": pr_resp.json()["html_url"]}
            elif pr_resp.status_code == 422:
                return {"status": "pr_exists", "message": "PR already open"}
            else:
                return {
                    "status": "error",
                    "error": f"PR failed: {pr_resp.status_code} {pr_resp.text[:300]}",
                }

    # ------------------------------------------------------------------
    # Method 2: publish_dev_to_article()
    # ------------------------------------------------------------------

    def publish_dev_to_article(self) -> Dict[str, Any]:
        """
        Publish a technical article to Dev.to via their REST API.
        Requires DEV_TO_API_KEY environment variable.

        Dev.to has 1M+ developers and accepts programmatic posting.
        API endpoint: POST https://dev.to/api/articles
        """
        if not DEV_TO_API_KEY:
            logger.warning("DEV_TO_API_KEY not set — skipping Dev.to publication")
            _log_action("publish_dev_to_article", "skipped", {"reason": "DEV_TO_API_KEY not set"})
            return {"status": "skipped", "reason": "DEV_TO_API_KEY not set"}

        article_body = """## The Problem

Prediction markets like Polymarket and Kalshi have hundreds of regulatory markets — Fed rate decisions, SEC enforcement actions, CFTC rulings, crypto legislation. But building a bot that trades these markets systematically requires:

1. Polling two separate APIs with different data formats
2. Normalizing market structures (Polymarket uses condition IDs, Kalshi uses tickers)
3. Classifying which markets are actually about regulatory events vs. sports/entertainment
4. Tracking upcoming resolution dates and relevant agency actions

I got frustrated enough to build a unified data layer. Here's how HYDRA works.

## The Architecture

HYDRA is a FastAPI application that:
- Polls the Polymarket Gamma API and Kalshi REST API every few minutes
- Filters for regulatory/macro markets using keyword and category matching
- Normalizes both into a common schema
- Serves them via a single endpoint

```bash
curl https://hydra-api-nlnj.onrender.com/v1/markets
```

Free to call. No API key. Returns a JSON array of active regulatory prediction markets with prices, 24h volume, and resolution timestamps.

## The Payment Layer

For signal processing — probability scoring, Fed speech analysis, oracle resolution data — I used x402, the HTTP 402 payment protocol.

Here's how it works: when a client calls a paid endpoint without payment, the server returns HTTP 402 with a machine-readable payment offer:

```json
{
  "amount": "2000000",
  "token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  "network": "base",
  "payTo": "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141"
}
```

The client sends the exact amount in USDC on Base, then retries with the transaction hash in the X-PAYMENT header. The server verifies on-chain and serves the response.

No API keys. No subscriptions. No accounts. An AI agent can discover the API, read the payment requirements, and autonomously pay for data — all in one HTTP exchange.

## What It Covers

- **Regulatory scan** — maps a business description to applicable regulations ($1)
- **Regulatory changes** — recent SEC, CFTC, FinCEN filings ($0.50)
- **Trading signals** — all active regulatory prediction markets, directional signal + confidence ($0.25)
- **Deep signal** — single market analysis ($0.10)
- **Fed signals** — rate probability model, FOMC speech analysis ($5)
- **Real-time FOMC classification** — HOLD/CUT/HIKE within 30 seconds of release ($25)
- **Oracle resolution** — evidence chain for UMA Optimistic Oracle bond assertions ($1)
- **Chainlink adapter** — regulatory data formatted for Chainlink Any API ($0.50)
- **Full alpha report** — complete trade recommendation for a specific position ($2)

## The x402 Ecosystem

x402 is an open standard for machine-to-machine payments. There's a growing ecosystem of services accepting it. HYDRA's discovery manifest is at:

```
https://hydra-api-nlnj.onrender.com/.well-known/x402.json
```

Any x402-compatible agent can discover HYDRA, understand its pricing, and pay autonomously — no human in the loop. This is the right payment primitive for AI agent APIs: no subscription management, no API key rotation, no billing portals. Just HTTP and USDC.

## The Prediction Market Angle

The most interesting use case is automated prediction market trading. Consider the workflow:

1. Bot calls `/v1/markets` (free) to get all active regulatory prediction markets
2. Bot finds KXFED-25JUN18 (Fed rate decision, June 2025) trading at 0.72 YES
3. Bot calls `/v1/markets/signal/KXFED-25JUN18` (pays $0.10 USDC) to get HYDRA's analysis
4. HYDRA returns: `bullish_yes`, confidence 85, key factors: CME FedWatch 91%, recent Powell speeches hawkish-neutral
5. Bot sizes position based on edge vs current market price

The whole pipeline — discovery, analysis, decision — happens in three HTTP calls with no human involvement.

## Code

The full source is at [github.com/OGCryptoKitty/hydra-arm3](https://github.com/OGCryptoKitty/hydra-arm3). The x402 middleware is the interesting part — ~200 lines in `src/x402/middleware.py` that intercepts requests, checks payment status, and verifies on-chain transactions via web3.py.

The prediction market normalization logic (`src/services/prediction_markets.py`) is also worth reading if you're building anything in this space — the Polymarket and Kalshi APIs have very different schemas.

Questions welcome in the comments."""

        payload = {
            "article": {
                "title": "How I Built a Pay-Per-Call Regulatory Intelligence API for Prediction Markets (x402/USDC)",
                "body_markdown": article_body,
                "published": True,
                "tags": ["webdev", "opensource", "python", "defi"],
                "canonical_url": f"{HYDRA_API_BASE}/docs",
                "description": (
                    "Building a unified regulatory intelligence API for prediction market bots "
                    "using FastAPI and the x402 USDC payment protocol. Free market discovery, "
                    "paid signal endpoints."
                ),
            }
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    "https://dev.to/api/articles",
                    json=payload,
                    headers={
                        "api-key": DEV_TO_API_KEY,
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    result = {
                        "status": "published",
                        "url": data.get("url"),
                        "id": data.get("id"),
                    }
                    _log_action("publish_dev_to_article", "published", result)
                    return result
                else:
                    result = {
                        "status": "error",
                        "code": resp.status_code,
                        "error": resp.text[:500],
                    }
                    _log_action("publish_dev_to_article", "error", result)
                    return result
        except Exception as exc:  # noqa: BLE001
            result = {"status": "error", "error": str(exc)}
            _log_action("publish_dev_to_article", "error", result)
            return result

    # ------------------------------------------------------------------
    # Method 3: submit_openapi_to_directories()
    # ------------------------------------------------------------------

    def submit_openapi_to_directories(self) -> Dict[str, Any]:
        """
        Fetch HYDRA's live OpenAPI spec and distribute it.

        Actions:
          1. Save spec to docs/openapi.json in the HYDRA repo
          2. Submit to APIs.guru via PR (calls _submit_apis_guru_pr)
        """
        results: Dict[str, Any] = {}

        # Fetch live spec
        try:
            resp = httpx.get(f"{HYDRA_API_BASE}/openapi.json", timeout=30.0)
            spec = resp.json()
            spec_str = json.dumps(spec, indent=2)

            # Save locally
            docs_dir = Path("/home/user/workspace/hydra-arm3/docs")
            docs_dir.mkdir(exist_ok=True)
            spec_path = docs_dir / "openapi.json"
            spec_path.write_text(spec_str, encoding="utf-8")
            results["local_save"] = {"status": "saved", "path": str(spec_path)}
            logger.info("OpenAPI spec saved to %s", spec_path)
        except Exception as exc:  # noqa: BLE001
            results["local_save"] = {"status": "error", "error": str(exc)}
            return results

        # Push to GitHub repo docs/
        try:
            push_result = self._push_file_to_repo(
                path="docs/openapi.json",
                content=spec_str,
                message="Update OpenAPI spec from live API",
            )
            results["github_push"] = push_result
            _log_action("push_openapi_to_github", push_result.get("status", "unknown"), push_result)
        except Exception as exc:  # noqa: BLE001
            results["github_push"] = {"status": "error", "error": str(exc)}

        # APIs.guru is handled by submit_to_api_directories
        results["apis_guru"] = {"status": "see_submit_to_api_directories"}

        return results

    # ------------------------------------------------------------------
    # Method 4: post_github_discussions()
    # ------------------------------------------------------------------

    def post_github_discussions(self) -> Dict[str, Any]:
        """
        Post HYDRA discovery posts to GitHub Discussions on repos
        where developers would find it useful.

        Uses GitHub GraphQL API to create discussions.
        Only posts to repos with Discussions enabled.
        """
        targets = [
            {
                "owner": "UMAprotocol",
                "repo": "protocol",
                "category_id": "MDE4OkRpc2N1c3Npb25DYXRlZ29yeTMyNzA0OTMz",  # Show and tell
                "repo_node_id": "MDEwOlJlcG9zaXRvcnkxNDIyMDMwMjc=",
            },
            {
                "owner": "APIs-guru",
                "repo": "openapi-directory",
                "category_id": "MDE4OkRpc2N1c3Npb25DYXRlZ29yeTMzMDM5OTky",  # Show and tell
                "repo_node_id": "MDEwOlJlcG9zaXRvcnkzMTE3NzU5Mw==",
            },
        ]

        discussion_title = "HYDRA — Free regulatory intelligence API for prediction market bots"
        discussion_body = """Built a regulatory intelligence API that might be useful for builders here.

Free endpoint aggregates live regulatory prediction markets from Polymarket and Kalshi:

```bash
curl https://hydra-api-nlnj.onrender.com/v1/markets
```

No API key, no signup. Returns SEC/CFTC/Fed markets normalized across both platforms — market titles, current prices, 24h volume, resolution dates.

**Paid signal layer (x402/USDC on Base):**
- Fed decision intelligence — rate probability, FOMC speech analysis ($5)
- Per-market regulatory signals — directional signal + confidence ($0.10–$0.25)
- Oracle resolution evidence chains — UMA OOv2 formatted assertion data ($1)
- Chainlink external adapter — regulatory data on-chain ($0.50)
- Full alpha report for specific positions ($2)

**Why x402?** No API keys, no subscriptions, no billing portal. An AI agent can discover HYDRA, read the payment manifest, and autonomously pay for and consume data — the full pipeline in 3 HTTP calls.

Docs: https://hydra-api-nlnj.onrender.com/docs
Discovery manifest: https://hydra-api-nlnj.onrender.com/.well-known/x402.json
Source: https://github.com/OGCryptoKitty/hydra-arm3

Happy to discuss integration patterns or the regulatory signal methodology."""

        results: Dict[str, Any] = {}

        for target in targets:
            repo_key = f"{target['owner']}/{target['repo']}"
            try:
                result = self._create_github_discussion(
                    repo_node_id=target["repo_node_id"],
                    category_id=target["category_id"],
                    title=discussion_title,
                    body=discussion_body,
                )
                results[repo_key] = result
                _log_action(f"post_discussion_{repo_key}", result.get("status", "unknown"), result)
            except Exception as exc:  # noqa: BLE001
                logger.error("Discussion post failed for %s: %s", repo_key, exc)
                results[repo_key] = {"status": "error", "error": str(exc)}
                _log_action(f"post_discussion_{repo_key}", "error", {"error": str(exc)})

        return results

    def _create_github_discussion(
        self,
        repo_node_id: str,
        category_id: str,
        title: str,
        body: str,
    ) -> Dict[str, Any]:
        """Create a GitHub Discussion via GraphQL API."""
        mutation = """
        mutation CreateDiscussion($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
          createDiscussion(input: {
            repositoryId: $repoId,
            categoryId: $categoryId,
            title: $title,
            body: $body
          }) {
            discussion {
              id
              url
              number
            }
          }
        }
        """
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                GITHUB_GRAPHQL_URL,
                json={
                    "query": mutation,
                    "variables": {
                        "repoId": repo_node_id,
                        "categoryId": category_id,
                        "title": title,
                        "body": body,
                    },
                },
                headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Content-Type": "application/json",
                },
            )
            data = resp.json()
            if "errors" in data:
                return {"status": "error", "errors": data["errors"]}
            discussion_data = data.get("data", {}).get("createDiscussion", {}).get("discussion", {})
            return {
                "status": "created",
                "url": discussion_data.get("url"),
                "number": discussion_data.get("number"),
            }

    # ------------------------------------------------------------------
    # Method 5: autonomous_seo_content()
    # ------------------------------------------------------------------

    def autonomous_seo_content(self) -> Dict[str, Any]:
        """
        Generate and push SEO-optimized markdown documentation pages
        to the HYDRA GitHub repo. These pages target high-intent
        developer search queries and will be indexed by Google via
        the GitHub Pages / raw content crawl.
        """
        docs_dir = Path("/home/user/workspace/hydra-arm3/docs")
        docs_dir.mkdir(exist_ok=True)

        pages = self._generate_seo_pages()
        results: Dict[str, Any] = {}

        for filename, content in pages.items():
            filepath = docs_dir / filename
            filepath.write_text(content, encoding="utf-8")

            try:
                push_result = self._push_file_to_repo(
                    path=f"docs/{filename}",
                    content=content,
                    message=f"Add SEO docs: {filename}",
                )
                results[filename] = push_result
                _log_action(f"push_seo_doc_{filename}", push_result.get("status", "unknown"), push_result)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to push %s: %s", filename, exc)
                results[filename] = {"status": "error", "error": str(exc)}

        return results

    def _generate_seo_pages(self) -> Dict[str, str]:
        """Generate all SEO documentation pages."""
        return {
            "index.md": self._page_index(),
            "polymarket-integration.md": self._page_polymarket(),
            "kalshi-integration.md": self._page_kalshi(),
            "fomc-fed-signals.md": self._page_fomc(),
            "uma-oracle-resolution.md": self._page_uma(),
            "x402-payment-guide.md": self._page_x402(),
        }

    def _page_index(self) -> str:
        return """# HYDRA Regulatory Intelligence API

**HYDRA** is a real-time regulatory intelligence API for prediction market traders, compliance automation bots, and DeFi oracle systems.

## Quick Start

```bash
# Free: all active regulatory prediction markets
curl https://hydra-api-nlnj.onrender.com/v1/markets

# Free: API pricing and payment addresses
curl https://hydra-api-nlnj.onrender.com/pricing

# Docs and interactive explorer
open https://hydra-api-nlnj.onrender.com/docs
```

No API key required for free endpoints. Paid endpoints accept USDC on Base via the x402 payment protocol.

## What HYDRA Covers

| Category | Endpoints | Price |
|----------|-----------|-------|
| Prediction Markets | Live regulatory markets from Polymarket + Kalshi | Free |
| Trading Signals | Directional signals with confidence scores | $0.10–$0.25 |
| Fed Intelligence | FOMC analysis, dot plot tracking | $5–$50 |
| Regulatory Scan | Business → applicable regulations | $1.00 |
| Oracle Data | UMA OOv2 + Chainlink adapter | $0.50–$1.00 |
| Alpha Reports | Full trade recommendation | $2.00 |

## API Base URL

```
https://hydra-api-nlnj.onrender.com
```

## Documentation

- [Polymarket Integration](polymarket-integration.md) — trading bot setup, signal consumption
- [Kalshi Integration](kalshi-integration.md) — ticker mapping, KXFED series
- [FOMC Fed Signals](fomc-fed-signals.md) — pre-meeting analysis, real-time classification
- [UMA Oracle Resolution](uma-oracle-resolution.md) — Optimistic Oracle assertion data
- [x402 Payment Guide](x402-payment-guide.md) — USDC payment flow, agent integration

## OpenAPI Spec

Machine-readable spec at: `https://hydra-api-nlnj.onrender.com/openapi.json`

## Source

[github.com/OGCryptoKitty/hydra-arm3](https://github.com/OGCryptoKitty/hydra-arm3)
"""

    def _page_polymarket(self) -> str:
        return """# Polymarket Integration Guide

HYDRA provides a free regulatory market discovery layer over the Polymarket API, plus paid trading signals for prediction market bots.

## Free Market Discovery

Get all active Polymarket regulatory markets in a normalized format:

```bash
curl "https://hydra-api-nlnj.onrender.com/v1/markets?platform=polymarket"
```

Response includes:
- `condition_id` — Polymarket's unique market identifier (0x...)
- `title` — market question
- `yes_price` — current YES token price (0–1)
- `volume_24h` — 24-hour USDC volume
- `end_date` — resolution timestamp
- `category` — regulatory domain (fed/sec/cftc/crypto/regulation)

## Trading Signals for Polymarket Bots

For each Polymarket market, HYDRA provides directional regulatory intelligence:

```python
import httpx

# Step 1: Discover markets (free)
markets = httpx.get("https://hydra-api-nlnj.onrender.com/v1/markets").json()
regulatory_markets = [m for m in markets if m["platform"] == "polymarket"]

# Step 2: Get signal for a specific market ($0.10 USDC via x402)
market_id = regulatory_markets[0]["condition_id"]

# First call returns 402 with payment instructions
resp = httpx.post(f"https://hydra-api-nlnj.onrender.com/v1/markets/signal/{market_id}")
# resp.status_code == 402
# resp.json()["payment"]["amount"] == "100000"  (0.10 USDC in base units)
# resp.json()["payment"]["payTo"] == "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141"

# After paying 0.10 USDC on Base, retry with tx hash:
signal = httpx.post(
    f"https://hydra-api-nlnj.onrender.com/v1/markets/signal/{market_id}",
    headers={"X-PAYMENT": "0x<your_tx_hash>"}
).json()

print(signal["direction"])    # "bullish_yes", "bullish_no", or "neutral"
print(signal["confidence"])   # 0-100
print(signal["analysis"])     # regulatory reasoning
```

## Full Alpha Report

For sizing large positions ($1,000+ USDC), use the alpha endpoint ($2.00):

```python
alpha = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/markets/alpha",
    json={"market_id": condition_id, "position": "yes", "size_usdc": 1000},
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

print(alpha["edge"])           # HYDRA probability vs market price
print(alpha["recommended"])    # True/False
print(alpha["optimal_entry"])  # Price at which the trade has positive EV
```

## x402 Discovery Manifest

HYDRA's full pricing manifest for automated agents:
```
https://hydra-api-nlnj.onrender.com/.well-known/x402.json
```

## Related

- [Kalshi Integration](kalshi-integration.md)
- [x402 Payment Guide](x402-payment-guide.md)
- [Live API Docs](https://hydra-api-nlnj.onrender.com/docs)
"""

    def _page_kalshi(self) -> str:
        return """# Kalshi Integration Guide

HYDRA normalizes Kalshi's regulatory prediction markets (especially the KXFED rate series) into a consistent schema alongside Polymarket data.

## Kalshi Market Discovery

```bash
curl "https://hydra-api-nlnj.onrender.com/v1/markets"
```

Kalshi markets in the response have:
- `platform`: `"kalshi"`
- `ticker`: Kalshi's ticker format (e.g., `KXFED-25JUN18`)
- `yes_price`: current YES price (0–1)
- `category`: `"fed"`, `"sec"`, `"crypto"`, etc.

## KXFED Series — Fed Rate Markets

Kalshi's KXFED series tracks Fed rate decisions. HYDRA tracks all active KXFED markets and provides:

1. **Signal endpoint** — directional analysis using CME FedWatch data, Fed governor speeches, economic indicators
2. **Resolution assessment** — HOLD/CUT/HIKE verdict with confidence and evidence chain

```bash
# Get signal for specific KXFED market ($0.10 USDC)
curl -X POST https://hydra-api-nlnj.onrender.com/v1/markets/signal/KXFED-25JUN18 \\
  -H "X-PAYMENT: 0x<tx_hash>"
```

## Oracle Resolution for Kalshi

After FOMC announcements, use the resolution endpoint to verify resolution direction:

```python
import httpx

resolution = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/fed/resolution",
    json={
        "market_question": "Will the Fed hold rates at the June 2025 FOMC meeting?",
        "include_kalshi_format": True
    },
    headers={"X-PAYMENT": "0x<tx_hash>"}  # $50 USDC
).json()

# Kalshi-formatted resolution
kalshi_data = resolution["kalshi_format"]
print(kalshi_data["ticker"])       # KXFED-25JUN18
print(kalshi_data["resolution"])   # "yes" or "no"
print(kalshi_data["evidence"])     # Fed statement URLs and key quotes
```

## Regulatory Changes Feed

Track regulatory events that affect Kalshi markets:

```python
events = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/markets/events",
    json={"since_hours": 24, "agencies": ["Fed", "SEC", "CFTC"]},
    headers={"X-PAYMENT": "0x<tx_hash>"}  # $0.15 USDC
).json()

for event in events["events"]:
    print(event["title"])
    print(event["matched_markets"])  # which Kalshi/Polymarket markets are affected
    print(event["urgency"])          # "high", "medium", "low"
```

## High-Frequency Bot Polling

For bots that need low-latency event detection, use the micro feed ($0.05 USDC):

```bash
# Returns last 10 regulatory events matched to active markets
curl -X GET https://hydra-api-nlnj.onrender.com/v1/markets/feed \\
  -H "X-PAYMENT: 0x<tx_hash>"
```

## Related

- [FOMC Fed Signals](fomc-fed-signals.md) — pre-meeting analysis for KXFED markets
- [Polymarket Integration](polymarket-integration.md)
- [Live API Docs](https://hydra-api-nlnj.onrender.com/docs)
"""

    def _page_fomc(self) -> str:
        return """# FOMC Fed Signal API

HYDRA provides three tiers of Federal Reserve intelligence for prediction market traders.

## The Fed Decision Package

| Endpoint | Price | Use Case |
|----------|-------|----------|
| `POST /v1/fed/signal` | $5.00 | Pre-meeting analysis (days before FOMC) |
| `POST /v1/fed/decision` | $25.00 | Real-time classification on FOMC day |
| `POST /v1/fed/resolution` | $50.00 | Full resolution package for oracle asserters |

## Pre-FOMC Signal ($5.00)

Call this 1–7 days before an FOMC meeting to get HYDRA's rate probability model:

```python
import httpx

signal = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/fed/signal",
    json={"include_speech_analysis": True, "include_indicators": True},
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

print(signal["rate_probability"])   # {"hold": 0.87, "cut": 0.11, "hike": 0.02}
print(signal["cme_fedwatch"])       # CME market-implied probabilities
print(signal["speech_tone"])        # "hawkish", "dovish", "neutral"
print(signal["dot_plot_delta"])     # median dot shift vs prior meeting
print(signal["key_indicators"])     # CPI, PCE, unemployment, GDP
```

## Real-Time FOMC Classification ($25.00)

On FOMC announcement days, this endpoint attempts to classify the decision within 30 seconds of the Federal Reserve statement release:

```python
decision = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/fed/decision",
    json={"include_market_impact": True},
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

print(decision["decision"])         # "HOLD", "CUT_25", "CUT_50", "HIKE_25"
print(decision["vote_breakdown"])   # e.g., "11-1 HOLD"
print(decision["statement_key_phrases"])
print(decision["market_impact"])    # expected impact on Kalshi/Polymarket markets
```

## Oracle Resolution Package ($50.00)

For UMA bond asserters and automated oracle systems resolving FOMC prediction markets:

```python
resolution = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/fed/resolution",
    json={
        "market_question": "Will the Federal Reserve hold interest rates at the June 2025 FOMC meeting?",
        "include_uma_data": True,
        "include_kalshi_format": True,
        "include_polymarket_format": True
    },
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

# Use in UMA Optimistic Oracle assertion
uma_data = resolution["uma_data"]
# uma_data["ancillary_data"] — encoded claim for OOv2
# uma_data["proposed_price"] — 1e18 (YES) or 0 (NO)
# uma_data["evidence_chain"] — list of source URLs with timestamps
```

## FOMC Calendar

HYDRA tracks the Federal Reserve's published meeting calendar. The next scheduled FOMC date is always available via the pre-signal endpoint without payment:

```bash
curl https://hydra-api-nlnj.onrender.com/pricing
# Returns next FOMC date in the pricing context
```

## Related

- [Kalshi KXFED Markets](kalshi-integration.md)
- [UMA Oracle Resolution](uma-oracle-resolution.md)
- [Live API Docs](https://hydra-api-nlnj.onrender.com/docs)
"""

    def _page_uma(self) -> str:
        return """# UMA Optimistic Oracle Resolution Data

HYDRA provides formatted assertion data for the UMA Optimistic Oracle (OOv2), the resolution layer for Polymarket prediction markets.

## The Problem

Asserting a bond to resolve a Polymarket market requires:
1. A factual claim about a real-world event
2. An evidence chain (URLs + timestamps) to defend the assertion during the dispute window
3. Correct formatting for UMA's ancillary data encoding

A failed assertion risks losing the $750+ USDC.e bond. HYDRA provides a $1.00 pre-assertion check.

## UMA Oracle Endpoint

```python
import httpx

# Check resolution before posting bond ($1.00 USDC)
oracle_data = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/oracle/uma",
    json={
        "assertion_claim": "The Federal Reserve held interest rates at the May 2025 FOMC meeting.",
        "bond_currency": "USDC.e",
        "market_question": "Will the Fed hold rates at the May 2025 FOMC meeting?"
    },
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

print(oracle_data["resolved"])           # True/False
print(oracle_data["resolution_value"])   # "Yes" or "No"
print(oracle_data["confidence"])         # 0-100
print(oracle_data["ancillary_data"])     # hex-encoded for OOv2 submission
print(oracle_data["proposed_price"])     # 1e18 (YES) or 0 (NO)
print(oracle_data["evidence_chain"])     # list of {url, title, timestamp, excerpt}
print(oracle_data["bond_recommendation"])  # "proceed" or "do_not_assert"
```

## FOMC-Specific Resolution

For Fed rate decision markets, use the higher-confidence `/v1/fed/resolution` endpoint ($50.00):

```python
fomc_resolution = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/fed/resolution",
    json={
        "market_question": "Will the Fed cut rates by 25bp at the June 2025 FOMC meeting?",
        "include_uma_data": True
    },
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

uma = fomc_resolution["uma_data"]
# uma["ancillary_data"] — ready to submit to UMA OOv2
# uma["evidence_chain"] — Fed statement, press conference transcript, vote record
```

## Chainlink External Adapter

HYDRA also serves as a Chainlink external adapter for regulatory data delivery on-chain:

```python
chainlink_data = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/oracle/chainlink",
    json={
        "data_request": "SEC enforcement action count 2025",
        "job_run_id": "1"
    },
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

# chainlink_data["data"]["result"] — numeric value for on-chain delivery
# chainlink_data["statusCode"] — 200 on success
```

## Market Resolution Assessment

For any prediction market (not just FOMC), use the general resolution endpoint ($1.00):

```python
assessment = httpx.post(
    "https://hydra-api-nlnj.onrender.com/v1/markets/resolution",
    json={"market_id": "0x<condition_id_or_kalshi_ticker>"},
    headers={"X-PAYMENT": "0x<tx_hash>"}
).json()

print(assessment["resolved"])
print(assessment["confidence"])
print(assessment["evidence_summary"])
```

## Related

- [FOMC Fed Signals](fomc-fed-signals.md)
- [Polymarket Integration](polymarket-integration.md)
- [x402 Payment Guide](x402-payment-guide.md)
"""

    def _page_x402(self) -> str:
        return """# x402 Payment Guide

HYDRA accepts payment in USDC on Base via the x402 HTTP 402 payment protocol. This guide explains the payment flow and how to integrate it into bots or agents.

## What is x402?

x402 is an open standard for machine-to-machine HTTP payments. It extends HTTP 402 ("Payment Required") into a functional payment protocol:

1. Client sends a request without payment
2. Server returns `402 Payment Required` with a machine-readable payment offer
3. Client sends the specified amount of USDC to the specified address on Base
4. Client retries the request with the transaction hash in `X-PAYMENT` header
5. Server verifies on-chain and returns the response

No API keys, no subscriptions, no billing portals. Works for AI agents, bots, and automated systems.

## Payment Details

| Field | Value |
|-------|-------|
| Network | Base (chain ID 8453) |
| Token | USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`) |
| Receiving wallet | `0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141` |

## Example Payment Flow

```python
import httpx
from web3 import Web3

HYDRA_BASE = "https://hydra-api-nlnj.onrender.com"
BASE_RPC = "https://mainnet.base.org"
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
HYDRA_WALLET = "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141"

def call_hydra_with_payment(endpoint: str, payload: dict, private_key: str):
    # Step 1: Initial call to get payment requirements
    resp = httpx.post(f"{HYDRA_BASE}{endpoint}", json=payload)
    assert resp.status_code == 402

    payment = resp.json()["payment"]
    amount_usdc = int(payment["amount"])  # in base units (6 decimals)

    # Step 2: Send USDC on Base
    w3 = Web3(Web3.HTTPProvider(BASE_RPC))
    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDRESS),
        abi=[{
            "name": "transfer",
            "type": "function",
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "amount", "type": "uint256"}
            ],
            "outputs": [{"name": "", "type": "bool"}]
        }]
    )
    account = w3.eth.account.from_key(private_key)
    tx = usdc.functions.transfer(
        Web3.to_checksum_address(HYDRA_WALLET),
        amount_usdc
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 100000,
        "maxFeePerGas": w3.eth.gas_price,
        "maxPriorityFeePerGas": w3.to_wei("0.01", "gwei"),
        "chainId": 8453,  # Base
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction).hex()
    w3.eth.wait_for_transaction_receipt(tx_hash)

    # Step 3: Retry with payment proof
    result = httpx.post(
        f"{HYDRA_BASE}{endpoint}",
        json=payload,
        headers={"X-PAYMENT": tx_hash}
    )
    assert result.status_code == 200
    return result.json()

# Usage
signal = call_hydra_with_payment(
    "/v1/markets/signals",
    {"platform": "all", "category": "fed"},
    private_key="0x..."
)
```

## Discovery Manifest

HYDRA publishes a machine-readable pricing manifest at:

```
https://hydra-api-nlnj.onrender.com/.well-known/x402.json
```

x402-compatible agents can automatically discover endpoints, pricing, and payment addresses from this manifest.

## Pricing Summary

| Endpoint | USDC |
|----------|------|
| `GET /v1/markets` | Free |
| `GET /v1/markets/feed` | $0.05 |
| `POST /v1/markets/signal/{id}` | $0.10 |
| `POST /v1/markets/events` | $0.15 |
| `POST /v1/markets/signals` | $0.25 |
| `POST /v1/regulatory/query` | $0.50 |
| `POST /v1/regulatory/changes` | $0.50 |
| `POST /v1/oracle/uma` | $0.50 |
| `POST /v1/oracle/chainlink` | $0.50 |
| `POST /v1/regulatory/scan` | $1.00 |
| `POST /v1/markets/resolution` | $1.00 |
| `POST /v1/markets/alpha` | $2.00 |
| `POST /v1/regulatory/jurisdiction` | $2.00 |
| `POST /v1/fed/signal` | $5.00 |
| `POST /v1/fed/decision` | $25.00 |
| `POST /v1/fed/resolution` | $50.00 |

## Related

- [Polymarket Integration](polymarket-integration.md)
- [FOMC Fed Signals](fomc-fed-signals.md)
- [Live API Docs](https://hydra-api-nlnj.onrender.com/docs)
"""

    # ------------------------------------------------------------------
    # Method 6: run_autonomous_marketing_loop()
    # ------------------------------------------------------------------

    def run_autonomous_marketing_loop(
        self,
        force_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Main marketing loop. Checks what has already been done and
        executes only pending actions.

        Schedule:
          - API directories: once (idempotent)
          - Dev.to article: once
          - GitHub Discussions: once, then weekly new content
          - SEO docs: push now, refresh monthly

        Parameters
        ----------
        force_all : bool
            If True, re-execute all actions even if previously completed.
        """
        results: Dict[str, Any] = {}

        # Load prior log to determine what has been done
        done_actions: set[str] = set()
        if MARKETING_LOG.exists() and not force_all:
            with MARKETING_LOG.open("r") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                        if rec.get("result") not in ("error",):
                            done_actions.add(rec.get("action", ""))
                    except json.JSONDecodeError:
                        pass

        logger.info("Prior completed marketing actions: %s", done_actions)

        # 1. API directories — once
        if "submit_public_apis_pr" not in done_actions or force_all:
            logger.info("Submitting to API directories...")
            results["api_directories"] = self.submit_to_api_directories()
        else:
            results["api_directories"] = {"status": "already_done"}

        # 2. OpenAPI spec distribution
        if "push_openapi_to_github" not in done_actions or force_all:
            logger.info("Distributing OpenAPI spec...")
            results["openapi"] = self.submit_openapi_to_directories()
        else:
            results["openapi"] = {"status": "already_done"}

        # 3. SEO docs
        if "push_seo_doc_index.md" not in done_actions or force_all:
            logger.info("Generating and pushing SEO docs...")
            results["seo_docs"] = self.autonomous_seo_content()
        else:
            results["seo_docs"] = {"status": "already_done"}

        # 4. GitHub Discussions
        if "post_discussion_UMAprotocol/protocol" not in done_actions or force_all:
            logger.info("Posting GitHub Discussions...")
            results["discussions"] = self.post_github_discussions()
        else:
            results["discussions"] = {"status": "already_done"}

        # 5. Dev.to article (requires API key)
        if "publish_dev_to_article" not in done_actions or force_all:
            if DEV_TO_API_KEY:
                logger.info("Publishing Dev.to article...")
                results["devto"] = self.publish_dev_to_article()
            else:
                results["devto"] = {"status": "skipped", "reason": "DEV_TO_API_KEY not set"}
        else:
            results["devto"] = {"status": "already_done"}

        _log_action("run_autonomous_marketing_loop", "completed", {"summary": {
            k: v.get("status") if isinstance(v, dict) else "dict" for k, v in results.items()
        }})

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _push_file_to_repo(
        self,
        path: str,
        content: str,
        message: str,
        branch: str = "master",
    ) -> Dict[str, Any]:
        """
        Create or update a file in the HYDRA GitHub repo.
        Uses the GitHub Contents API.
        """
        with httpx.Client(headers=self.github_headers, timeout=30.0) as client:
            # Check if file exists (to get SHA for update)
            existing = client.get(
                f"{GITHUB_API_BASE}/repos/{HYDRA_REPO}/contents/{path}",
                params={"ref": branch},
            )

            content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            payload: Dict[str, Any] = {
                "message": message,
                "content": content_b64,
                "branch": branch,
            }

            if existing.status_code == 200:
                payload["sha"] = existing.json()["sha"]

            resp = client.put(
                f"{GITHUB_API_BASE}/repos/{HYDRA_REPO}/contents/{path}",
                json=payload,
            )

            if resp.status_code in (200, 201):
                return {
                    "status": "pushed",
                    "path": path,
                    "url": resp.json().get("content", {}).get("html_url"),
                }
            else:
                return {
                    "status": "error",
                    "code": resp.status_code,
                    "error": resp.text[:300],
                }
