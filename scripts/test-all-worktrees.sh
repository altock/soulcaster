#!/bin/bash
# Test all worktrees in parallel
# Usage: ./scripts/test-all-worktrees.sh

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🧪 Testing all worktrees in parallel..."
echo ""

# test_worktree runs backend and dashboard tests in the specified worktree and prefixes every output line with the provided worktree name.
# worktree_path is the filesystem path to the worktree where tests should be executed.
# worktree_name is a short label used to prefix and identify all printed output for this worktree.
test_worktree() {
    local worktree_path=$1
    local worktree_name=$2
    
    echo "[$worktree_name] Starting tests..."
    
    cd "$worktree_path"
    
    # Backend tests
    if [ -d "backend/tests" ]; then
        echo "[$worktree_name] Running backend tests..."
        python -m pytest backend/tests -q --tb=short 2>&1 | sed "s/^/[$worktree_name] /"
    fi
    
    # Dashboard tests
    if [ -d "dashboard/__tests__" ]; then
        echo "[$worktree_name] Running dashboard tests..."
        cd dashboard
        npm test -- --runInBand 2>&1 | sed "s/^/[$worktree_name] /"
        cd ..
    fi
    
    echo "[$worktree_name] ✅ Tests complete"
}

# Run tests in parallel using background processes
test_worktree "$REPO_ROOT/worktrees/billing-integration" "BILLING" &
BILLING_PID=$!

test_worktree "$REPO_ROOT/worktrees/system-readiness" "SYSTEM" &
SYSTEM_PID=$!

test_worktree "$REPO_ROOT/worktrees/onboarding-flow" "ONBOARDING" &
ONBOARDING_PID=$!

# Wait for all tests to complete
wait $BILLING_PID
BILLING_EXIT=$?

wait $SYSTEM_PID
SYSTEM_EXIT=$?

wait $ONBOARDING_PID
ONBOARDING_EXIT=$?

echo ""
echo "=========================================="
echo "Test Results:"
echo "  Billing Integration: $([ $BILLING_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "  System Readiness: $([ $SYSTEM_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "  Onboarding Flow: $([ $ONBOARDING_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "=========================================="

# Exit with failure if any tests failed
if [ $BILLING_EXIT -ne 0 ] || [ $SYSTEM_EXIT -ne 0 ] || [ $ONBOARDING_EXIT -ne 0 ]; then
    exit 1
fi

exit 0
