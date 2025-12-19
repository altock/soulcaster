.PHONY: help dev-backend dev-dashboard dev-reset prod-health test lint format install-backend install-dashboard

# Default target
help:
	@echo "Soulcaster Development Commands"
	@echo "================================"
	@echo ""
	@echo "Development:"
	@echo "  make dev-backend         - Run FastAPI backend (localhost:8000)"
	@echo "  make dev-dashboard       - Run Next.js dashboard (localhost:3000)"
	@echo "  make dev-reset           - Reset all DEV data (Redis + Vector)"
	@echo "  make dev-reset-force     - Reset DEV data without confirmation"
	@echo ""
	@echo "Production:"
	@echo "  make prod-health         - Check production backend health"
	@echo "  make prod-deploy-backend - Deploy backend to Sevalla"
	@echo "  make prod-deploy-dashboard - Deploy dashboard to Vercel"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test                - Run all tests"
	@echo "  make test-backend        - Run backend tests only"
	@echo "  make test-dashboard      - Run dashboard tests only"
	@echo "  make lint                - Run linters"
	@echo "  make format              - Format code"
	@echo ""
	@echo "Installation:"
	@echo "  make install-backend     - Install backend dependencies (uv)"
	@echo "  make install-dashboard   - Install dashboard dependencies (npm)"
	@echo "  make install             - Install all dependencies"

# ============================================================================
# Development
# ============================================================================

dev-backend:
	@echo "🚀 Starting FastAPI backend on http://localhost:8000"
	cd backend && uv run uvicorn main:app --reload --port 8000

dev-dashboard:
	@echo "🚀 Starting Next.js dashboard on http://localhost:3000"
	cd dashboard && npm run dev

dev-reset:
	@echo "🗑️  Resetting DEV data..."
	python scripts/reset_dev_data.py

dev-reset-force:
	@echo "🗑️  Force resetting DEV data (no confirmation)..."
	python scripts/reset_dev_data.py --force

# ============================================================================
# Production
# ============================================================================

prod-health:
	@echo "🏥 Checking production backend health..."
	@if [ -z "$$PROD_BACKEND_URL" ]; then \
		echo "❌ PROD_BACKEND_URL not set"; \
		exit 1; \
	fi
	@curl -sf $$PROD_BACKEND_URL/health | jq '.' || echo "❌ Health check failed"

prod-deploy-backend:
	@echo "🚀 Deploying backend to Sevalla..."
	@echo "⚠️  Manual step required:"
	@echo "   1. Push to 'main' branch"
	@echo "   2. Sevalla will auto-deploy"
	@echo ""
	@echo "Or use Sevalla CLI if configured"

prod-deploy-dashboard:
	@echo "🚀 Deploying dashboard to Vercel..."
	cd dashboard && vercel --prod

# ============================================================================
# Testing & Quality
# ============================================================================

test: test-backend test-dashboard

test-backend:
	@echo "🧪 Running backend tests..."
	cd backend && uv run pytest -v

test-dashboard:
	@echo "🧪 Running dashboard tests..."
	cd dashboard && npm test

lint:
	@echo "🔍 Linting code..."
	@echo "Backend:"
	cd backend && uv run ruff check .
	@echo "Dashboard:"
	cd dashboard && npm run lint

format:
	@echo "✨ Formatting code..."
	@echo "Backend:"
	cd backend && uv run black .
	cd backend && uv run ruff check --fix .
	@echo "Dashboard:"
	cd dashboard && npm run format

# ============================================================================
# Installation
# ============================================================================

install-backend:
	@echo "📦 Installing backend dependencies with uv..."
	cd backend && uv sync

install-dashboard:
	@echo "📦 Installing dashboard dependencies..."
	cd dashboard && npm install
	cd dashboard && npx prisma generate

install: install-backend install-dashboard
	@echo "✅ All dependencies installed!"

# ============================================================================
# Database
# ============================================================================

db-migrate:
	@echo "🗄️  Running Prisma migrations..."
	cd dashboard && npx prisma migrate dev

db-reset:
	@echo "🗄️  Resetting Prisma database..."
	cd dashboard && npx prisma migrate reset

db-studio:
	@echo "🗄️  Opening Prisma Studio..."
	cd dashboard && npx prisma studio

# ============================================================================
# Utilities
# ============================================================================

check-env:
	@echo "🔍 Checking environment configuration..."
	@echo "Backend .env:"
	@if [ -f backend/.env ]; then echo "✅ Found"; else echo "❌ Missing"; fi
	@echo "Dashboard .env.local:"
	@if [ -f dashboard/.env.local ]; then echo "✅ Found"; else echo "❌ Missing"; fi

logs-backend-dev:
	@echo "📋 Tailing local backend logs..."
	tail -f backend/logs/*.log 2>/dev/null || echo "No log files found"

clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf backend/__pycache__ backend/**/__pycache__
	rm -rf dashboard/.next dashboard/node_modules/.cache
	@echo "✅ Clean complete"
