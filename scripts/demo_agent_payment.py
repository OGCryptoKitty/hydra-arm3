#!/usr/bin/env python3
"""
HYDRA x402 Payment Demo — 5-step agent payment flow.

Demonstrates how an AI agent discovers, tests, and pays for HYDRA endpoints
using the x402-payment-harness SDK on Base L2.

Requirements:
    pip install -r scripts/requirements.txt

Environment:
    Copy scripts/.env.example to scripts/.env and fill in your wallet key.
"""

import os
import sys
import json
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

HYDRA_BASE = "https://hydra-api-nlnj.onrender.com"
WALLET_KEY = os.getenv("WALLET_PRIVATE_KEY", "")


def step1_discover():
    """Step 1: Discover HYDRA via x402 manifest."""
    print("\n=== Step 1: Discovery ===")
    r = httpx.get(f"{HYDRA_BASE}/.well-known/x402.json")
    manifest = r.json()
    print(f"Service: {manifest['name']}")
    print(f"Network: {manifest['payment']['network']}")
    print(f"Token:   {manifest['payment']['token']}")
    print(f"Wallet:  {manifest['payment']['wallet']}")
    print(f"Endpoints: {len(manifest['endpoints'])}")
    return manifest


def step2_free_call():
    """Step 2: Test a free endpoint to verify connectivity."""
    print("\n=== Step 2: Free Endpoint Test ===")
    r = httpx.get(f"{HYDRA_BASE}/v1/markets")
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"Markets found: {len(data.get('markets', data.get('data', [])))}")
    return data


def step3_trigger_402():
    """Step 3: Call a paid endpoint without payment to get 402 challenge."""
    print("\n=== Step 3: Trigger 402 Challenge ===")
    r = httpx.get(f"{HYDRA_BASE}/v1/util/crypto/price", params={"token": "ETH"})
    print(f"Status: {r.status_code}")
    if r.status_code == 402:
        print("Payment required — x402 challenge received")
        print(f"Headers: {dict(r.headers)}")
    return r


def step4_paid_call_harness():
    """Step 4: Pay via x402-payment-harness SDK."""
    print("\n=== Step 4: Paid Call via x402-payment-harness ===")

    if not WALLET_KEY:
        print("SKIP: Set WALLET_PRIVATE_KEY in scripts/.env to test payments")
        return None

    try:
        from x402_harness import X402Client, PaymentConfig

        config = PaymentConfig(
            network="base",
            chain_id=8453,
            token_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            private_key=WALLET_KEY,
        )
        client = X402Client(base_url=HYDRA_BASE)

        result = client.pay(
            url="/v1/util/crypto/price?token=ETH",
            config=config,
            method="GET",
        )
        print(f"Payment status: {result.status}")
        print(f"Tx hash: {result.tx_hash}")
        print(f"Response: {json.dumps(result.data, indent=2)[:200]}")
        return result
    except ImportError:
        print("x402-payment-harness not installed. Trying direct payment...")
        return step4_paid_call_direct()


def step4_paid_call_direct():
    """Step 4 (fallback): Pay via direct X-Payment-Proof header."""
    print("\nDirect payment requires a pre-sent USDC transaction.")
    print("1. Send 0.001 USDC to 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141 on Base")
    print("2. Copy the tx hash")
    print("3. Call: curl -H 'X-Payment-Proof: 0x<tx_hash>' "
          f"'{HYDRA_BASE}/v1/util/crypto/price?token=ETH'")
    return None


def step5_paid_call_sdk():
    """Step 5: Pay via official x402 SDK."""
    print("\n=== Step 5: Paid Call via x402 SDK ===")

    if not WALLET_KEY:
        print("SKIP: Set WALLET_PRIVATE_KEY in scripts/.env to test payments")
        return None

    try:
        from x402.client import x402ClientSync
        from eth_account import Account

        signer = Account.from_key(WALLET_KEY)
        client = x402ClientSync(signer=signer)

        r = client.get(
            f"{HYDRA_BASE}/v1/util/crypto/price",
            params={"token": "BTC"},
        )
        print(f"Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)[:200]}")
        return r
    except ImportError:
        print("x402 SDK not installed. Install: pip install 'x402[evm]>=2.6.0'")
        return None


def main():
    print("HYDRA x402 Payment Demo")
    print("=" * 50)

    manifest = step1_discover()
    data = step2_free_call()
    challenge = step3_trigger_402()
    result_harness = step4_paid_call_harness()
    result_sdk = step5_paid_call_sdk()

    print("\n" + "=" * 50)
    print("Demo complete.")
    if not WALLET_KEY:
        print("\nTo test paid endpoints, set WALLET_PRIVATE_KEY in scripts/.env")


if __name__ == "__main__":
    main()
