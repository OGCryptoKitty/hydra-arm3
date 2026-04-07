# HYDRA API — Community Registration & Distribution Guide

This document lists every place to register, post, or engage for HYDRA API discovery.
Each entry includes the URL, what to do, and a ready-to-use draft message.

---

## 1. x402 Directories & Discovery Platforms

The x402 discovery standard is emerging. Service manifests are hosted at
`/.well-known/x402.json` and indexed by AI agent frameworks.

| Target | URL | Action |
|--------|-----|--------|
| x402.org directory (if launched) | https://x402.org | Submit service manifest URL |
| Well-known crawlers | Auto-discovery | Ensure `/.well-known/x402.json` is live |
| AI agent frameworks (e.g. LangChain tools) | Various | Register as an x402-enabled tool |

**Draft submission (for any x402 registry):**
```
Name: HYDRA Regulatory Intelligence
URL: https://hydra-api-nlnj.onrender.com
Discovery: https://hydra-api-nlnj.onrender.com/.well-known/x402.json
Category: Financial Data / Regulatory Intelligence
Description: Real-time SEC, CFTC, Fed, and FinCEN monitoring translated into
prediction market signals. Oracle-ready resolution verdicts for UMA and Chainlink.
Pay-per-use with USDC on Base.
Free entry point: GET /v1/markets
```

---

## 2. Polymarket Community

### Polymarket Discord
- **URL:** https://discord.gg/polymarket (check official site for current invite)
- **Channels to post in:** #builders, #api-integrations, #market-discussion, #tools
- **Draft post:**

> **HYDRA — Free regulatory intelligence feed for Polymarket traders**
>
> I built an API that monitors SEC, CFTC, Fed, and FinCEN in real time and maps
> regulatory events to open Polymarket markets.
>
> **Free to start:**
> `GET https://hydra-api-nlnj.onrender.com/v1/markets`
> Returns active regulatory prediction markets across Polymarket. No auth, no payment.
>
> **Paid (USDC via x402):**
> - $2 — Scored signal for a specific market
> - $5 — Bulk signals across all regulatory markets
> - $10 — Alpha report with Kelly-sized trade verdict
> - $50 — FOMC resolution verdict for oracle submission
>
> Built for bots and automated strategies. Designed to work with the x402 payment
> protocol so your agent can discover, pay, and receive data in one loop.
>
> Docs: https://hydra-api-nlnj.onrender.com/docs

### Polymarket Builder Program
- **URL:** https://polymarket.com/builders (check official Polymarket site)
- **Action:** Apply as a data provider / infrastructure builder
- **Notes:** Frame HYDRA as complementary infrastructure — not a competing market creator

### Polymarket Developer Docs
- **URL:** https://docs.polymarket.com
- **Action:** Read their API, identify markets you can cover, reach out via official channels

---

## 3. Kalshi Community

### Kalshi Developer Forum / API Access
- **URL:** https://kalshi.com/developers (check official site)
- **Action:** Request API access, mention HYDRA as a data consumer and signal provider
- **Draft outreach:**

> Hi Kalshi team — I've built HYDRA, a regulatory intelligence API that generates
> scored signals for Kalshi markets. I'd love to discuss becoming an official data
> partner. HYDRA monitors SEC, CFTC, Fed, and FinCEN and produces oracle-ready
> resolution verdicts that could help with market settlement.
>
> API: https://hydra-api-nlnj.onrender.com/docs

### Kalshi Discord / Slack
- **URL:** Check https://kalshi.com for community links
- **Channels:** #traders, #api-discussion, #tools

---

## 4. Prediction Market Communities

### Metaculus
- **URL:** https://www.metaculus.com/questions/
- **Action:** Post in the community forum about regulatory data tools
- **Draft:**

> HYDRA is a regulatory intelligence API I built for prediction market traders.
> It monitors SEC, CFTC, Fed, and FinCEN and translates events into scored market signals.
> Free endpoint: `GET https://hydra-api-nlnj.onrender.com/v1/markets`
> Full docs: https://hydra-api-nlnj.onrender.com/docs

### Manifold Markets Discord
- **URL:** https://discord.gg/manifold (check official site)
- **Channels:** #developers, #market-data
- **Draft:** Same structure as Polymarket Discord post above, adapted for Manifold context

### Prediction Market Subreddits
See Section 8 below for Reddit posts.

---

## 5. DeFi & Oracle Communities

### UMA Protocol Discord
- **URL:** https://discord.umaproject.org (or via https://umaproject.org)
- **Channels:** #asserters, #developers, #integrations
- **What to share:** HYDRA's `/v1/oracle/uma` endpoint generates structured assertion
  data with evidence chains for UMA Optimistic Oracle submissions.
- **Draft post:**

> **HYDRA — Regulatory oracle data for UMA asserters**
>
> I built an API that generates UMA-ready assertion data for regulatory prediction markets.
> The `/v1/oracle/uma` endpoint returns:
> - Structured YES/NO/AMBIGUOUS verdict
> - Evidence chain with statutory citations and agency source links
> - Confidence score and dispute-resistant rationale
>
> Useful for anyone asserting on regulatory outcomes (SEC actions, FOMC decisions, etc.)
> Cost: $5 USDC per assertion (x402 on Base)
> FOMC resolution: $50 USDC (includes 30-second FOMC classification)
>
> Docs: https://hydra-api-nlnj.onrender.com/docs

### Chainlink Community
- **URL:** https://discord.gg/chainlink (check official site)
- **Channels:** #external-adapters, #node-operators, #developers
- **What to share:** HYDRA's `/v1/oracle/chainlink` endpoint returns data in standard
  External Adapter format — drop-in compatible with any Chainlink node.
- **Draft post:**

> **HYDRA — Regulatory data as a Chainlink External Adapter**
>
> HYDRA's `/v1/oracle/chainlink` endpoint returns regulatory resolution data in
> standard Chainlink External Adapter format. Point your node job spec at:
> `POST https://hydra-api-nlnj.onrender.com/v1/oracle/chainlink`
>
> Covers: SEC actions, CFTC enforcement, FOMC decisions, FinCEN notices.
> Cost: $5 USDC per call (x402 on Base)
>
> Docs: https://hydra-api-nlnj.onrender.com/docs

### API3 Discord
- **URL:** https://discord.gg/api3 (check official site)
- **Channels:** #data-providers, #integrations
- **Draft:** Similar to Chainlink post above; emphasize the structured data format

---

## 6. Crypto Developer Communities

### Base Ecosystem — Coinbase Developer Platform
- **URL:** https://docs.base.org / https://discord.gg/buildonbase
- **Action:** Register HYDRA as a Base-native service in the ecosystem directory
- **Channels:** #builders, #dapps, #showcase
- **Draft:**

> **HYDRA — Regulatory intelligence API native to Base**
>
> HYDRA uses x402 (HTTP 402 Payment Required) with USDC on Base for all payments.
> Zero subscriptions, zero API keys — just on-chain micropayments on Base.
>
> Free endpoint to try: `GET https://hydra-api-nlnj.onrender.com/v1/markets`
>
> Payment wallet: 0x2F12A73e1e08F3BCE12212005cCaBE2ACEf87141
> Network: Base (chain 8453)
> Token: USDC (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)

### Ethereum Developer Forums / ETH Research
- **URL:** https://ethresear.ch / https://ethereum-magicians.org
- **Action:** Post in relevant threads about x402 payment protocol adoption

### Developer DAO
- **URL:** https://discord.gg/devdao
- **Channels:** #build, #projects, #showcase

---

## 7. AI Agent Communities

### x402 Protocol Community
- **URL:** Check https://x402.org or GitHub for x402 spec discussions
- **Action:** Register HYDRA in any x402-capable service registry; contribute to spec discussions

### LangChain / LlamaIndex Integrations
- **URL:** https://python.langchain.com / https://www.llamaindex.ai
- **Action:** Consider building a LangChain tool or LlamaIndex reader that wraps HYDRA endpoints.
  Post in #integrations on their Discord communities.
- **Pitch:** "HYDRA is an x402-enabled API that gives LLM agents access to real-time
  regulatory intelligence. The agent can discover, pay (USDC on Base), and receive
  structured regulatory data autonomously."

### AutoGPT / Open-source agent communities
- **URL:** https://discord.gg/autogpt
- **Action:** Post in #plugins or #tools channels; HYDRA's x402 manifest makes it
  auto-discoverable for agents that support the protocol.

### Conway Automaton Ecosystem
- **Action:** Register as a compatible x402 service in any Conway-compatible registry.
  Ensure `/.well-known/x402.json` is accurate and up to date.

---

## 8. Reddit

### r/Polymarket
- **URL:** https://reddit.com/r/Polymarket
- **Draft post (title):** "Free regulatory feed for Polymarket traders — HYDRA API"
- **Draft body:**

> I built HYDRA, a regulatory intelligence API that monitors SEC, CFTC, Fed, and FinCEN
> and maps events to open Polymarket markets.
>
> **Free to use:**
> ```
> curl https://hydra-api-nlnj.onrender.com/v1/markets
> ```
> Returns active regulatory prediction markets. No auth required.
>
> **Paid tiers (USDC via x402 on Base):**
> - $2 — Scored signal for a specific market
> - $10 — Alpha report with Kelly Criterion sizing
> - $50 — FOMC oracle resolution verdict
>
> Built for bots. Full docs: https://hydra-api-nlnj.onrender.com/docs

### r/Kalshi
- **URL:** https://reddit.com/r/Kalshi
- **Draft post title:** "API for regulatory signals mapped to Kalshi markets"
- **Draft:** Same as above, adapted to mention Kalshi

### r/defi
- **URL:** https://reddit.com/r/defi
- **Draft post title:** "HYDRA — pay-as-you-go regulatory data API using x402 (USDC on Base)"
- **Draft body:**

> HYDRA is a regulatory intelligence API that uses the x402 HTTP payment protocol
> to accept USDC on Base for each API call — no subscriptions, no API keys.
>
> The use case: prediction market traders and oracle operators who need real-time
> SEC, CFTC, Fed, and FinCEN data to trade and resolve markets.
>
> Discovery manifest: https://hydra-api-nlnj.onrender.com/.well-known/x402.json
> Docs: https://hydra-api-nlnj.onrender.com/docs

### r/algotrading
- **URL:** https://reddit.com/r/algotrading
- **Draft post title:** "Regulatory event data API for prediction market bots — pay per call"
- **Draft body:**

> I've built an API that turns raw SEC, CFTC, Fed, and FinCEN events into structured
> trading signals for Polymarket and Kalshi. Designed for bots, not dashboards.
>
> Signal output includes: numeric score, directional bias, confidence interval, rationale.
> FOMC decision classification within 30 seconds of release.
>
> Pay per call with USDC on Base using the x402 protocol — your bot can autonomously
> discover pricing, pay, and receive data in one loop.
>
> Docs: https://hydra-api-nlnj.onrender.com/docs

### r/CryptoCurrency
- **URL:** https://reddit.com/r/CryptoCurrency
- **Draft post title:** "Built a regulatory intelligence API for crypto prediction markets (x402 + USDC on Base)"
- **Draft:** Brief version of the DeFi post above

---

## 9. Twitter/X Accounts to Engage

### Prediction Market Influencers & Accounts
| Account | Focus | Engagement approach |
|---------|-------|---------------------|
| @Polymarket | Official account | Tag in posts about regulatory market activity |
| @KalshiHQ | Official Kalshi | Tag in posts about FOMC/regulatory markets |
| @manifoldmarkets | Manifold | Tag when relevant markets are active |
| @metaculus | Metaculus | Tag in regulatory forecasting discussions |
| @elilifland | Superforecaster | Engage on regulatory outcomes |
| @pphilosopher | Prediction markets | Engage on data/signals discussion |

### DeFi / Oracle Data Accounts
| Account | Focus | Engagement approach |
|---------|-------|---------------------|
| @UMAprotocol | UMA Oracle | Tag in posts about regulatory oracle use cases |
| @chainlink | Chainlink | Tag in posts about external adapter data sources |
| @APIThreeDotOrg | API3 | Engage on data provider discussions |
| @BuildOnBase | Base ecosystem | Post about x402 + USDC on Base |

### Regulatory & Policy Commentators
| Account | Focus | Engagement approach |
|---------|-------|---------------------|
| @coincenter | Crypto policy | Engage on regulatory impact analysis |
| @cliffynotes | Crypto regulation | Add HYDRA context to regulatory threads |
| @secgov | SEC official | Monitor for events; create timely posts |

**General Twitter strategy:**
- Post when major regulatory events break (enforcement actions, rule proposals)
- Use template: "🏛️ [AGENCY] [EVENT]: [summary] | Prediction market signal available via HYDRA: [link] | #Polymarket #Kalshi"
- Run the twitter_bot.py script after major regulatory events
- Engage genuinely on regulatory threads before dropping links

---

## 10. Product Hunt & Hacker News

### Product Hunt
- **URL:** https://producthunt.com/posts/new
- **Suggested tagline:** "Real-time regulatory intelligence for prediction markets — pay per call"
- **Draft description:**

> HYDRA is a regulatory intelligence API built for prediction market traders and oracle operators.
>
> It monitors SEC, CFTC, Federal Reserve, and FinCEN in real time and translates regulatory events
> into actionable signals for Polymarket and Kalshi markets.
>
> **What makes it different:**
> • Pay-per-call with USDC on Base — no subscriptions, no API keys
> • x402 protocol: AI agents can discover, pay, and receive data autonomously
> • Oracle-ready output for UMA Optimistic Oracle and Chainlink External Adapters
> • FOMC decision classification within 30 seconds of release ($25/call)
>
> **Free to start:** `GET /v1/markets` returns active regulatory prediction markets — no payment required.
>
> Docs: https://hydra-api-nlnj.onrender.com/docs
>
> **Topics to select:** API, FinTech, Crypto, Prediction Markets, AI

### Hacker News (Show HN)
- **URL:** https://news.ycombinator.com/submit
- **Title:** "Show HN: HYDRA – Regulatory intelligence API for prediction markets (x402, USDC on Base)"
- **Draft text (for comment thread):**

> HYDRA is an API I built that monitors SEC, CFTC, Fed, and FinCEN RSS feeds and generates
> scored signals for Polymarket and Kalshi prediction markets.
>
> The interesting technical angle: it uses the x402 HTTP payment protocol. When you call
> a paid endpoint, you get a 402 response with payment details (USDC amount, wallet address
> on Base). Pay the USDC, include the tx hash in X-Payment-Proof, resend — you get the data.
> No API keys, no accounts, no subscription state.
>
> This makes it well-suited for AI agents and trading bots that can autonomously discover
> pricing and pay for data in a single loop. There's a discovery manifest at
> /.well-known/x402.json that follows the emerging x402 discovery spec.
>
> Free endpoint to try: https://hydra-api-nlnj.onrender.com/v1/markets
> Full docs: https://hydra-api-nlnj.onrender.com/docs
>
> Happy to answer questions about the x402 implementation or the prediction market signal design.

---

## General Posting Guidelines

1. **Lead with the free endpoint.** `GET /v1/markets` is the genuine value entry point.
   Never lead with a paid endpoint — let people discover value first.

2. **Be specific about the use case.** "Regulatory signals for prediction markets" is
   more compelling than "financial data API". Name Polymarket and Kalshi explicitly.

3. **Explain x402 briefly.** Most developers haven't heard of x402. One sentence:
   "Call the endpoint, get a 402 with payment details, pay USDC on Base, resend."

4. **Don't spam.** One post per community is the right cadence. Follow up only when
   you have a meaningful update (new endpoint, major regulatory event, integration).

5. **Engage before you post.** In Discord communities especially, spend a few days
   being genuinely helpful in conversations before posting about HYDRA.

6. **Timing matters.** Post within minutes of major regulatory events (FOMC decisions,
   SEC enforcement, FinCEN notices). That's when demand for this data is highest.
