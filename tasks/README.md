# Soulcaster Tasks & Documentation

This directory contains task plans, implementation roadmaps, and testing strategies for the Soulcaster project.

## Task Documents

- **`github_integration_plan.md`** - Complete plan for GitHub issue ingestion, API integration, polling, and webhooks
- **`testing_validation_plan.md`** - Comprehensive testing strategy including unit tests, integration tests, load tests, and quality gates
- **`PHASE2_CLUSTERING_CHECKLIST.md`** - Day-by-day checklist for implementing the clustering pipeline with embeddings

## Scripts

See `scripts/` directory:
- **`generate_enhanced_test_data.py`** - Generate realistic GitHub repos with intentional bugs and clustered issues
- **`create_github_issues.sh`** - Bash wrapper for easy test data generation

## Usage

### Generate Test Data
```bash
# Create a test repository with bugs and issues
python scripts/generate_enhanced_test_data.py https://github.com/username/test-repo $GITHUB_TOKEN --modules all

# Or use the shell wrapper
./scripts/create_github_issues.sh https://github.com/username/test-repo $GITHUB_TOKEN
```

### Run Tests
```bash
# Backend tests
cd backend && pytest tests -v --cov=backend

# Dashboard tests
cd dashboard && npm run test
```

## Status

The core system is now operational with:
- ✅ Multi-source feedback ingestion (Reddit, GitHub, Sentry, manual)
- ✅ AI-powered clustering with embeddings
- ✅ Multi-tenant projects and users
- ✅ Job tracking for agent fixes
- ✅ Dashboard with authentication
- ✅ Coding agent (local and Fargate deployment)

See individual task documents for implementation details and completion status.
