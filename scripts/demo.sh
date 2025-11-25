#!/bin/bash
# Soulcaster Demo Script
# Demonstrates the full loop: Ingest -> Cluster -> Fix -> PR
#
# Prerequisites:
# - Backend running on localhost:8000
# - Dashboard running on localhost:3000
# - Redis configured and accessible
# - Environment variables set (see .env.example)

set -e

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:3000}"
FIXTURES_DIR="$(dirname "$0")/../fixtures"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_step() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

echo_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

echo_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if services are running
echo_step "Step 0: Checking services"

if ! curl -s "$BACKEND_URL/health" > /dev/null 2>&1; then
    if ! curl -s "$BACKEND_URL/clusters" > /dev/null 2>&1; then
        echo -e "${RED}Backend not responding at $BACKEND_URL${NC}"
        echo "Start it with: uvicorn backend.main:app --reload"
        exit 1
    fi
fi
echo_success "Backend is running at $BACKEND_URL"

# Step 1: Ingest sample feedback
echo_step "Step 1: Ingesting sample feedback"

echo_info "Sending Sentry webhook..."
curl -s -X POST "$BACKEND_URL/ingest/sentry" \
    -H "Content-Type: application/json" \
    -d @"$FIXTURES_DIR/sentry_webhook.json" | jq -r '.id // "OK"'

echo_info "Sending Reddit post..."
curl -s -X POST "$BACKEND_URL/ingest/reddit" \
    -H "Content-Type: application/json" \
    -d @"$FIXTURES_DIR/reddit_post.json" | jq -r '.id // "OK"'

echo_info "Sending manual feedback..."
curl -s -X POST "$BACKEND_URL/ingest/manual" \
    -H "Content-Type: application/json" \
    -d @"$FIXTURES_DIR/manual_feedback.json" | jq -r '.id // "OK"'

echo_success "All feedback ingested"

# Step 2: Check feedback count
echo_step "Step 2: Verifying feedback"

STATS=$(curl -s "$BACKEND_URL/stats")
TOTAL=$(echo "$STATS" | jq -r '.total_feedback')
echo_success "Total feedback items: $TOTAL"
echo "$STATS" | jq '.by_source'

# Step 3: Trigger clustering (via dashboard API)
echo_step "Step 3: Triggering clustering"

echo_info "Running vector-based clustering..."
CLUSTER_RESULT=$(curl -s -X POST "$DASHBOARD_URL/api/clusters/run-vector" \
    -H "Content-Type: application/json" \
    -d '{}' 2>/dev/null || echo '{"error": "Dashboard not available - cluster manually via UI"}')

if echo "$CLUSTER_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo_info "Note: Dashboard API not available. Visit $DASHBOARD_URL/clusters to trigger clustering via UI"
else
    echo "$CLUSTER_RESULT" | jq '.'
    echo_success "Clustering complete"
fi

# Step 4: List clusters
echo_step "Step 4: Viewing clusters"

CLUSTERS=$(curl -s "$BACKEND_URL/clusters")
CLUSTER_COUNT=$(echo "$CLUSTERS" | jq '. | length')
echo_success "Found $CLUSTER_COUNT cluster(s)"

if [ "$CLUSTER_COUNT" -gt 0 ]; then
    echo_info "Cluster summary:"
    echo "$CLUSTERS" | jq -r '.[] | "  - \(.title) (\(.count) items, status: \(.status))"'

    # Get first cluster ID for potential fix
    FIRST_CLUSTER_ID=$(echo "$CLUSTERS" | jq -r '.[0].id')
    echo ""
    echo_info "First cluster ID: $FIRST_CLUSTER_ID"
fi

# Step 5: Instructions for generating fix
echo_step "Step 5: Next steps"

echo "To generate a fix:"
echo "  1. Open $DASHBOARD_URL/clusters in your browser"
echo "  2. Click on a cluster to view details"
echo "  3. Click 'Generate Fix' to trigger the coding agent"
echo "  4. Wait for the PR to be created"
echo ""
echo "Or via API:"
echo "  curl -X POST $BACKEND_URL/clusters/{cluster_id}/start_fix"
echo ""

echo_step "Demo complete!"
echo "The full loop from feedback ingestion to PR creation is ready."
echo "Dashboard: $DASHBOARD_URL"
echo "Backend API: $BACKEND_URL/docs"
