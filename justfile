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
# Docker (Local Testing Only - Production uses hosting platform)
# ============================================================================

# Build backend Docker image (local testing)
docker-build:
    @echo "🐳 Building backend Docker image (local test)..."
    @echo "ℹ️  Production builds happen automatically on hosting platform"
    cd backend && docker build -t soulcaster-backend .

# Run backend in Docker with unified .env (local test)
docker-run:
    @echo "🐳 Running backend in Docker on http://localhost:8000"
    @echo "Loading env vars from .env"
    docker run -p 8000:8000 --env-file .env soulcaster-backend

# Build and run with Docker Compose (includes Redis + unified .env)
docker-up:
    @echo "🐳 Starting backend + Redis with Docker Compose..."
    @echo "Using unified .env from project root (../.env)"
    @echo "ℹ️  This is for local testing - production uses hosting platform"
    cd backend && docker-compose up --build

# Stop Docker Compose services
docker-down:
    @echo "🐳 Stopping Docker Compose services..."
    cd backend && docker-compose down

# View Docker Compose logs
docker-logs:
    @echo "📋 Showing Docker Compose logs..."
    cd backend && docker-compose logs -f

# Test Docker build without cache (troubleshooting)
docker-build-clean:
    @echo "🐳 Building Docker image (no cache)..."
    cd backend && docker build --no-cache -t soulcaster-backend .

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

# Deploy backend (git push triggers auto-deploy)
prod-deploy-backend:
    @echo "🚀 Deploying backend..."
    @echo "⚠️  Ensure you've:"
    @echo "   1. Committed all changes"
    @echo "   2. Updated env vars in hosting dashboard"
    @echo "   3. Pushed to 'main' branch"
    @echo ""
    git push origin main

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
    echo ""
    echo "Unified .env (recommended):"
    if [ -f .env ]; then
        echo "  ✅ Found at project root"
        echo ""
        echo "  Required variables:"
        grep -q "^ENVIRONMENT=" .env && echo "    ✅ ENVIRONMENT" || echo "    ❌ ENVIRONMENT (missing or commented)"
        grep -q "^UPSTASH_REDIS_REST_URL=" .env && echo "    ✅ UPSTASH_REDIS_REST_URL" || echo "    ❌ UPSTASH_REDIS_REST_URL"
        grep -q "^UPSTASH_REDIS_REST_TOKEN=" .env && echo "    ✅ UPSTASH_REDIS_REST_TOKEN" || echo "    ❌ UPSTASH_REDIS_REST_TOKEN"
        grep -q "^UPSTASH_VECTOR_REST_URL=" .env && echo "    ✅ UPSTASH_VECTOR_REST_URL" || echo "    ❌ UPSTASH_VECTOR_REST_URL"
        grep -q "^UPSTASH_VECTOR_REST_TOKEN=" .env && echo "    ✅ UPSTASH_VECTOR_REST_TOKEN" || echo "    ❌ UPSTASH_VECTOR_REST_TOKEN"
        grep -q "^GEMINI_API_KEY=" .env && echo "    ✅ GEMINI_API_KEY" || echo "    ❌ GEMINI_API_KEY"
        grep -q "^GITHUB_ID=" .env && echo "    ✅ GITHUB_ID" || echo "    ❌ GITHUB_ID"
        grep -q "^GITHUB_SECRET=" .env && echo "    ✅ GITHUB_SECRET" || echo "    ❌ GITHUB_SECRET"
        grep -q "^NEXTAUTH_SECRET=" .env && echo "    ✅ NEXTAUTH_SECRET" || echo "    ❌ NEXTAUTH_SECRET"
        grep -q "^DATABASE_URL=" .env && echo "    ✅ DATABASE_URL" || echo "    ❌ DATABASE_URL"
        grep -q "^E2B_API_KEY=" .env && echo "    ✅ E2B_API_KEY" || echo "    ❌ E2B_API_KEY"
    else
        echo "  ❌ Missing - run: cp .env.example .env"
    fi
    echo ""
    echo "Legacy files (should be removed):"
    if [ -f backend/.env ]; then echo "  ⚠️  backend/.env exists (remove it)"; fi
    if [ -f dashboard/.env.local ]; then echo "  ⚠️  dashboard/.env.local exists (remove it)"; fi

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
