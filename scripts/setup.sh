#!/bin/bash
# ═══════════════════════════════════════════════════════════
# HYDRA Arm 3 — Post-Deploy Setup Script
# ═══════════════════════════════════════════════════════════
# Run this after deploying to Render. It will:
# 1. Verify the deployment is healthy
# 2. Connect your receiving wallet
# 3. Show all endpoint pricing
# 4. Test a free endpoint
# ═══════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════════"
echo " HYDRA Arm 3 — Post-Deploy Setup"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Get URL from user
if [ -z "$HYDRA_URL" ]; then
    read -p "Enter your Render URL (e.g., https://hydra-arm3.onrender.com): " HYDRA_URL
fi
# Strip trailing slash
HYDRA_URL="${HYDRA_URL%/}"

echo ""
echo "Step 1: Health Check..."
echo "─────────────────────────────────────────────────────────"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "$HYDRA_URL/health" 2>/dev/null)
if [ "$HEALTH" = "200" ]; then
    echo "✓ HYDRA is live at $HYDRA_URL"
    curl -s "$HYDRA_URL/health" | python3 -m json.tool 2>/dev/null || curl -s "$HYDRA_URL/health"
else
    echo "✗ Health check failed (HTTP $HEALTH). Is the service running?"
    echo "  Check Render dashboard for deployment logs."
    exit 1
fi

echo ""
echo "Step 2: Verify Pricing..."
echo "─────────────────────────────────────────────────────────"
curl -s "$HYDRA_URL/pricing" | python3 -m json.tool 2>/dev/null || curl -s "$HYDRA_URL/pricing"

echo ""
echo "Step 3: Test Free Discovery Endpoint..."
echo "─────────────────────────────────────────────────────────"
DISC=$(curl -s -o /dev/null -w "%{http_code}" "$HYDRA_URL/v1/markets/discovery" 2>/dev/null)
echo "Discovery endpoint: HTTP $DISC"

echo ""
echo "Step 4: Test Paid Endpoint (expect 402 Payment Required)..."
echo "─────────────────────────────────────────────────────────"
PAID=$(curl -s "$HYDRA_URL/v1/regulatory/scan" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"business_description": "crypto exchange"}' 2>/dev/null)
echo "$PAID" | python3 -m json.tool 2>/dev/null || echo "$PAID"

echo ""
echo "Step 5: Set Receiving Wallet..."
echo "─────────────────────────────────────────────────────────"
if [ -z "$RECEIVING_WALLET" ]; then
    read -p "Enter your receiving wallet address (0x...): " RECEIVING_WALLET
fi

if [ -n "$RECEIVING_WALLET" ]; then
    echo "Setting wallet to: $RECEIVING_WALLET"
    WALLET_RESULT=$(curl -s "$HYDRA_URL/system/wallet" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "{\"address\": \"$RECEIVING_WALLET\"}" 2>/dev/null)
    echo "$WALLET_RESULT" | python3 -m json.tool 2>/dev/null || echo "$WALLET_RESULT"
else
    echo "Skipped — no wallet provided."
    echo "Set later with: curl -X POST $HYDRA_URL/system/wallet -H 'Content-Type: application/json' -d '{\"address\": \"0xYOUR_WALLET\"}'"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo " HYDRA is ready to earn."
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Share these links:"
echo "  API Docs:    $HYDRA_URL/docs"
echo "  Discovery:   $HYDRA_URL/v1/markets/discovery"
echo "  Pricing:     $HYDRA_URL/v1/markets/pricing"
echo "  Health:      $HYDRA_URL/health"
echo ""
echo "Marketing announcements ready in marketing/ directory."
echo "Find-replace HYDRA_URL with: $HYDRA_URL"
echo ""
