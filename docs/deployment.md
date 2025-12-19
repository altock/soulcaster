# Soulcaster Deployment Guide

Complete guide for deploying Soulcaster to DEV and PROD environments.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         DEV                                  │
├─────────────────────────────────────────────────────────────┤
│  Dashboard: Vercel Preview                                   │
│  Backend: Sevalla Account #1                                 │
│  Redis: Upstash DEV instance                                 │
│  Vector: Upstash Vector DEV instance                         │
│  Database: PostgreSQL DEV (Neon)                             │
│  Data: Resettable via script                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                         PROD                                 │
├─────────────────────────────────────────────────────────────┤
│  Dashboard: Vercel Production                                │
│  Backend: Sevalla Account #2                                 │
│  Redis: Upstash PROD instance                                │
│  Vector: Upstash Vector PROD instance                        │
│  Database: PostgreSQL PROD (Neon)                            │
│  Data: Protected, no reset capability                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Required Accounts

1. **Sevalla** (2 accounts - one for dev, one for prod)
   - Sign up at: https://sevalla.com
   - Each account has $50 credit

2. **Upstash** (1 account with multiple databases)
   - Sign up at: https://upstash.com
   - Create separate Redis instances for dev/prod
   - Create separate Vector instances for dev/prod

3. **Vercel** (1 account)
   - Sign up at: https://vercel.com
   - Connect your GitHub repository

4. **Neon** or **Supabase** (PostgreSQL database)
   - Neon: https://neon.tech
   - Supabase: https://supabase.com
   - Create separate databases for dev/prod

5. **Google AI Studio** (Gemini API)
   - Get API key at: https://makersuite.google.com/app/apikey

6. **E2B** (Sandbox runtime)
   - Sign up at: https://e2b.dev
   - Get API key from dashboard

### Required Tools

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Node.js (v18+)
# Download from: https://nodejs.org

# Install Vercel CLI (optional, for manual deployments)
npm install -g vercel

# Install Just (modern command runner)
brew install just  # macOS
# or: cargo install just

# Install jq (for JSON parsing)
brew install jq  # macOS
# or: apt-get install jq  # Linux
```

---

## Step 1: Upstash Setup

### 1.1 Create Redis Instances

#### DEV Redis
1. Go to https://console.upstash.com/redis
2. Click "Create Database"
3. Name: `soulcaster-dev`
4. Region: Choose closest to you
5. Type: Pay as you go
6. Copy REST URL and REST token

#### PROD Redis
1. Repeat above steps
2. Name: `soulcaster-prod`
3. Copy REST URL and REST token

### 1.2 Create Vector Instances

#### DEV Vector
1. Go to https://console.upstash.com/vector
2. Click "Create Index"
3. Name: `soulcaster-dev-embeddings`
4. Dimensions: `768` (for Gemini text-embedding-004)
5. Region: Same as Redis
6. Copy REST URL and REST token

#### PROD Vector
1. Repeat above steps
2. Name: `soulcaster-prod-embeddings`
3. Copy REST URL and REST token

---

## Step 2: Backend Deployment (Sevalla)

### 2.1 DEV Backend Setup

#### Create Sevalla App (Account #1)

1. Log into your first Sevalla account
2. Click "Add Application"
3. Configure:
   - **Name**: `soulcaster-backend-dev`
   - **Repository**: Connect your GitHub repo
   - **Branch**: `dev` or `main`
   - **Root directory**: `backend`
   - **Build command**: `uv sync`
   - **Start command**: `uv run uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Port**: Auto (use `$PORT`)

#### Set Environment Variables

In Sevalla dashboard, add these environment variables:

```bash
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Upstash Redis (DEV)
UPSTASH_REDIS_REST_URL=https://your-dev-instance.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-dev-token

# Upstash Vector (DEV)
UPSTASH_VECTOR_REST_URL=https://your-dev-vector.upstash.io
UPSTASH_VECTOR_REST_TOKEN=your-dev-vector-token

# Gemini API
GEMINI_API_KEY=your-gemini-key
GOOGLE_GENERATIVE_AI_API_KEY=your-gemini-key

# GitHub OAuth
GITHUB_ID=your-github-oauth-client-id
GITHUB_SECRET=your-github-oauth-client-secret
GITHUB_TOKEN=ghp_your-personal-access-token

# E2B
E2B_API_KEY=your-e2b-key
KILOCODE_TEMPLATE_NAME=kilo-sandbox-v-0-1-dev
CODING_AGENT_RUNNER=sandbox_kilo

# Backend URL (for agent callbacks)
BACKEND_URL=https://soulcaster-backend-dev.sevalla.app

# Git config
GIT_USER_EMAIL=soulcaster-bot@example.com
GIT_USER_NAME=Soulcaster Bot

# CORS (add your Vercel preview URL)
ALLOWED_ORIGINS=http://localhost:3000,https://your-app-git-dev-username.vercel.app
```

#### Deploy

1. Click "Deploy"
2. Wait for build to complete
3. Test health endpoint: `curl https://soulcaster-backend-dev.sevalla.app/health`

Expected output:
```json
{
  "status": "healthy",
  "service": "soulcaster-backend",
  "environment": "development",
  "storage": "connected",
  "timestamp": "2024-..."
}
```

### 2.2 PROD Backend Setup

Repeat the same steps in your **second Sevalla account**, with these changes:

- **Name**: `soulcaster-backend-prod`
- **Branch**: `main`
- **ENVIRONMENT**: `production`
- **LOG_LEVEL**: `INFO`
- Use PROD Upstash credentials
- **BACKEND_URL**: `https://soulcaster-backend-prod.sevalla.app`
- **ALLOWED_ORIGINS**: `https://your-app.vercel.app`

---

## Step 3: PostgreSQL Database Setup

### 3.1 Create Neon Databases

#### DEV Database
1. Go to https://console.neon.tech
2. Click "Create Project"
3. Name: `soulcaster-dev`
4. Region: Same as your backend
5. Copy connection string (starts with `postgresql://`)
6. Save as `DATABASE_URL` for dashboard

#### PROD Database
1. Repeat above
2. Name: `soulcaster-prod`
3. Copy connection string

---

## Step 4: Dashboard Deployment (Vercel)

### 4.1 Connect Repository

1. Go to https://vercel.com
2. Click "Add New Project"
3. Import your GitHub repository
4. Configure:
   - **Framework Preset**: Next.js
   - **Root Directory**: `dashboard`
   - **Build Command**: `npm run build` (default)
   - **Output Directory**: `.next` (default)

### 4.2 Environment Variables

#### Production Environment

Add these in Vercel → Settings → Environment Variables → Production:

```bash
BACKEND_URL=https://soulcaster-backend-prod.sevalla.app

# Upstash Redis (PROD)
UPSTASH_REDIS_REST_URL=https://your-prod-instance.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-prod-token

# Upstash Vector (PROD)
UPSTASH_VECTOR_REST_URL=https://your-prod-vector.upstash.io
UPSTASH_VECTOR_REST_TOKEN=your-prod-vector-token

# Gemini
GEMINI_API_KEY=your-gemini-key

# GitHub OAuth (PROD app)
GITHUB_ID=your-prod-github-oauth-client-id
GITHUB_SECRET=your-prod-github-oauth-client-secret

# NextAuth
NEXTAUTH_URL=https://your-app.vercel.app
NEXTAUTH_SECRET=<generate with: openssl rand -base64 32>

# Database (PROD)
DATABASE_URL=postgresql://...neon.tech/soulcaster-prod
```

#### Preview Environment (DEV)

Add these in Vercel → Settings → Environment Variables → Preview:

```bash
BACKEND_URL=https://soulcaster-backend-dev.sevalla.app

# Use DEV Upstash credentials
UPSTASH_REDIS_REST_URL=https://your-dev-instance.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-dev-token

UPSTASH_VECTOR_REST_URL=https://your-dev-vector.upstash.io
UPSTASH_VECTOR_REST_TOKEN=your-dev-vector-token

# DEV GitHub OAuth app
GITHUB_ID=your-dev-github-oauth-client-id
GITHUB_SECRET=your-dev-github-oauth-client-secret

# NextAuth (use preview URL)
NEXTAUTH_URL=https://your-app-git-dev-username.vercel.app
NEXTAUTH_SECRET=<generate a different secret for dev>

# Database (DEV)
DATABASE_URL=postgresql://...neon.tech/soulcaster-dev
```

### 4.3 Run Prisma Migrations

After first deployment:

```bash
# Local setup first
cd dashboard
npm install
npx prisma migrate dev --name init

# Push to production
npx prisma migrate deploy
```

Or set up in Vercel:
- Add build command: `npx prisma migrate deploy && npx prisma generate && next build`

---

## Step 5: GitHub OAuth Apps

### 5.1 DEV OAuth App

1. Go to https://github.com/settings/developers
2. Click "New OAuth App"
3. Configure:
   - **Application name**: Soulcaster DEV
   - **Homepage URL**: `https://your-app-git-dev-username.vercel.app`
   - **Authorization callback URL**: `https://your-app-git-dev-username.vercel.app/api/auth/callback/github`
4. Click "Register application"
5. Copy **Client ID** and generate **Client Secret**
6. Add to Vercel Preview environment variables

### 5.2 PROD OAuth App

1. Repeat above steps
2. **Application name**: Soulcaster
3. **Homepage URL**: `https://your-app.vercel.app`
4. **Callback URL**: `https://your-app.vercel.app/api/auth/callback/github`
5. Add to Vercel Production environment variables

---

## Step 6: Local Development Setup

### 6.1 Clone and Configure

```bash
# Clone repository
git clone https://github.com/your-username/soulcaster.git
cd soulcaster

# Copy environment templates
cp backend/.env.example backend/.env
cp dashboard/.env.example dashboard/.env.local

# Edit .env files with DEV credentials
nano backend/.env
nano dashboard/.env.local
```

### 6.2 Install Dependencies

```bash
# Using just (recommended)
just install

# Or manually:
cd backend && uv sync
cd dashboard && npm install && npx prisma generate
```

### 6.3 Run Locally

```bash
# Terminal 1: Backend
just dev-backend
# or: cd backend && uv run uvicorn main:app --reload --port 8000

# Terminal 2: Dashboard
just dev-dashboard
# or: cd dashboard && npm run dev

# Access:
# - Dashboard: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

---

## Step 7: Testing the Setup

### 7.1 Health Checks

```bash
# Local
curl http://localhost:8000/health | jq

# DEV
curl https://soulcaster-backend-dev.sevalla.app/health | jq

# PROD
curl https://soulcaster-backend-prod.sevalla.app/health | jq
```

Expected response:
```json
{
  "status": "healthy",
  "service": "soulcaster-backend",
  "environment": "development",  // or "production"
  "storage": "connected",
  "timestamp": "2024-12-18T..."
}
```

### 7.2 Test Dashboard

1. Open dashboard URL
2. Click "Sign in with GitHub"
3. Authorize the OAuth app
4. You should see the dashboard with empty state

### 7.3 Test Data Flow

1. Ingest test feedback:
   ```bash
   curl -X POST http://localhost:8000/ingest/manual \
     -H "Content-Type: application/json" \
     -d '{"text": "Test feedback item", "project_id": "your-project-id"}'
   ```

2. Check in dashboard - should see the feedback item
3. Try clustering in the UI
4. Create a test cluster

---

## Step 8: Data Reset (DEV Only)

### Reset DEV Data

```bash
# Interactive (asks for confirmation)
just dev-reset

# Force (no confirmation)
just dev-reset-force

# Or directly:
python scripts/reset_dev_data.py
python scripts/reset_dev_data.py --force
```

The script will:
- ✅ Validate you're using DEV credentials (refuses PROD)
- ✅ Scan and delete all Redis keys
- ✅ Reset Upstash Vector database
- ✅ Print summary of deleted items

**Safety features:**
- Refuses to run if `ENVIRONMENT=production`
- Refuses to run if URL contains "prod" or "production"
- Requires typing "DELETE" to confirm (unless `--force`)

---

## Troubleshooting

### Backend won't start

**Check logs in Sevalla:**
1. Go to Sevalla dashboard
2. Click on your app
3. Click "Logs"

**Common issues:**
- Missing environment variables
- Invalid Upstash credentials
- Port already in use (local)

### Dashboard shows "Network Error"

**Check:**
1. BACKEND_URL is set correctly in Vercel
2. Backend is actually running (check health endpoint)
3. CORS settings allow the dashboard origin

### "Storage disconnected" in health check

**Check:**
1. UPSTASH_REDIS_REST_URL is correct
2. UPSTASH_REDIS_REST_TOKEN is valid
3. Upstash instance is not paused/deleted

### GitHub OAuth fails

**Check:**
1. Callback URL matches exactly (including https://)
2. Client ID and Secret are correct
3. OAuth app is not suspended

### Prisma errors

```bash
# Regenerate client
cd dashboard
npx prisma generate

# Reset database (DEV only!)
npx prisma migrate reset

# Create new migration
npx prisma migrate dev --name your_migration_name
```

---

## Maintenance

### Update Dependencies

```bash
# Backend
cd backend
uv sync --upgrade

# Dashboard
cd dashboard
npm update
npx prisma generate
```

### Monitor Costs

**Sevalla:**
- Check usage dashboard
- $50 credit should last months for dev

**Upstash:**
- Free tier: 10,000 commands/day per database
- Monitor at: https://console.upstash.com

**Neon:**
- Free tier: 3 GB storage, 1 active database
- Monitor at: https://console.neon.tech

**Vercel:**
- Free tier: 100 GB bandwidth/month
- Monitor at: https://vercel.com/dashboard/usage

---

## Security Checklist

- [ ] DEV and PROD use separate Upstash instances
- [ ] DEV and PROD use separate PostgreSQL databases
- [ ] DEV and PROD use separate GitHub OAuth apps
- [ ] NEXTAUTH_SECRET is different for DEV and PROD
- [ ] PROD environment variables are not committed to git
- [ ] `.env` and `.env.local` are in `.gitignore`
- [ ] Reset script refuses to run with PROD credentials
- [ ] Sevalla PROD account has 2FA enabled
- [ ] GitHub account has 2FA enabled
- [ ] Upstash PROD databases have backups enabled

---

## Next Steps

1. **Set up monitoring** (see docs/operations/monitoring_alerting.md)
2. **Configure backups** (see docs/operations/backup_restore.md)
3. **Add integrations** (Datadog, PostHog, Splunk - see docs/integrations-design.md)
4. **Set up CI/CD** (GitHub Actions for automated testing)
5. **Configure custom domain** (Vercel custom domains for PROD)

---

## Quick Reference

### Useful Commands

```bash
# Show all available commands
just

# Development
just dev-backend              # Run backend locally
just dev-dashboard            # Run dashboard locally
just dev-reset               # Reset DEV data
just install                 # Install all dependencies

# Testing
just test                    # Run all tests
just test-backend            # Backend tests only
just lint                    # Run linters

# Production
just prod-health             # Check PROD health
just prod-deploy-dashboard   # Deploy to Vercel

# Database
just db-migrate              # Run Prisma migrations
just db-studio              # Open Prisma Studio
```

### Important URLs

| Environment | Service | URL |
|-------------|---------|-----|
| DEV | Backend | https://soulcaster-backend-dev.sevalla.app |
| DEV | Dashboard | https://your-app-git-dev.vercel.app |
| DEV | Health Check | https://soulcaster-backend-dev.sevalla.app/health |
| PROD | Backend | https://soulcaster-backend-prod.sevalla.app |
| PROD | Dashboard | https://your-app.vercel.app |
| PROD | Health Check | https://soulcaster-backend-prod.sevalla.app/health |

---

## Support

- **Documentation**: See `/docs` directory
- **Issues**: https://github.com/your-username/soulcaster/issues
- **Sevalla Docs**: https://sevalla.com/docs
- **Vercel Docs**: https://vercel.com/docs
- **Upstash Docs**: https://docs.upstash.com
