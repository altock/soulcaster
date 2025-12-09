#!/bin/bash
# Run servers in all worktrees on different ports
# Usage: ./scripts/run-all-servers.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 Starting servers in all worktrees..."
echo ""
echo "Servers will run on:"
echo "  Main - Backend: 8000, Dashboard: 3000"
echo "  Billing - Backend: 8001, Dashboard: 3001"  
echo "  System - Backend: 8002, Dashboard: 3002"
echo "  Onboarding - Backend: 8003, Dashboard: 3003"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Function to start servers in a worktree
start_worktree_servers() {
    local worktree_path=$1
    local worktree_name=$2
    local backend_port=$3
    local dashboard_port=$4
    
    echo "[$worktree_name] Starting on ports $backend_port (backend) and $dashboard_port (dashboard)..."
    
    # Start backend (fail fast if path is wrong)
    cd "$worktree_path/backend" || {
        echo "[$worktree_name-setup] Failed to cd into $worktree_path/backend"
        exit 1
    }
    PORT=$backend_port uvicorn main:app --reload --port $backend_port 2>&1 | sed "s/^/[$worktree_name-BE] /" &
    
    # Start dashboard (fail fast if path is wrong)
    cd "$worktree_path/dashboard" || {
        echo "[$worktree_name-setup] Failed to cd into $worktree_path/dashboard"
        exit 1
    }
    PORT=$dashboard_port NEXT_PUBLIC_API_URL="http://localhost:$backend_port" npm run dev -- --port $dashboard_port 2>&1 | sed "s/^/[$worktree_name-FE] /" &
}

# Start servers in each worktree
start_worktree_servers "$REPO_ROOT/worktrees/billing-integration" "BILLING" 8001 3001
start_worktree_servers "$REPO_ROOT/worktrees/system-readiness" "SYSTEM" 8002 3002
start_worktree_servers "$REPO_ROOT/worktrees/onboarding-flow" "ONBOARDING" 8003 3003

# Also start main if desired
# start_worktree_servers "$REPO_ROOT" "MAIN" 8000 3000

# Wait for Ctrl+C
trap 'echo "Stopping all servers..."; kill $(jobs -p); exit 0' INT TERM

# Keep script running
wait

