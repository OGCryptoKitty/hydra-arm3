# HYDRA Arm 3 — Deploy & Earn

## 3-Minute Deploy to Render

### Step 1: Deploy (1 click)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/OGCryptoKitty/hydra-arm3)

Or manually:
1. Go to https://dashboard.render.com/
2. Click **New → Web Service**
3. Connect your GitHub repo: `OGCryptoKitty/hydra-arm3`
4. Render auto-detects the `render.yaml` — click **Apply**

### Step 2: Set Environment Variables (2 minutes)

In Render Dashboard → your service → **Environment**:

| Variable | Value | Required |
|----------|-------|----------|
| `WALLET_ADDRESS` | `0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141` | Yes |
| `WALLET_PRIVATE_KEY` | Your wallet's private key (for remittance) | Yes (for transfers) |
| `ANTHROPIC_API_KEY` | Get at https://console.anthropic.com/ | **Highly recommended** |
| `BASE_RPC_URL` | `https://mainnet.base.org` (free) or Alchemy key | Optional |

### Step 3: Set Up Your Receiving Wallet (2 minutes)

1. Download **Coinbase Wallet** (blue "W" icon, NOT the exchange):
   - iPhone: https://apps.apple.com/app/coinbase-wallet/id1278383455
   - Android: https://play.google.com/store/apps/details?id=org.toshi
2. Create wallet, write down 12-word phrase on paper
3. Copy your 0x... address

### Step 4: Connect Your Wallet to HYDRA

```bash
curl -X POST https://YOUR-HYDRA-URL/system/wallet \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SYSTEM_TOKEN" \
  -d '{"address": "0xYOUR_COINBASE_WALLET_ADDRESS"}'
```

### Step 5: Start Earning

HYDRA now earns USDC from every API call. At $1,000 balance, it prompts you to transfer.

---

## Get Your Anthropic API Key (enables AI-powered analysis)

1. Go to https://console.anthropic.com/
2. Sign up (free)
3. Go to **API Keys** → **Create Key**
4. Copy the key (starts with `sk-ant-...`)
5. Add to Render environment as `ANTHROPIC_API_KEY`

Cost: ~$0.002 per API call (Claude Haiku). Your endpoints charge $2-50/call. **99.9% margin.**

---

## Verify It's Working

```bash
# Health check
curl https://YOUR-HYDRA-URL/health

# See all pricing
curl https://YOUR-HYDRA-URL/pricing

# Test a paid endpoint (will return 402 with payment instructions)
curl -X POST https://YOUR-HYDRA-URL/v1/regulatory/scan \
  -H "Content-Type: application/json" \
  -d '{"business_description": "crypto exchange"}'
```
