# HYDRA Client Examples

## Quick Start

```bash
pip install requests web3
python hydra_client.py
```

## Auto-Payment Mode

```python
from hydra_client import HydraClient

# Initialize with your private key (Base L2 wallet with USDC)
client = HydraClient(private_key="0x_your_private_key")

# Paid endpoints auto-pay via x402
alpha = client.get("/v1/intelligence/alpha")  # $5.00 USDC
print(alpha["composite_score"], alpha["direction"])

# Check your balance
print(client.balance())
```

## Read-Only Mode (no payments)

```python
client = HydraClient()  # No private key

# Free endpoints work normally
health = client.get("/health")
directory = client.get("/v1/x402/directory")

# Paid endpoints return payment instructions
result = client.get("/v1/intelligence/alpha")
# → {"error": "payment_required", "payment_instructions": {...}}
```

## MCP Integration

```bash
claude mcp add --transport http hydra https://hydra-api-nlnj.onrender.com/mcp
```

## Endpoints

| Endpoint | Price | Description |
|----------|-------|-------------|
| GET /v1/intelligence/alpha | $5.00 | Composite regulatory + Fed + markets signal |
| GET /v1/intelligence/pulse | $0.50 | Hourly regulatory pulse |
| GET /v1/intelligence/risk-score | $2.00 | Token/protocol risk score |
| GET /v1/intelligence/digest | $1.00 | Daily regulatory digest |
| POST /v1/alerts/subscribe | $0.10 | Push alert webhooks (100 alerts) |
| GET /v1/x402/directory | FREE | x402 ecosystem directory |
| Full list | — | https://hydra-api-nlnj.onrender.com/pricing |
