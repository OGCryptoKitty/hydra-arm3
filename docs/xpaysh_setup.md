# HYDRA — xpay.sh MCP Monetization Setup

[xpay.sh](https://xpay.sh) proxies MCP servers with per-tool billing, taking a 5% platform fee.

## Registration

1. Create account at https://xpay.sh
2. Register HYDRA MCP server:
   - **Server URL**: `https://hydra-api-nlnj.onrender.com/mcp`
   - **Transport**: Streamable HTTP
   - **Name**: `hydra-regulatory-intelligence`

3. Configure per-tool pricing to match HYDRA's x402 prices:
   | Tool | Price |
   |------|-------|
   | scrape_url | $0.005 |
   | crypto_price | $0.001 |
   | parse_rss | $0.002 |
   | wallet_balance | $0.001 |
   | gas_prices | $0.001 |
   | tx_status | $0.001 |
   | batch_utility | $0.01 |
   | market_feed | $0.10 |
   | market_events | $0.50 |
   | regulatory_scan | $2.00 |
   | regulatory_changes | $1.00 |
   | regulatory_jurisdiction | $3.00 |
   | regulatory_query | $1.00 |
   | market_signal | $2.00 |
   | market_signals | $5.00 |
   | alpha_report | $10.00 |
   | fed_signal | $5.00 |
   | fed_decision | $25.00 |
   | fed_resolution | $50.00 |
   | oracle_uma | $5.00 |
   | oracle_chainlink | $5.00 |
   | market_resolution | $25.00 |

4. Once registered, HYDRA will be available at:
   ```
   https://hydra-regulatory-intelligence.mcp.xpay.sh/mcp
   ```

## Client Configuration

Users connect via the xpay.sh proxy URL:
```bash
claude mcp add --transport http hydra-regulatory https://hydra-regulatory-intelligence.mcp.xpay.sh/mcp
```

## Revenue Split

- 95% to HYDRA developer
- 5% xpay.sh platform fee
- Payments handled by xpay.sh (Stripe billing)
- No USDC/crypto needed by the end user
