"""
HYDRA x402 Client — Reference Implementation
=============================================
Drop-in Python client for paying and calling HYDRA endpoints.
Handles x402 payment flow automatically.

Usage:
    from hydra_client import HydraClient

    client = HydraClient(private_key="0x...")

    # Free endpoints (no payment needed)
    health = client.get("/health")
    directory = client.get("/v1/x402/directory")

    # Paid endpoints (auto-pays via x402)
    alpha = client.get("/v1/intelligence/alpha")      # $5.00
    pulse = client.get("/v1/intelligence/pulse")       # $0.50
    risk = client.get("/v1/intelligence/risk-score", params={"token": "ETH"})  # $2.00
    extract = client.post("/v1/extract/url", json={"url": "https://sec.gov"})  # $0.01

    # Direct payment proof (manual)
    result = client.get("/v1/fed/signal", headers={"X-Payment-Proof": "0x_your_tx_hash"})
"""

import hashlib
import json
import time
from decimal import Decimal
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    raise ImportError("pip install requests")

try:
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    _HAS_WEB3 = True
except ImportError:
    _HAS_WEB3 = False


HYDRA_BASE = "https://hydra-api-nlnj.onrender.com"
BASE_RPC = "https://mainnet.base.org"
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
HYDRA_WALLET = "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141"
CHAIN_ID = 8453

# Minimal ERC-20 ABI for transfer
ERC20_ABI = [
    {
        "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
        "stateMutability": "view",
    },
]


class HydraClient:
    """
    Reference x402 client for HYDRA.

    Handles the full payment flow:
    1. Call endpoint
    2. If 402 returned, parse payment instructions
    3. Send USDC on Base to HYDRA wallet
    4. Retry with X-Payment-Proof header containing tx hash
    5. Return the paid response
    """

    def __init__(
        self,
        private_key: Optional[str] = None,
        base_url: str = HYDRA_BASE,
        rpc_url: str = BASE_RPC,
        auto_pay: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.auto_pay = auto_pay
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "HydraClient/1.0 (x402)"

        if private_key and _HAS_WEB3:
            self._w3 = Web3(Web3.HTTPProvider(rpc_url))
            self._account = self._w3.eth.account.from_key(private_key)
            self._usdc = self._w3.eth.contract(
                address=Web3.to_checksum_address(USDC_ADDRESS),
                abi=ERC20_ABI,
            )
        else:
            self._w3 = None
            self._account = None
            self._usdc = None

    def get(self, path: str, params: Optional[dict] = None, headers: Optional[dict] = None, **kwargs) -> dict:
        return self._request("GET", path, params=params, headers=headers, **kwargs)

    def post(self, path: str, json: Optional[dict] = None, headers: Optional[dict] = None, **kwargs) -> dict:
        return self._request("POST", path, json=json, headers=headers, **kwargs)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", None) or {}

        resp = self._session.request(method, url, headers=headers, timeout=30, **kwargs)

        # Free endpoint or already paid
        if resp.status_code == 200:
            return resp.json()

        # Payment required
        if resp.status_code == 402:
            payment_info = resp.json()

            if not self.auto_pay or not self._w3:
                return {
                    "error": "payment_required",
                    "status": 402,
                    "payment_instructions": payment_info,
                    "hint": "Initialize HydraClient with private_key= to enable auto-payment, or pass X-Payment-Proof header with a USDC tx hash.",
                }

            # Auto-pay: send USDC
            amount_usdc = Decimal(str(payment_info.get("amount", payment_info.get("price", "0"))))
            tx_hash = self._send_usdc(amount_usdc)

            if tx_hash:
                # Retry with payment proof
                headers["X-Payment-Proof"] = tx_hash
                resp2 = self._session.request(method, url, headers=headers, timeout=30, **kwargs)
                if resp2.status_code == 200:
                    return resp2.json()
                return {"error": f"Payment sent ({tx_hash}) but endpoint returned {resp2.status_code}", "response": resp2.text[:500]}

            return {"error": "USDC transfer failed", "payment_instructions": payment_info}

        return {"error": f"HTTP {resp.status_code}", "response": resp.text[:500]}

    def _send_usdc(self, amount_usdc: Decimal) -> Optional[str]:
        if not self._w3 or not self._account:
            return None

        amount_base_units = int(amount_usdc * 10**6)

        tx = self._usdc.functions.transfer(
            Web3.to_checksum_address(HYDRA_WALLET),
            amount_base_units,
        ).build_transaction({
            "from": self._account.address,
            "nonce": self._w3.eth.get_transaction_count(self._account.address),
            "gas": 100_000,
            "gasPrice": self._w3.eth.gas_price,
            "chainId": CHAIN_ID,
        })

        signed = self._w3.eth.account.sign_transaction(tx, self._account.key)
        tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)

        # Wait for confirmation
        receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt.status == 1:
            return tx_hash.hex()
        return None

    def balance(self) -> dict:
        """Check your USDC balance on Base."""
        if not self._w3 or not self._account:
            return {"error": "No wallet configured"}
        bal = self._usdc.functions.balanceOf(self._account.address).call()
        return {"address": self._account.address, "usdc_balance": f"${bal / 1e6:.6f}"}


# ── Quick demo ────────────────────────────────────────────────
if __name__ == "__main__":
    print("HYDRA x402 Client — Demo")
    print("=" * 40)

    client = HydraClient()  # No private key = read-only mode

    # Free endpoints
    print("\n[FREE] Health check:")
    print(json.dumps(client.get("/health"), indent=2)[:500])

    print("\n[FREE] x402 Ecosystem Directory:")
    result = client.get("/v1/x402/directory")
    print(f"  Services indexed: {result.get('total_services', 'N/A')}")

    print("\n[FREE] Pricing:")
    result = client.get("/pricing")
    print(f"  Endpoints: {len(result.get('endpoints', result.get('pricing', {})))}")

    # Paid endpoint (will return payment instructions in read-only mode)
    print("\n[PAID] Intelligence Alpha ($5.00):")
    result = client.get("/v1/intelligence/alpha")
    if "error" in result:
        print(f"  → {result['error']}")
        print(f"  → To auto-pay: HydraClient(private_key='0x...')")
    else:
        print(f"  Composite score: {result.get('composite_score')}")
        print(f"  Direction: {result.get('direction')}")

    print("\nFull docs: https://hydra-api-nlnj.onrender.com/docs")
    print("x402 manifest: https://hydra-api-nlnj.onrender.com/.well-known/x402.json")
