# Soulcaster Development Commands
# Run 'just' to see all available commands

# Default recipe - show help
default:
    @just --list

# ============================================================================
# Development
# ============================================================================

# Run FastAPI backend (localhost:8000)
dev-backend:
    @echo "🚀 Starting FastAPI backend on http://localhost:8000"
    cd backend && uv run uvicorn main:app --reload --port 8000

# Run Next.js dashboard (localhost:3000)
dev-dashboard:
    @echo "🚀 Starting Next.js dashboard on http://localhost:3000"
    cd dashboard && npm run dev

# Reset all DEV data (Redis + Vector)
dev-reset:
    @echo "🗑️  Resetting DEV data..."
    python scripts/reset_dev_data.py

# Reset DEV data without confirmation
dev-reset-force:
    @echo "🗑️  Force resetting DEV data (no confirmation)..."
    python scripts/reset_dev_data.py --force

# ============================================================================
# Production
# ============================================================================

# Check production backend health
prod-health:
    #!/usr/bin/env bash
    if [ -z "$PROD_BACKEND_URL" ]; then
        echo "❌ PROD_BACKEND_URL not set"
        exit 1
    fi
    echo "🏥 Checking production backend health..."
    curl -sf $PROD_BACKEND_URL/health | jq '.' || echo "❌ Health check failed"

# Deploy backend to Sevalla (manual reminder)
prod-deploy-backend:
    @echo "🚀 Deploying backend to Sevalla..."
    @echo "⚠️  Manual step required:"
    @echo "   1. Push to 'main' branch"
    @echo "   2. Sevalla will auto-deploy"

# Deploy dashboard to Vercel
prod-deploy-dashboard:
    @echo "🚀 Deploying dashboard to Vercel..."
    cd dashboard && vercel --prod

# ============================================================================
# Testing & Quality
# ============================================================================

# Run all tests
test: test-backend test-dashboard

# Run backend tests
test-backend:
    @echo "🧪 Running backend tests..."
    cd backend && uv run pytest -v

# Run dashboard tests
test-dashboard:
    @echo "🧪 Running dashboard tests..."
    cd dashboard && npm test

# Run linters
lint:
    @echo "🔍 Linting code..."
    @echo "Backend:"
    cd backend && uv run ruff check .
    @echo "\nDashboard:"
    cd dashboard && npm run lint

# Format code
format:
    @echo "✨ Formatting code..."
    @echo "Backend:"
    cd backend && uv run black .
    cd backend && uv run ruff check --fix .
    @echo "\nDashboard:"
    cd dashboard && npm run format

# ============================================================================
# Installation
# ============================================================================

# Install backend dependencies with uv
install-backend:
    @echo "📦 Installing backend dependencies with uv..."
    cd backend && uv sync

# Install dashboard dependencies
install-dashboard:
    @echo "📦 Installing dashboard dependencies..."
    cd dashboard && npm install
    cd dashboard && npx prisma generate

# Install all dependencies
install: install-backend install-dashboard
    @echo "✅ All dependencies installed!"

# ============================================================================
# Database
# ============================================================================

# Run Prisma migrations
db-migrate:
    @echo "🗄️  Running Prisma migrations..."
    cd dashboard && npx prisma migrate dev

# Reset Prisma database (DEV only!)
db-reset:
    @echo "🗄️  Resetting Prisma database..."
    cd dashboard && npx prisma migrate reset

# Open Prisma Studio
db-studio:
    @echo "🗄️  Opening Prisma Studio..."
    cd dashboard && npx prisma studio

# ============================================================================
# Utilities
# ============================================================================

# Check environment configuration
check-env:
    #!/usr/bin/env bash
    echo "🔍 Checking environment configuration..."
    echo "Backend .env:"
    if [ -f backend/.env ]; then echo "✅ Found"; else echo "❌ Missing"; fi
    echo "Dashboard .env.local:"
    if [ -f dashboard/.env.local ]; then echo "✅ Found"; else echo "❌ Missing"; fi

# Tail local backend logs
logs-backend-dev:
    @echo "📋 Tailing local backend logs..."
    tail -f backend/logs/*.log 2>/dev/null || echo "No log files found"

# Clean build artifacts
clean:
    @echo "🧹 Cleaning build artifacts..."
    rm -rf backend/__pycache__ backend/**/__pycache__
    rm -rf dashboard/.next dashboard/node_modules/.cache
    @echo "✅ Clean complete"

# ============================================================================
# Git & Worktree
# ============================================================================

# Show current worktree info
worktree-info:
    @echo "📂 Worktree Information:"
    @git worktree list
    @echo ""
    @echo "Current branch:"
    @git branch --show-current
    @echo ""
    @echo "Status:"
    @git status -s

# Create a new worktree for a feature
worktree-create BRANCH:
    @echo "🌳 Creating worktree for {{BRANCH}}..."
    git worktree add ../soulcaster-{{BRANCH}} -b {{BRANCH}}
    @echo "✅ Created at ../soulcaster-{{BRANCH}}"

# Remove a worktree
worktree-remove PATH:
    @echo "🗑️  Removing worktree at {{PATH}}..."
    git worktree remove {{PATH}}
