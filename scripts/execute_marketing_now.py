"""
Execute all HYDRA autonomous marketing actions immediately.

Run: python scripts/execute_marketing_now.py

This script bootstraps the marketing pipeline in one shot:
  1. Fetch OpenAPI spec from live API, save to docs/openapi.json
  2. Generate all SEO docs pages
  3. Push docs/ to GitHub
  4. Post to GitHub Discussions on relevant repos
  5. Submit to public-apis/public-apis PR
  6. Submit to APIs-guru/openapi-directory PR
  7. Publish Dev.to article (if DEV_TO_API_KEY set)
  8. Generate initial revenue report
  9. Log all results

All results are logged to /home/user/workspace/hydra-bootstrap/marketing_log.jsonl
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hydra.execute_marketing")

# Bootstrap directory
BOOTSTRAP_DIR = Path("/home/user/workspace/hydra-bootstrap")
BOOTSTRAP_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_FILE = BOOTSTRAP_DIR / f"marketing_run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"


def step_header(num: int, title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  Step {num}: {title}")
    print(f"{'='*60}")


def main() -> None:
    print("""
╔══════════════════════════════════════════════════════════╗
║       HYDRA Autonomous Marketing Engine — Bootstrap      ║
║       Zero-human-involvement marketing execution         ║
╚══════════════════════════════════════════════════════════╝
""")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print(f"Results will be saved to: {RESULTS_FILE}")

    # Import after path setup
    try:
        from src.runtime.autonomous_marketing import AutonomousMarketing
        from src.runtime.revenue_optimizer import RevenueOptimizer
    except ImportError as exc:
        logger.error("Import failed: %s", exc)
        print(f"\nFATAL: Could not import HYDRA modules. Run from the hydra-arm3 root directory.")
        print(f"  cd /home/user/workspace/hydra-arm3 && python scripts/execute_marketing_now.py")
        sys.exit(1)

    marketing = AutonomousMarketing()
    revenue = RevenueOptimizer()
    all_results: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": {},
    }

    # ------------------------------------------------------------------
    # Step 1: Fetch OpenAPI spec from live API
    # ------------------------------------------------------------------
    step_header(1, "Fetch live OpenAPI spec + distribute to directories")
    try:
        result = marketing.submit_openapi_to_directories()
        all_results["steps"]["openapi_distribution"] = result
        for key, val in result.items():
            status = val.get("status", "?") if isinstance(val, dict) else str(val)
            print(f"  [{key}]: {status}")
    except Exception as exc:
        logger.exception("OpenAPI distribution failed")
        all_results["steps"]["openapi_distribution"] = {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Step 2: Generate and push SEO docs
    # ------------------------------------------------------------------
    step_header(2, "Generate and push SEO documentation pages")
    try:
        result = marketing.autonomous_seo_content()
        all_results["steps"]["seo_docs"] = result
        for filename, val in result.items():
            status = val.get("status", "?") if isinstance(val, dict) else str(val)
            print(f"  [{filename}]: {status}")
    except Exception as exc:
        logger.exception("SEO docs generation failed")
        all_results["steps"]["seo_docs"] = {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Step 3: Post to GitHub Discussions
    # ------------------------------------------------------------------
    step_header(3, "Post to GitHub Discussions on relevant repos")
    try:
        result = marketing.post_github_discussions()
        all_results["steps"]["github_discussions"] = result
        for repo, val in result.items():
            status = val.get("status", "?") if isinstance(val, dict) else str(val)
            url = val.get("url", "") if isinstance(val, dict) else ""
            print(f"  [{repo}]: {status} {url}")
    except Exception as exc:
        logger.exception("GitHub Discussions failed")
        all_results["steps"]["github_discussions"] = {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Step 4: Submit to public-apis/public-apis PR
    # ------------------------------------------------------------------
    step_header(4, "Submit PR to public-apis/public-apis")
    try:
        result = marketing._submit_public_apis_pr()
        all_results["steps"]["public_apis_pr"] = result
        status = result.get("status", "?")
        url = result.get("url", "")
        print(f"  Status: {status}")
        if url:
            print(f"  URL: {url}")
        msg = result.get("message") or result.get("error", "")
        if msg:
            print(f"  Detail: {msg}")
    except Exception as exc:
        logger.exception("public-apis PR failed")
        all_results["steps"]["public_apis_pr"] = {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Step 5: Submit to APIs.guru PR
    # ------------------------------------------------------------------
    step_header(5, "Submit PR to APIs-guru/openapi-directory")
    try:
        result = marketing._submit_apis_guru_pr()
        all_results["steps"]["apis_guru_pr"] = result
        status = result.get("status", "?")
        url = result.get("url", "")
        print(f"  Status: {status}")
        if url:
            print(f"  URL: {url}")
        msg = result.get("message") or result.get("error", "")
        if msg:
            print(f"  Detail: {msg[:200]}")
    except Exception as exc:
        logger.exception("APIs.guru PR failed")
        all_results["steps"]["apis_guru_pr"] = {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Step 6: Publish Dev.to article
    # ------------------------------------------------------------------
    step_header(6, "Publish Dev.to article")
    dev_to_key = os.environ.get("DEV_TO_API_KEY", "")
    if not dev_to_key:
        print("  SKIPPED: DEV_TO_API_KEY environment variable not set")
        print("  To publish: export DEV_TO_API_KEY=your_key && python scripts/execute_marketing_now.py")
        all_results["steps"]["devto_article"] = {"status": "skipped", "reason": "DEV_TO_API_KEY not set"}
    else:
        try:
            result = marketing.publish_dev_to_article()
            all_results["steps"]["devto_article"] = result
            status = result.get("status", "?")
            url = result.get("url", "")
            print(f"  Status: {status}")
            if url:
                print(f"  URL: {url}")
        except Exception as exc:
            logger.exception("Dev.to publication failed")
            all_results["steps"]["devto_article"] = {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Step 7: Generate initial revenue report
    # ------------------------------------------------------------------
    step_header(7, "Generate initial revenue report")
    try:
        report = revenue.generate_weekly_report()
        all_results["steps"]["revenue_report"] = {"status": "generated", "chars": len(report)}
        print(f"  Generated {len(report)} chars")
        print("  Saved to /home/user/workspace/hydra-bootstrap/reports/")

        # Also print a brief summary
        performance = revenue.analyze_endpoint_performance()
        print(f"\n  Revenue summary:")
        print(f"    Total revenue: ${performance['total_revenue_usdc']:.2f} USDC")
        print(f"    Total calls: {performance['total_calls']}")
    except Exception as exc:
        logger.exception("Revenue report failed")
        all_results["steps"]["revenue_report"] = {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Step 8: Log pricing recommendations
    # ------------------------------------------------------------------
    step_header(8, "Generate pricing recommendations")
    try:
        pricing_recs = revenue.generate_pricing_recommendation()
        recs = pricing_recs.get("recommendations", [])
        all_results["steps"]["pricing_recommendations"] = pricing_recs
        print(f"  {len(recs)} recommendations generated")
        for rec in recs[:3]:
            endpoint = rec.get("endpoint", "")
            action = rec.get("action", "").replace("_", " ")
            priority = rec.get("priority", "").upper()
            print(f"  [{priority}] {endpoint}: {action}")
    except Exception as exc:
        logger.exception("Pricing recommendations failed")
        all_results["steps"]["pricing_recommendations"] = {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    all_results["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Count successes/failures
    success_count = 0
    failure_count = 0
    for step_name, step_result in all_results["steps"].items():
        if isinstance(step_result, dict):
            status = step_result.get("status", "")
            if status in ("error",):
                failure_count += 1
            elif status not in ("skipped",):
                success_count += 1

    print(f"\n{'='*60}")
    print(f"  COMPLETE: {success_count} succeeded, {failure_count} failed")
    print(f"  Completed: {all_results['completed_at']}")
    print(f"{'='*60}\n")

    # Save results JSON
    RESULTS_FILE.write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")
    print(f"Full results saved to: {RESULTS_FILE}")

    # Print any PR URLs
    print("\nCreated resources:")
    for step_name, step_result in all_results["steps"].items():
        if isinstance(step_result, dict):
            url = step_result.get("url")
            if url:
                print(f"  {step_name}: {url}")

    return all_results


if __name__ == "__main__":
    main()
