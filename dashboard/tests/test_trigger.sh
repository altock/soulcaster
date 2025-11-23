#!/bin/bash

# Usage:
# ./test_trigger.sh [issue_url]
# OR
# ./test_trigger.sh context "Fix this bug please" "Bug Title" [owner] [repo]

if [ "$1" == "context" ]; then
    CONTEXT=${2:-"This is a test context for automatic issue creation."}
    TITLE=${3:-"Test Issue from Script"}
    OWNER=${4:-"naga-k"}
    REPO=${5:-"soulcaster"}
    
    echo "🚀 Triggering Agent with Context: '$CONTEXT'"
    echo "   Repo: $OWNER/$REPO"
    echo "----------------------------------------"
    
    curl -X POST http://localhost:3000/api/trigger-agent \
      -H "Content-Type: application/json" \
      -d "{\"context\": \"$CONTEXT\", \"issue_title\": \"$TITLE\", \"owner\": \"$OWNER\", \"repo\": \"$REPO\"}"

else
    # Default to a dummy URL if none provided
    ISSUE_URL=${1:-"https://github.com/owner/repo/issues/123"}

    echo "🚀 Triggering Agent for Issue: $ISSUE_URL"
    echo "----------------------------------------"

    curl -X POST http://localhost:3000/api/trigger-agent \
      -H "Content-Type: application/json" \
      -d "{\"issue_url\": \"$ISSUE_URL\"}"
fi

echo "\n----------------------------------------"
echo "✅ Request sent."
