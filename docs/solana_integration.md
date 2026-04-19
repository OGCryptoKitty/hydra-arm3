# HYDRA — Solana x402 Integration Roadmap

Future expansion: accept x402 payments in USDC on Solana alongside Base L2.

## Why Solana

- Sub-cent transaction fees (~$0.00025 per tx)
- 400ms finality vs Base ~2s
- Growing AI agent ecosystem (Solana Agent Kit, ai16z, ELIZA)
- x402 protocol supports Solana via `solana:mainnet` network identifier

## Architecture

### Dual-chain x402 manifest

```json
{
  "payment": [
    {
      "network": "eip155:8453",
      "chain_id": 8453,
      "token": "USDC",
      "token_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      "wallet": "0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141"
    },
    {
      "network": "solana:mainnet",
      "token": "USDC",
      "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
      "wallet": "<SOLANA_WALLET_ADDRESS>"
    }
  ]
}
```

### Implementation Steps

1. **Generate Solana wallet** — Ed25519 keypair, fund with SOL for rent
2. **Update x402.json** — Add Solana payment option to manifest
3. **Update middleware** — `src/x402/middleware.py` to verify Solana USDC transfers via RPC
4. **Update verify.py** — Add `verify_solana_payment()` using `solana-py` or `solders`
5. **Test** — End-to-end payment flow with Solana devnet first

### Dependencies

```
solana-py>=0.34.0
solders>=0.21.0
```

### Revenue Impact

- Access to Solana-native AI agents that don't hold EVM tokens
- Lower payment friction for micro-tier endpoints ($0.001 - $0.01)
- Estimated 20-30% of AI agent market is Solana-native

## Status

**Planned** — implement when Base L2 revenue exceeds $100/month to justify multi-chain maintenance.
