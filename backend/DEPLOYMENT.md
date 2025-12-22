# Soulcaster Backend Deployment Guide

## Quick Start - Local Docker Testing

**IMPORTANT:** All commands use the unified `.env` file at project root.

```bash
# From project root, use just commands:

# Build and run with Docker Compose (includes local Redis)
just docker-up

# Or build and run just the backend
just docker-build
just docker-run

# View logs
just docker-logs

# Stop services
just docker-down
```

Backend will be available at `http://localhost:8000`

**Env File Location:** All Docker commands automatically use `.env` from the project root (not `backend/.env`)

---

## Production Deployment

### Railway (Recommended - Easiest)

1. **Connect GitHub Repository**
   - Go to [railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub repo"
   - Select `soulcaster` repo

2. **Configure Service**
   - Railway auto-detects the Dockerfile
   - Set root directory: `/backend`
   - Configure environment variables (see below)

3. **Add Redis** (Optional if using Upstash)
   - Click "New" → "Database" → "Redis"
   - Railway provides `REDIS_URL` automatically

4. **Deploy**
   - Push to main branch → auto-deploys
   - Railway provides a public URL

**Environment Variables** (add in Railway dashboard):
```bash
ENVIRONMENT=production
UPSTASH_REDIS_REST_URL=https://your-redis.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-token
UPSTASH_VECTOR_REST_URL=https://your-vector.upstash.io
UPSTASH_VECTOR_REST_TOKEN=your-token
GEMINI_API_KEY=your-key
GITHUB_TOKEN=ghp_your-token
E2B_API_KEY=your-key
BLOB_READ_WRITE_TOKEN=your-token
SENTRY_DSN=your-dsn (optional)
ALLOWED_ORIGINS=https://your-dashboard.vercel.app
```

---

### Render

1. **Create New Web Service**
   - Go to [render.com](https://render.com)
   - Connect GitHub repo
   - Select `backend` directory

2. **Configure Build**
   - Environment: `Docker`
   - Dockerfile path: `./backend/Dockerfile`
   - Auto-deploy: `Yes`

3. **Add Environment Variables** (same as Railway)

4. **Optional: Add Redis**
   - Create new Redis instance in Render
   - Or use Upstash (recommended)

---

### Fly.io

1. **Install flyctl**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Initialize app**
   ```bash
   cd backend
   fly launch --no-deploy
   ```

3. **Set secrets**
   ```bash
   fly secrets set UPSTASH_REDIS_REST_URL=https://...
   fly secrets set GEMINI_API_KEY=...
   # ... (all env vars)
   ```

4. **Deploy**
   ```bash
   fly deploy
   ```

---

### Your Current Hosting (Sevalla/Other)

**If your host supports Dockerfile deployments:**
1. Push `Dockerfile` to repo
2. Configure env vars in hosting dashboard
3. Deploy

**If your host needs manual setup:**
```bash
# SSH into server
git pull origin main
cd backend

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Run with systemd or supervisor
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Post-Deployment Checklist

- [ ] Health check passes: `curl https://your-api.com/health`
- [ ] CORS configured: Add dashboard URL to `ALLOWED_ORIGINS`
- [ ] Environment variables set (all required vars from `.env.example`)
- [ ] Sentry error tracking configured (optional but recommended)
- [ ] Update dashboard `BACKEND_URL` to point to production API
- [ ] Test ingestion endpoint: `POST /ingest/manual`
- [ ] Test clustering: `POST /cluster-jobs`

---

## Monitoring & Maintenance

**Health Checks**
- Endpoint: `GET /health`
- Returns: `{"status": "ok", "redis": "connected", "timestamp": "..."}`

**Logs**
- Railway/Render: View in dashboard
- Fly.io: `fly logs`
- Sentry: Automatic error capture

**Scaling**
- Railway/Render: Auto-scaling available
- Fly.io: `fly scale count 2` (horizontal scaling)

---

## Troubleshooting

**"Connection refused" errors**
- Check `UPSTASH_REDIS_REST_URL` is set correctly
- Verify Upstash Redis is accessible (check Upstash dashboard)

**"Health check failing"**
- Check logs for startup errors
- Verify all required env vars are set
- Test Redis connectivity: `curl $UPSTASH_REDIS_REST_URL/ping -H "Authorization: Bearer $UPSTASH_REDIS_REST_TOKEN"`

**"Module not found" errors**
- Rebuild Docker image: `docker-compose up --build`
- Check `requirements.txt` includes all dependencies

**Jobs not running**
- Check E2B_API_KEY is valid
- Verify GITHUB_TOKEN has repo access
- Check job logs: `GET /jobs/{job_id}/logs`
