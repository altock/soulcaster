#!/bin/bash
# Create GitHub issues for Soulcaster test repository
# Usage: ./scripts/create_github_issues.sh <repo_url> <github_token>

set -e

REPO_URL=$1
GITHUB_TOKEN=$2

if [ -z "$REPO_URL" ] || [ -z "$GITHUB_TOKEN" ]; then
    echo "Usage: $0 <repo_url> <github_token>"
    echo "Example: $0 https://github.com/username/test-repo ghp_xxxxx"
    exit 1
fi

echo "🚀 Generating test data for Soulcaster..."
echo "Repository: $REPO_URL"
echo ""

# Run enhanced generator
python3 scripts/generate_enhanced_test_data.py "$REPO_URL" "$GITHUB_TOKEN" --modules all

echo ""
echo "✅ Test data generation complete!"
echo ""
echo "Next steps:"
echo "1. Visit $REPO_URL/issues to see the generated issues"
echo "2. Run Soulcaster ingestion: curl -X POST http://localhost:8000/ingest/github/repo/..."
echo "3. Check clustering: curl http://localhost:8000/api/clusters"
