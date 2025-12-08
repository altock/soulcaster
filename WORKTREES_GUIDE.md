# Worktrees Guide - Parallel Feature Development

## Overview

This repo uses Git worktrees to enable parallel feature development. Each worktree is a separate working directory that lets you work on different branches simultaneously.

## Current Worktrees

```
📁 soulcaster/                          (main branch)
├── 📁 worktrees/
│   ├── 📁 billing-integration/        (feature/billing-integration)
│   ├── 📁 system-readiness/           (feature/system-readiness)
│   └── 📁 onboarding-flow/            (feature/onboarding-flow)
```

## Quick Commands

### View all worktrees
```bash
git worktree list
```

### Switch between worktrees
Just `cd` into the directory:
```bash
cd worktrees/billing-integration
cd worktrees/system-readiness
cd worktrees/onboarding-flow
cd ../..  # back to main
```

### Test all worktrees in parallel
```bash
./scripts/test-all-worktrees.sh
```

### Run servers in all worktrees (different ports)
```bash
./scripts/run-all-servers.sh
```

## Working in Each Worktree

Each worktree is a complete, independent working directory:

### 1. Billing Integration (`worktrees/billing-integration`)
**Focus:** Payment/Stripe integration, subscription management

Tasks from `tasks/72hr_revenue_plan.md`:
- [ ] Set up Stripe checkout link
- [ ] Design Partner pricing page
- [ ] Payment flow integration
- [ ] Subscription status tracking

```bash
cd worktrees/billing-integration

# Work on billing features
git status
git add dashboard/lib/billing.ts
git commit -m "feat: add Stripe checkout integration"

# Run tests
cd backend && python -m pytest tests -q
cd ../dashboard && npm test

# Run servers (billing worktree)
cd backend && uvicorn main:app --reload --port 8001
cd ../dashboard && npm run dev -- --port 3001
```

### 2. System Readiness (`worktrees/system-readiness`)
**Focus:** Backend stability, observability, logging

Tasks from `documentation/revenue_week1_mrr_plan.md` Section 3:
- [ ] Ensure stable deployment with Redis/Upstash
- [ ] Verify all backend endpoints are reachable
- [ ] Add logging for cluster creation and status changes
- [ ] Add logging for agent job status updates

```bash
cd worktrees/system-readiness

# Work on observability
git status
git add backend/main.py
git commit -m "feat: add structured logging for clusters"

# Run tests
cd backend && python -m pytest tests -q --cov=backend

# Run servers (system worktree)
cd backend && uvicorn main:app --reload --port 8002
```

### 3. Onboarding Flow (`worktrees/onboarding-flow`)
**Focus:** Customer onboarding UI, documentation, setup checklists

Tasks from `tasks/72hr_revenue_plan.md`:
- [ ] Create Design Partner Brief (Google Doc/Notion)
- [ ] Add "Paid Design Partner" section to README
- [ ] Create one-page onboarding checklist
- [ ] Build onboarding UI in dashboard

```bash
cd worktrees/onboarding-flow

# Work on onboarding
git status
git add dashboard/app/onboarding/
git commit -m "feat: add customer onboarding flow"

# Run dashboard
cd dashboard && npm run dev -- --port 3003
```

## Testing in Parallel

### Option 1: Manual (3 terminals)

**Terminal 1 - Billing:**
```bash
cd worktrees/billing-integration/backend
python -m pytest tests -q
```

**Terminal 2 - System:**
```bash
cd worktrees/system-readiness/backend
python -m pytest tests -q
```

**Terminal 3 - Onboarding:**
```bash
cd worktrees/onboarding-flow/dashboard
npm test -- --runInBand
```

### Option 2: Automated Script
```bash
# Test all worktrees at once
./scripts/test-all-worktrees.sh
```

## Running Servers in Parallel

Each worktree can run its own backend and dashboard on different ports:

| Worktree | Backend Port | Dashboard Port | Dashboard URL |
|----------|--------------|----------------|---------------|
| Main | 8000 | 3000 | http://localhost:3000 |
| Billing | 8001 | 3001 | http://localhost:3001 |
| System | 8002 | 3002 | http://localhost:3002 |
| Onboarding | 8003 | 3003 | http://localhost:3003 |

### Start all servers at once:
```bash
./scripts/run-all-servers.sh
```

### Or start manually in separate terminals:

**Terminal 1 - Billing:**
```bash
cd worktrees/billing-integration
cd backend && uvicorn main:app --reload --port 8001 &
cd dashboard && npm run dev -- --port 3001
```

**Terminal 2 - System:**
```bash
cd worktrees/system-readiness
cd backend && uvicorn main:app --reload --port 8002 &
cd dashboard && npm run dev -- --port 3002
```

**Terminal 3 - Onboarding:**
```bash
cd worktrees/onboarding-flow/dashboard
npm run dev -- --port 3003
```

## Syncing Changes Between Worktrees

When you need to pull in changes from main:

```bash
cd worktrees/billing-integration
git fetch origin
git rebase origin/main
# or
git merge origin/main
```

## Merging Features Back to Main

Once a feature is complete:

```bash
# From any worktree, push your feature branch
cd worktrees/billing-integration
git push origin feature/billing-integration

# Then create a PR on GitHub
# Or merge locally:
cd ../..  # back to main
git merge feature/billing-integration
git push origin main
```

## Cleaning Up Worktrees

When done with a feature:

```bash
# Remove the worktree
git worktree remove worktrees/billing-integration

# Delete the branch (optional)
git branch -d feature/billing-integration
```

## Common Operations

### Check status across all worktrees
```bash
git worktree list
for worktree in worktrees/*; do
  echo "=== $worktree ==="
  cd "$worktree" && git status -s && cd ../..
done
```

### Create a new worktree
```bash
git worktree add worktrees/new-feature -b feature/new-feature
```

### Install dependencies in a new worktree
```bash
cd worktrees/billing-integration
pip install -r backend/requirements.txt
npm install --prefix dashboard
```

## Tips

1. **Each worktree shares the same .git directory** - commits made in one worktree are visible in all others
2. **Different branches can have different code** - perfect for testing breaking changes
3. **Use different ports** - run multiple versions simultaneously
4. **Test isolation** - each worktree can have different env vars
5. **PR workflow** - open separate PRs for each feature branch

## Task Mapping

Based on your revenue plan, here's what belongs in each worktree:

### Billing Integration
- Stripe integration (`dashboard/lib/billing.ts`)
- Checkout flow (`dashboard/app/billing/`)
- Subscription management
- Payment links and pricing pages

### System Readiness
- Backend logging and observability
- Redis/Upstash stability
- Endpoint verification
- Error tracking and monitoring
- CloudWatch/logging setup

### Onboarding Flow
- Customer onboarding UI
- Setup checklists
- Documentation for design partners
- Welcome flows and tutorials
- Configuration wizards

## Next Steps

1. Copy your current billing work to the billing-integration worktree
2. Start working on system readiness in parallel
3. Keep main branch clean - only merge tested features
4. Use the scripts provided to test everything in parallel

Happy parallel development! 🚀

