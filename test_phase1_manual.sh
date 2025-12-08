#!/bin/bash
# Manual test script for Phase 1 - feedback:unclustered functionality

echo "🧪 Phase 1 Manual Testing Script"
echo "================================="
echo ""

BACKEND_URL="http://localhost:8002"

echo "📝 Instructions:"
echo "1. In another terminal, start the backend:"
echo "   cd worktrees/system-readiness/backend"
echo "   uvicorn main:app --reload --port 8002"
echo ""
echo "2. Press Enter when ready to test..."
read

echo ""
echo "🔄 Test 1: Ingest Reddit feedback"
echo "-----------------------------------"
curl -X POST "$BACKEND_URL/ingest/reddit" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-001",
    "source": "reddit",
    "external_id": "t3_test001",
    "title": "Test bug from manual script",
    "body": "This is a test to verify unclustered tracking",
    "metadata": {"subreddit": "testing"},
    "created_at": "2024-12-08T10:00:00Z"
  }' | jq '.'

echo ""
echo ""
echo "🔄 Test 2: Ingest Manual feedback"
echo "-----------------------------------"
curl -X POST "$BACKEND_URL/ingest/manual" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Manual test feedback for Phase 1"
  }' | jq '.'

echo ""
echo ""
echo "🔄 Test 3: Ingest Sentry error"
echo "-----------------------------------"
curl -X POST "$BACKEND_URL/ingest/sentry" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "sentry_manual_test",
    "message": "Test error from manual script",
    "exception": {
      "values": [{
        "type": "TestError",
        "value": "This is a test exception"
      }]
    }
  }' | jq '.'

echo ""
echo ""
echo "📊 Test 4: Check all feedback items"
echo "-----------------------------------"
curl -X GET "$BACKEND_URL/feedback" | jq '.items | length'
echo "feedback items ingested"

echo ""
echo ""
echo "📊 Test 5: Check stats"
echo "-----------------------------------"
curl -X GET "$BACKEND_URL/stats" | jq '.'

echo ""
echo ""
echo "✅ Manual tests complete!"
echo ""
echo "🔍 To verify Redis keys (if using Redis):"
echo "   redis-cli"
echo "   > SMEMBERS feedback:unclustered"
echo "   > HGETALL feedback:test-001"
echo ""

