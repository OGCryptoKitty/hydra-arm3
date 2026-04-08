# Reddit r/algotrading Announcement

Replace `https://hydra-api-nlnj.onrender.com` with your Render deployment URL before posting.

---

**Title: Open-sourced a regulatory intelligence API for prediction market bots — AI signal scoring, pay-per-call in USDC**

I've been building automated trading strategies for prediction markets (Polymarket, Kalshi) and the biggest alpha I found is in regulatory events — SEC actions, FOMC decisions, crypto legislation votes. These events drive massive volume in prediction markets, and the bots that react first capture the edge.

**The problem:** Monitoring 6+ federal agencies, parsing legalese, and scoring impact on specific markets is a full-time job. Most bots just react to price movement, which means they're late.

**What I built:**
HYDRA is a REST API that:
1. Monitors SEC EDGAR, CFTC, FinCEN, OCC, CFPB, Fed RSS in real-time
2. Uses Claude (Anthropic's AI) to analyze each event against active prediction markets
3. Returns structured signals: direction (BULLISH_YES/NO/NEUTRAL), confidence (0-100), key factors, risk assessment
4. For oracle markets (UMA): generates formatted resolution verdicts

**Technical details for the algo crowd:**
- x402 payment protocol — USDC micropayments on Base L2 per API call
- No auth needed for free endpoints, no signup
- Sub-second response times for cached data, 2-5s for fresh AI analysis
- Webhook system for push notifications on regulatory events (HMAC-SHA256 signed)
- Prometheus metrics endpoint for monitoring your spend
- Subscription API keys for volume discounts (10-30% off)

**Pricing:**
- Event feed: $0.25/call (designed for 5-min polling)
- Classified events: $1.50/call
- Single market signal: $5.00/call
- Bulk signals: $15.00/call
- Alpha report (edge calc, Kelly sizing): $30.00/call
- Resolution verdict: $50.00/call

**Stack:** Python/FastAPI, Claude API for analysis, live data from NY Fed + Treasury.gov + Fed RSS, on-chain payment verification via Base RPC.

**Economics:**
- AI cost per call: ~$0.002 (Haiku)
- Revenue per call: $0.25 - $50
- Margin: 99%+
- For users: if you trade $50K/month on regulatory markets, a 1% informational edge = $500/month

**Code is open source.** API docs at `https://hydra-api-nlnj.onrender.com/docs`. Free discovery endpoint at `https://hydra-api-nlnj.onrender.com/v1/markets/discovery`.

Curious what this community thinks about the pricing model and whether regulatory intelligence is something your strategies would use.
