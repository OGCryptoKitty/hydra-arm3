# x402 Payment Guide

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
