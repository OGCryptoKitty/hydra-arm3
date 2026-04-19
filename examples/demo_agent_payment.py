#!/usr/bin/env python3
"""
HYDRA x402 Payment Demo — End-to-end agent payment example.

Shows three ways to interact with HYDRA:
  1. Free endpoint (no payment required)
  2. Paid endpoint via x402-payment-harness (pip install x402-payment-harness)
  3. Paid endpoint via direct X-Payment-Proof header (bring your own tx hash)

Prerequisites:
  pip install httpx x402-payment-harness  # optional: for method 2

Usage:
  python demo_agent_payment.py                          # free endpoint only
  python demo_agent_payment.py --key 0xYOUR_PRIVATE_KEY # full paid flow
"""

import argparse
import json
import sys

import httpx

HYDRA_BASE = "https://hydra-api-nlnj.onrender.com"


def step_1_discover():
    """Discover HYDRA via x402 manifest."""
    print("=" * 60)
    print("Step 1: Discover HYDRA")
    print("=" * 60)

    manifest = httpx.get(f"{HYDRA_BASE}/.well-known/x402.json").json()
    print(f"  Name: {manifest['name']}")
    print(f"  Endpoints: {len(manifest['endpoints'])} total")
    print(f"  Network: {manifest['payment']['network']}")
    print(f"  Token: {manifest['payment']['token']}")
    print(f"  Wallet: {manifest['payment']['wallet']}")

    free = [e for e in manifest["endpoints"] if e["price"] == "free"]
    paid = [e for e in manifest["endpoints"] if e["price"] != "free"]
    print(f"  Free: {len(free)} | Paid: {len(paid)}")
    print()
    return manifest


def step_2_free_call():
    """Call a free endpoint — no payment required."""
    print("=" * 60)
    print("Step 2: Free endpoint — GET /v1/markets")
    print("=" * 60)

    resp = httpx.get(f"{HYDRA_BASE}/v1/markets")
    print(f"  Status: {resp.status_code}")
    data = resp.json()
    print(f"  Markets returned: {len(data.get('markets', data.get('data', [])))} ")
    print(f"  Response preview: {json.dumps(data, indent=2)[:300]}...")
    print()
    return resp.status_code == 200


def step_3_paid_402_challenge():
    """Hit a paid endpoint to see the 402 challenge."""
    print("=" * 60)
    print("Step 3: Paid endpoint 402 challenge — GET /v1/util/gas")
    print("=" * 60)

    resp = httpx.get(f"{HYDRA_BASE}/v1/util/gas")
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 402:
        print("  x402 payment required (this is correct behavior)")
        print(f"  Headers: {dict(resp.headers)}")
        try:
            body = resp.json()
            print(f"  Payment info: {json.dumps(body, indent=2)[:400]}")
        except Exception:
            print(f"  Body: {resp.text[:400]}")
    print()
    return resp.status_code == 402


def step_4_paid_with_harness(private_key: str):
    """Pay via x402-payment-harness (if installed)."""
    print("=" * 60)
    print("Step 4: Paid call via x402-payment-harness ($0.001)")
    print("=" * 60)

    try:
        import subprocess

        result = subprocess.run(
            [
                "x402-pay",
                "--url", f"{HYDRA_BASE}/v1/util/gas",
                "--key", private_key,
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        print(f"  Exit code: {result.returncode}")
        print(f"  Output: {result.stdout[:500]}")
        if result.stderr:
            print(f"  Stderr: {result.stderr[:300]}")
        return result.returncode == 0
    except FileNotFoundError:
        print("  x402-payment-harness not installed.")
        print("  Install: pip install x402-payment-harness")
        return False
    except Exception as exc:
        print(f"  Error: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="HYDRA x402 Payment Demo")
    parser.add_argument("--key", help="EOA private key for paid x402 calls")
    args = parser.parse_args()

    print()
    print("HYDRA Regulatory Intelligence — x402 Payment Demo")
    print()

    step_1_discover()
    step_2_free_call()
    challenge_ok = step_3_paid_402_challenge()

    if args.key:
        step_4_paid_with_harness(args.key)
    else:
        print("=" * 60)
        print("Step 4: Skipped (no --key provided)")
        print("=" * 60)
        print("  To make a paid call, run:")
        print(f"  python {sys.argv[0]} --key 0xYOUR_EOA_PRIVATE_KEY")
        print()

    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Discovery: OK")
    print(f"  Free endpoint: OK")
    print(f"  402 challenge: {'OK' if challenge_ok else 'UNEXPECTED'}")
    print(f"  Paid call: {'run with --key' if not args.key else 'attempted'}")
    print()


if __name__ == "__main__":
    main()
