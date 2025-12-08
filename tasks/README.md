# GitHub Integration & Test Data Tasks

This worktree is dedicated to GitHub integration, test data generation, and system testing.

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

## Related Worktrees

- **`system-readiness`** - Core system stability (ingestion, clustering, storage)
- **`billing-integration`** - Payment and subscription features
- **`onboarding-flow`** - User onboarding and setup

## Branch

This worktree tracks the `github-test-data` branch.
