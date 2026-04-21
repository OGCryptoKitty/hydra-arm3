# HYDRA — 402-Native Paid Work Engine for Agents

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/OGCryptoKitty/hydra-arm3)

**40 paid API endpoints** from $0.001 USDC. Web extraction, search, format conversion, developer tools, web checks, public data, regulatory intelligence, prediction market signals, and oracle data. Pay-per-call via **x402** on Base L2.

**Live:** [hydra-api-nlnj.onrender.com](https://hydra-api-nlnj.onrender.com) | **Docs:** [/docs](https://hydra-api-nlnj.onrender.com/docs) | **x402:** [/.well-known/x402.json](https://hydra-api-nlnj.onrender.com/.well-known/x402.json)

## MCP Server

HYDRA exposes all 40 paid + 12 free endpoints as MCP tools via [Model Context Protocol](https://modelcontextprotocol.io).

**Server URL:** `https://hydra-api-nlnj.onrender.com/mcp`
**Transport:** Streamable HTTP

```bash
# Claude Code
claude mcp add --transport http hydra https://hydra-api-nlnj.onrender.com/mcp

# Claude Desktop — add to claude_desktop_config.json:
```
```json
{
  "mcpServers": {
    "hydra": {
      "url": "https://hydra-api-nlnj.onrender.com/mcp"
    }
  }
}
```

### MCP Tools (40 paid + 12 free)

#### Extraction & Search ($0.01 - $0.05)
| Tool | Price | Description |
|------|-------|-------------|
| `extract_url` | $0.01 | Structured web extraction — title, headings, text, links, metadata |
| `extract_search` | $0.02 | Web search with structured result extraction |
| `extract_multi` | $0.05 | Batch extraction from up to 5 URLs in parallel |

#### Web Checks ($0.003 - $0.005)
| Tool | Price | Description |
|------|-------|-------------|
| `check_url` | $0.005 | URL health — status code, redirects, response time |
| `check_dns` | $0.005 | DNS records — A, AAAA, MX, TXT, NS, CNAME |
| `check_ssl` | $0.005 | SSL certificate — issuer, expiry, SANs, days remaining |
| `check_headers` | $0.003 | HTTP headers with security analysis and score |

#### Format Conversion ($0.003 - $0.005)
| Tool | Price | Description |
|------|-------|-------------|
| `convert_html2md` | $0.005 | HTML to Markdown — headings, lists, links, code, tables |
| `convert_json2csv` | $0.003 | JSON array to CSV with auto-detected headers |
| `convert_csv2json` | $0.003 | CSV text to JSON array |

#### Developer Tools ($0.001 - $0.003)
| Tool | Price | Description |
|------|-------|-------------|
| `hash_text` | $0.001 | SHA-256, SHA-512, MD5, SHA-1, SHA3-256 |
| `encode_decode` | $0.001 | Base64, URL, hex encode/decode |
| `text_diff` | $0.003 | Unified diff with change stats and similarity |
| `validate_json` | $0.001 | JSON validation with pretty-print |
| `validate_email` | $0.002 | Email format + MX record check |

#### Public Data ($0.01 - $0.02)
| Tool | Price | Description |
|------|-------|-------------|
| `wikipedia_summary` | $0.01 | Wikipedia article summary with thumbnail |
| `arxiv_search` | $0.02 | arXiv paper search — authors, abstracts, PDFs |
| `edgar_filings` | $0.02 | SEC EDGAR filing search — 10-K, 10-Q, 8-K |

#### Agent Utilities ($0.001 - $0.01)
| Tool | Price | Description |
|------|-------|-------------|
| `crypto_price` | $0.001 | Token price, 24h change, market cap |
| `gas_prices` | $0.001 | Base L2 gas prices with cost estimates |
| `wallet_balance` | $0.001 | ETH and USDC balance on Base |
| `tx_status` | $0.001 | Transaction receipt lookup |
| `parse_rss` | $0.002 | RSS/Atom feed to structured JSON |
| `scrape_url` | $0.005 | URL to clean structured text |
| `batch_utility` | $0.01 | Batch up to 5 utility calls |

#### Regulatory Intelligence ($1.00 - $3.00)
| Tool | Price | Description |
|------|-------|-------------|
| `regulatory_scan` | $2.00 | Full regulatory risk scan |
| `regulatory_changes` | $1.00 | Recent classified regulatory changes |
| `regulatory_query` | $1.00 | Regulatory Q&A with statutory citations |
| `regulatory_jurisdiction` | $3.00 | Jurisdiction comparison with cost modeling |

#### Prediction Markets ($0.10 - $25.00)
| Tool | Price | Description |
|------|-------|-------------|
| `market_feed` | $0.10 | Last 10 regulatory events for markets |
| `market_events` | $0.50 | Classified regulatory events by agency |
| `market_signal` | $2.00 | Scored signal for one prediction market |
| `market_signals` | $5.00 | Bulk signals for all active markets |
| `alpha_report` | $10.00 | Premium alpha with Kelly sizing |
| `market_resolution` | $25.00 | Resolution verdict for settlement |

#### Fed Intelligence ($5.00 - $50.00)
| Tool | Price | Description |
|------|-------|-------------|
| `fed_signal` | $5.00 | Pre-FOMC signal with rate probabilities |
| `fed_decision` | $25.00 | Real-time FOMC decision classification |
| `fed_resolution` | $50.00 | FOMC resolution verdict for oracles |

#### Oracle Integration ($5.00)
| Tool | Price | Description |
|------|-------|-------------|
| `oracle_uma` | $5.00 | UMA Optimistic Oracle assertion data |
| `oracle_chainlink` | $5.00 | Chainlink External Adapter response |

## x402 Payment Flow

```
1. Call any paid endpoint → 402 Payment Required
   Response includes: amount, wallet, chain_id, x402 machine-readable block

2. Send USDC to 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141 on Base (chain 8453)

3. Retry with Header: X-Payment-Proof: 0x{tx_hash}
   → 200 OK (payment verified on-chain via Base RPC)
```

Three payment methods: **x402** (standard), **X-Payment-Proof** (direct tx hash), **MPP** (session-based).

## Quick Start

```bash
# Free endpoints — no payment needed
curl -s https://hydra-api-nlnj.onrender.com/health | python3 -m json.tool
curl -s https://hydra-api-nlnj.onrender.com/v1/markets | python3 -m json.tool
curl -s https://hydra-api-nlnj.onrender.com/pricing | python3 -m json.tool

# Trigger a 402 challenge (shows payment instructions)
curl -s https://hydra-api-nlnj.onrender.com/v1/check/url?url=https://example.com
```

## Deploy

### One-Click (Render)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/OGCryptoKitty/hydra-arm3)

### Local
```bash
pip install -r requirements.txt
cp scripts/.env.example .env
uvicorn src.main:app --host 0.0.0.0 --port 8402
```

## Architecture

- **FastAPI** async API with x402 payment middleware
- **Web3.py** on-chain USDC payment verification via Base RPC
- **HydraAutomaton** — autonomous heartbeat (balance checks, lifecycle, remittance, keepalive)
- **ConstitutionCheck** — three-law compliance (OFAC, solvency, filing deadlines)
- **TransactionLog** — append-only JSONL audit trail
- **Rule-based engines** — all endpoints are deterministic, zero LLM dependency

## Discovery

| Protocol | URL |
|----------|-----|
| **x402 Manifest** | [`/.well-known/x402.json`](https://hydra-api-nlnj.onrender.com/.well-known/x402.json) |
| **MCP Manifest** | [`/.well-known/mcp.json`](https://hydra-api-nlnj.onrender.com/.well-known/mcp.json) |
| **MCP Server** | [`/mcp`](https://hydra-api-nlnj.onrender.com/mcp) |
| **A2A Agent Card** | [`/.well-known/agent.json`](https://hydra-api-nlnj.onrender.com/.well-known/agent.json) |
| **LLMs.txt** | [`/.well-known/llms.txt`](https://hydra-api-nlnj.onrender.com/.well-known/llms.txt) |
| **AI Plugin** | [`/.well-known/ai-plugin.json`](https://hydra-api-nlnj.onrender.com/.well-known/ai-plugin.json) |
| **OpenAPI** | [`/openapi.json`](https://hydra-api-nlnj.onrender.com/openapi.json) |
| **APIs.json** | [`/apis.json`](https://hydra-api-nlnj.onrender.com/apis.json) |
| **Sitemap** | [`/sitemap.xml`](https://hydra-api-nlnj.onrender.com/sitemap.xml) |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WALLET_ADDRESS` | `0x2F12...141` | USDC recipient wallet |
| `WALLET_PRIVATE_KEY` | — | Private key for treasury ops (Aave yield, remittance) |
| `BASE_RPC_URL` | `https://mainnet.base.org` | Base L2 RPC |
| `HYDRA_STATE_DIR` | `/tmp/hydra-data` | State persistence directory |
| `PORT` | `8402` | Server port |

## License

Proprietary — HYDRA Systems LLC
