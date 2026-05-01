# HYDRA -- Awesome List Submission Entries

Prepared entries for submitting HYDRA to curated awesome lists.
Each section contains the target repo, format, drafted entry, requirements, and PR instructions.

---

## 1. punkpeye/awesome-mcp-servers

**Repo:** https://github.com/punkpeye/awesome-mcp-servers
**Stars:** Largest MCP server directory (10k+ stars)
**Format:** Markdown list items with badges
**Category:** Place under an appropriate section (e.g., Data & Finance, or create "Regulatory / Finance" if none fits)

### Entry

```markdown
- [HYDRA](https://github.com/OGCryptoKitty/hydra-arm3) 🐍 ☁️ - Autonomous regulatory intelligence API with 55+ paid tools. Real-time data from 13 government/market sources (SEC EDGAR, CFTC, FinCEN, Fed, FDIC, FRED, Treasury, Kalshi). FOMC rate probabilities, prediction market signals with Kelly sizing, economic snapshots, web extraction utilities. Pay-per-call $0.001-$50 USDC via x402 on Base L2. `https://hydra-api-nlnj.onrender.com/mcp`
```

### Requirements
- Fork repo, create branch `add-hydra-server`
- Edit `README.md`, place alphabetically in the chosen section
- Badges: `🐍` (Python), `☁️` (Cloud/remote)
- Include the MCP server URL for direct connection
- PR title: `Add HYDRA regulatory intelligence server`
- Tip: add `🤖🤖🤖` to PR title for fast-tracked review

### PR Description

```
Adds HYDRA, an autonomous regulatory intelligence MCP server with 55+ tools.

- 13 real-time data sources (SEC EDGAR, CFTC, FinCEN, OCC, CFPB, Fed, Treasury, FDIC, BLS, FRED, Kalshi, Federal Register, Congress)
- Streamable HTTP transport at https://hydra-api-nlnj.onrender.com/mcp
- x402 USDC micropayments on Base L2 ($0.001 - $50.00 per call)
- Tools include: regulatory scans, FOMC rate signals, prediction market alpha reports, economic snapshots, web extraction, format conversion, developer utilities
- MCP manifest: https://hydra-api-nlnj.onrender.com/.well-known/mcp.json
- OpenAPI docs: https://hydra-api-nlnj.onrender.com/docs
```

---

## 2. wong2/awesome-mcp-servers

**Repo:** https://github.com/wong2/awesome-mcp-servers
**Stars:** Major MCP directory (high star count)
**Format:** Bold linked name + dash + description
**Category:** Place in "Community Servers" section, alphabetically

### Entry

```markdown
- **[HYDRA](https://github.com/OGCryptoKitty/hydra-arm3)** - Autonomous regulatory intelligence API with 55+ MCP tools. Real-time feeds from 13 government sources (SEC, CFTC, FinCEN, Fed, FDIC, FRED, Treasury). FOMC rate probabilities calibrated against Kalshi KXFED, prediction market alpha reports with Kelly sizing, economic snapshots, web extraction. x402 USDC payments on Base L2.
```

### Requirements
- Follow existing format: `**[Name](URL)** - Description`
- Place alphabetically in Community Servers
- PR title: `Add HYDRA regulatory intelligence server`

---

## 3. jaw9c/awesome-remote-mcp-servers

**Repo:** https://github.com/jaw9c/awesome-remote-mcp-servers
**Stars:** Curated list specifically for remote/hosted MCP servers
**Format:** Table row with columns: Name | Category | URL | Authentication | Maintainer

### Entry

```markdown
| HYDRA | Regulatory Intelligence | `https://hydra-api-nlnj.onrender.com/mcp` | x402 (USDC payment) | [OGCryptoKitty](https://github.com/OGCryptoKitty) |
```

### Requirements
- Remote MCP server with a public URL (HYDRA qualifies: streamable HTTP at /mcp)
- Must specify authentication method
- Note: This list prefers OAuth 2.0 per MCP spec. HYDRA uses x402 payment-based access, which is different. Include a note in the PR explaining x402 as a payment-gated auth model. Acceptance is not guaranteed.
- PR title: `Add HYDRA regulatory intelligence server`

---

## 4. xpaysh/awesome-x402

**Repo:** https://github.com/xpaysh/awesome-x402
**Stars:** Primary x402 ecosystem directory
**Format:** `[Name](URL) - Description with pricing and chain details`
**Category:** Place in "Production Implementations" or "Ecosystem Projects" section

### Entry

```markdown
- [HYDRA](https://hydra-api-nlnj.onrender.com) - Autonomous regulatory intelligence API with 55+ x402-paid endpoints. Real-time data from 13 government/market sources (SEC EDGAR, CFTC, FinCEN, Fed, FDIC, FRED, Treasury, Kalshi). FOMC rate probabilities, prediction market alpha with Kelly sizing, economic snapshots, web extraction, developer utilities. $0.001-$50.00 USDC per call on Base L2. MCP server included. ([GitHub](https://github.com/OGCryptoKitty/hydra-arm3)) ([x402 Manifest](https://hydra-api-nlnj.onrender.com/.well-known/x402.json)) ([Docs](https://hydra-api-nlnj.onrender.com/docs))
```

### Requirements
- "Add high-signal links: specifications, reference implementations, deep-dive posts, audits, and example apps"
- "Prefer primary sources and canonical specifications"
- "Submit a PR with a concise description; group items under existing sections when possible"
- Include chain (Base), token (USDC), and pricing info
- PR title: `Add HYDRA -- 55+ endpoint regulatory intelligence API on Base L2`

### PR Description

```
Adds HYDRA to Production Implementations.

HYDRA is an autonomous regulatory intelligence API with 55+ x402-paid endpoints on Base L2.
- Payment: USDC via x402 protocol, $0.001-$50.00 per call
- Chain: Base (8453)
- 13 real-time government data sources
- Also serves as an MCP server with streamable HTTP transport
- x402 manifest: https://hydra-api-nlnj.onrender.com/.well-known/x402.json
- GitHub: https://github.com/OGCryptoKitty/hydra-arm3
```

---

## 5. Merit-Systems/awesome-x402

**Repo:** https://github.com/Merit-Systems/awesome-x402
**Stars:** Second x402 ecosystem directory
**Format:** `[Name](URL) - Description`
**Category:** Place in "Ecosystem" section

### Entry

```markdown
- [HYDRA](https://hydra-api-nlnj.onrender.com) - Regulatory intelligence API with 55+ x402-paid endpoints on Base L2. 13 real-time data sources, FOMC signals, prediction market alpha, economic snapshots. $0.001-$50 USDC per call.
```

### Requirements
- Simple format: linked name + description
- Include chain and pricing info
- PR title: `Add HYDRA regulatory intelligence API`

---

## 6. a6b8/awesome-x402-servers

**Repo:** https://github.com/a6b8/awesome-x402-servers
**Stars:** Dedicated list of x402-enabled servers
**Format:** Check repo for exact format (table or list)

### Entry

```markdown
- [HYDRA](https://hydra-api-nlnj.onrender.com) - Autonomous regulatory intelligence API. 55+ x402 endpoints, 13 real-time government data sources, FOMC rate signals, prediction market alpha, economic snapshots, web extraction. Base L2 / USDC, $0.001-$50.00 per call. ([GitHub](https://github.com/OGCryptoKitty/hydra-arm3))
```

### Requirements
- Must be a live x402 server (HYDRA qualifies)
- PR title: `Add HYDRA regulatory intelligence server`

---

## 7. public-apis/public-apis

**Repo:** https://github.com/public-apis/public-apis
**Stars:** 300k+ stars, largest API directory on GitHub
**Format:** Table row: `| API | Description | Auth | HTTPS | CORS |`
**Category:** Place in "Cryptocurrency" or "Finance" section (alphabetically)

### Entry (Cryptocurrency section)

```markdown
| [HYDRA](https://hydra-api-nlnj.onrender.com/docs) | Regulatory intelligence API with real-time SEC, Fed, FDIC data and prediction market signals | `apiKey` | Yes | Yes |
```

### Entry (Finance section -- alternative placement)

```markdown
| [HYDRA](https://hydra-api-nlnj.onrender.com/docs) | Real-time regulatory intelligence from 13 government sources with FOMC rate probabilities | `apiKey` | Yes | Yes |
```

### Requirements (STRICT)
- **Free tier required:** API must have "full, free access or at least a free tier." HYDRA has 12 free endpoints (/health, /status, /docs, /.well-known/*, etc.) which qualifies, but paid endpoints use x402. Note this in PR description. This may be borderline -- emphasize the free endpoints.
- Description must NOT exceed 100 characters (both entries above are under 100)
- Auth: Use `apiKey` (closest match to x402 payment proof header)
- HTTPS: Yes
- CORS: Verify and set to Yes, No, or Unknown
- One link per PR
- Alphabetical ordering within section
- PR title format: `Add HYDRA API`
- Commit message: `Add HYDRA to Cryptocurrency` or `Add HYDRA to Finance`
- Squash all commits before submitting
- Do NOT include "API" in the name column (use "HYDRA" not "HYDRA API")
- Link should point to documentation page

### Risk Assessment
**Medium risk of rejection.** public-apis historically prefers fully free APIs. HYDRA's free tier (health, status, docs, manifests) may satisfy the requirement, but the core product is paid. Frame the PR around the free endpoints and note that paid tiers exist.

---

## 8. aarora4/Awesome-Prediction-Market-Tools

**Repo:** https://github.com/aarora4/Awesome-Prediction-Market-Tools
**Stars:** Primary prediction market tools directory
**Format:** Bold linked name + em dash + italicized description
**Category:** Place in "APIs" section

### Entry

```markdown
**[HYDRA](https://hydra-api-nlnj.onrender.com)** -- *Regulatory intelligence API for prediction market traders. Scored signals with HYDRA probability vs market price, Kelly optimal sizing, edge analysis, and trade verdicts for Polymarket and Kalshi markets. FOMC rate probabilities calibrated against Kalshi KXFED contracts. 13 real-time government data sources. Pay-per-call via x402 USDC on Base L2.*
```

### Requirements
- "Pull requests welcome -- add your tool or improve the list!"
- No strict formatting rules beyond matching existing style
- PR title: `Add HYDRA regulatory intelligence API`

### PR Description

```
Adds HYDRA to the APIs section.

HYDRA is a regulatory intelligence API purpose-built for prediction market traders:
- Scored market signals with HYDRA regulatory probability vs market price
- Kelly optimal sizing and edge analysis for Polymarket/Kalshi markets
- FOMC rate probability model calibrated against Kalshi KXFED contract prices
- 13 real-time government data sources (SEC, CFTC, FinCEN, Fed, FDIC, FRED, Treasury, etc.)
- Pay-per-call: $0.10-$50.00 USDC via x402 on Base L2
- Live at https://hydra-api-nlnj.onrender.com
- Docs: https://hydra-api-nlnj.onrender.com/docs
```

---

## 9. 0xperp/awesome-prediction-markets

**Repo:** https://github.com/0xperp/awesome-prediction-markets
**Stars:** Prediction markets ecosystem directory
**Format:** `[Name](URL) - Description` or nested list with details
**Category:** Place in "Repositories" or "Cool Websites" section

### Entry

```markdown
- [HYDRA](https://hydra-api-nlnj.onrender.com) - Regulatory intelligence API for prediction markets. Scored signals, FOMC rate probabilities (Kalshi KXFED calibrated), alpha reports with Kelly sizing. 13 government data sources, x402 USDC payments on Base.
```

### Requirements
- Simple format, no strict rules
- PR title: `Add HYDRA regulatory intelligence API`

---

## 10. awesomelistsio/awesome-defi

**Repo:** https://github.com/awesomelistsio/awesome-defi
**Stars:** Curated DeFi resources directory
**Format:** `**[Name](URL)** - Description`
**Category:** Place in "Analytics and Data Tools" section

### Entry

```markdown
- **[HYDRA](https://hydra-api-nlnj.onrender.com)** - Autonomous regulatory intelligence API delivering real-time data from 13 government sources (SEC, CFTC, Fed, FDIC, Treasury). FOMC rate probability models, prediction market signals, compliance risk scoring. 55+ endpoints paid via x402 USDC micropayments on Base L2. Compounds treasury via Aave V3 yield.
```

### Requirements
- Must be "well-maintained" with "clear documentation" (HYDRA has OpenAPI docs at /docs)
- No spam or self-promotion -- focus on utility value
- Follow alphabetical ordering
- Follow existing formatting in CONTRIBUTING.md
- PR title: `Add HYDRA regulatory intelligence API`

---

## 11. mjhea0/awesome-fastapi

**Repo:** https://github.com/mjhea0/awesome-fastapi
**Stars:** Primary FastAPI projects directory
**Format:** `[Name](URL) - Description`
**Category:** Place in "Open Source Projects" section

### Entry

```markdown
- [HYDRA](https://github.com/OGCryptoKitty/hydra-arm3) - Autonomous regulatory intelligence API with 55+ paid endpoints, MCP server, x402 payment middleware, and 13 real-time government data sources. Demonstrates FastAPI with background task automation, lifespan events, and middleware-based payment gating.
```

### Requirements
- Must be a real open-source FastAPI project (HYDRA is: FastAPI app in src/main.py, public GitHub repo)
- Place alphabetically in "Open Source Projects"
- No explicit CONTRIBUTING.md -- follow existing format
- PR title: `Add HYDRA`

---

## 12. ahmet/awesome-web3

**Repo:** https://github.com/ahmet/awesome-web3
**Stars:** Curated Web3 resources directory
**Format:** `[Name](URL) - Description`
**Category:** Place in "Open Source Project" section or potentially "AI & LLM & MCP"

### Entry (for "AI & LLM & MCP" section)

```markdown
- [HYDRA](https://github.com/OGCryptoKitty/hydra-arm3) - Autonomous regulatory intelligence API and MCP server with 55+ x402-paid endpoints on Base L2. Real-time data from 13 government sources, FOMC rate signals, prediction market alpha, Aave V3 treasury yield.
```

### Entry (for "Open Source Project" section)

```markdown
- [HYDRA](https://github.com/OGCryptoKitty/hydra-arm3) - Pay-per-call regulatory intelligence API on Base L2. 55+ endpoints paid via x402 USDC micropayments, MCP server for AI agents, Aave V3 yield compounding.
```

### Requirements
- One link per PR
- Follow alphabetical ordering
- Squash commits
- PR title format: `Add HYDRA` (omit "Awesome" prefix)
- Must follow Code of Conduct

---

## Summary Table

| # | Awesome List | Repo | Format | HYDRA Category | Acceptance Likelihood |
|---|---|---|---|---|---|
| 1 | awesome-mcp-servers (punkpeye) | [Link](https://github.com/punkpeye/awesome-mcp-servers) | List + badges | Data/Finance | High |
| 2 | awesome-mcp-servers (wong2) | [Link](https://github.com/wong2/awesome-mcp-servers) | Bold list | Community Servers | High |
| 3 | awesome-remote-mcp-servers | [Link](https://github.com/jaw9c/awesome-remote-mcp-servers) | Table row | Regulatory Intelligence | Medium (auth model) |
| 4 | awesome-x402 (xpaysh) | [Link](https://github.com/xpaysh/awesome-x402) | List + links | Production Implementations | High |
| 5 | awesome-x402 (Merit-Systems) | [Link](https://github.com/Merit-Systems/awesome-x402) | Simple list | Ecosystem | High |
| 6 | awesome-x402-servers | [Link](https://github.com/a6b8/awesome-x402-servers) | List | x402 Servers | High |
| 7 | public-apis | [Link](https://github.com/public-apis/public-apis) | Table row | Cryptocurrency / Finance | Medium (free tier rule) |
| 8 | Awesome-Prediction-Market-Tools | [Link](https://github.com/aarora4/Awesome-Prediction-Market-Tools) | Bold + italic | APIs | High |
| 9 | awesome-prediction-markets | [Link](https://github.com/0xperp/awesome-prediction-markets) | Simple list | Repositories | High |
| 10 | awesome-defi | [Link](https://github.com/awesomelistsio/awesome-defi) | Bold list | Analytics and Data Tools | High |
| 11 | awesome-fastapi | [Link](https://github.com/mjhea0/awesome-fastapi) | Simple list | Open Source Projects | High |
| 12 | awesome-web3 | [Link](https://github.com/ahmet/awesome-web3) | Simple list | AI & LLM & MCP | High |

---

## Submission Priority Order

Submit in this order for maximum distribution impact:

1. **awesome-x402 (xpaysh)** -- Exact target audience, HYDRA is a flagship x402 implementation
2. **awesome-mcp-servers (punkpeye)** -- Largest MCP directory, high visibility
3. **Awesome-Prediction-Market-Tools** -- Direct target audience (prediction market traders)
4. **awesome-mcp-servers (wong2)** -- Second major MCP directory
5. **awesome-x402 (Merit-Systems)** -- Second x402 directory
6. **awesome-x402-servers** -- Dedicated x402 server list
7. **awesome-remote-mcp-servers** -- Remote MCP servers specifically
8. **awesome-defi** -- DeFi ecosystem visibility
9. **awesome-web3** -- Broad Web3 developer audience
10. **awesome-fastapi** -- Python/FastAPI developer community
11. **awesome-prediction-markets** -- Additional prediction market visibility
12. **public-apis** -- Highest star count but strictest rules on free access

---

## PR Workflow Template

For each submission:

```bash
# 1. Fork the target repo on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/REPO_NAME.git
cd REPO_NAME

# 3. Create a branch
git checkout -b add-hydra

# 4. Edit README.md -- add the entry from above in the correct section (alphabetical)

# 5. Commit
git add README.md
git commit -m "Add HYDRA to [Section Name]"

# 6. Push
git push origin add-hydra

# 7. Open PR on GitHub with the title and description from the relevant section above
```
