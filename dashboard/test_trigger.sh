#!/bin/bash

# Default to a dummy URL if none provided
ISSUE_URL=${1:-"https://github.com/owner/repo/issues/123"}

echo "🚀 Triggering Agent for Issue: $ISSUE_URL"
echo "----------------------------------------"

curl -X POST http://localhost:3000/api/trigger-agent \
  -H "Content-Type: application/json" \
  -d "{\"issue_url\": \"$ISSUE_URL\"}"

echo "\n----------------------------------------"
echo "✅ Request sent."
