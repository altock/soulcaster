# Phase 1 Testing Guide

This guide shows you how to test the Phase 1 ingestion moat code.

## Quick Test (30 seconds)

```bash
cd /Users/nagakarumuri/Documents/Hackathon/soulcaster/worktrees/system-readiness

# Run the interactive Python test
python test_phase1_interactive.py
```

**Expected output:** All tests PASS ✅

---

## Option 1: Automated Unit Tests ⚡ (Fastest)

### Run Phase 1 specific tests
```bash
cd backend
python -m pytest tests/test_ingestion.py -k "unclustered" -v
```

**Output:**
```
tests/test_ingestion.py::test_add_feedback_writes_to_unclustered PASSED
tests/test_ingestion.py::test_all_sources_add_to_unclustered PASSED
tests/test_ingestion.py::test_remove_from_unclustered PASSED
tests/test_ingestion.py::test_get_unclustered_feedback_empty PASSED
tests/test_ingestion.py::test_duplicate_ingestion_does_not_duplicate_unclustered PASSED

5 passed
```

### Run all ingestion tests
```bash
python -m pytest tests/test_ingestion.py -v
```

**Output:** `12 passed`

### Run full backend test suite
```bash
python -m pytest tests/ -v
```

**Output:** `36 passed`

### Run with coverage
```bash
python -m pytest tests/ --cov=backend --cov-report=term-missing
```

Shows exactly which lines are tested.

---

## Option 2: Interactive Python Test 🐍 (Most Detailed)

```bash
cd /Users/nagakarumuri/Documents/Hackathon/soulcaster/worktrees/system-readiness
python test_phase1_interactive.py
```

**What it tests:**
- ✅ Adds 3 feedback items (reddit, sentry, manual)
- ✅ Verifies all are in unclustered set
- ✅ Removes one item from unclustered
- ✅ Verifies item still exists in storage
- ✅ Shows detailed step-by-step output

**Expected:** All 6 tests pass with detailed logs

---

## Option 3: Manual API Testing 🌐 (Most Real-World)

### Step 1: Start Backend Server

**Terminal 1:**
```bash
cd /Users/nagakarumuri/Documents/Hackathon/soulcaster/worktrees/system-readiness/backend
uvicorn main:app --reload --port 8002
```

Wait for: `Uvicorn running on http://127.0.0.1:8002`

### Step 2: Run Manual Test Script

**Terminal 2:**
```bash
cd /Users/nagakarumuri/Documents/Hackathon/soulcaster/worktrees/system-readiness
./test_phase1_manual.sh
```

This will:
1. POST to `/ingest/reddit`
2. POST to `/ingest/manual`
3. POST to `/ingest/sentry`
4. GET `/feedback` to see all items
5. GET `/stats` to see counts

### Step 3: Manual curl commands (optional)

```bash
# Ingest Reddit feedback
curl -X POST http://localhost:8002/ingest/reddit \
  -H "Content-Type: application/json" \
  -d '{
    "id": "manual-test-001",
    "source": "reddit",
    "external_id": "t3_manual001",
    "title": "Manual test bug",
    "body": "Testing unclustered tracking",
    "metadata": {"subreddit": "testing"},
    "created_at": "2024-12-08T10:00:00Z"
  }'

# Check all feedback
curl http://localhost:8002/feedback | jq '.'

# Check stats
curl http://localhost:8002/stats | jq '.'
```

---

## Option 4: Redis Verification 🔴 (If using Redis)

If you're using Redis/Upstash, you can directly inspect the keys:

```bash
# Connect to Redis
redis-cli

# Or for Upstash, use their CLI or REST API
```

**Redis commands to verify:**

```redis
# See all unclustered feedback IDs
SMEMBERS feedback:unclustered

# Check a specific feedback item
HGETALL feedback:<uuid>

# See all feedback by source
SMEMBERS feedback:source:reddit
SMEMBERS feedback:source:sentry
SMEMBERS feedback:source:manual

# See feedback sorted by creation time
ZRANGE feedback:created 0 -1 WITHSCORES
```

**Expected:**
- `feedback:unclustered` set contains UUIDs of all ingested items
- Each `feedback:<uuid>` hash contains the full item data
- Source sets contain appropriate items

---

## Option 5: Parallel Testing 🎭 (Test All Worktrees)

From the main repo:

```bash
cd /Users/nagakarumuri/Documents/Hackathon/soulcaster
./scripts/test-all-worktrees.sh
```

This tests:
- `system-readiness` worktree (your Phase 1 code)
- `billing-integration` worktree
- `onboarding-flow` worktree

---

## Verification Checklist

After running tests, verify:

- [ ] ✅ 36 backend tests pass
- [ ] ✅ 12 ingestion tests pass (including 5 new Phase 1 tests)
- [ ] ✅ `get_unclustered_feedback()` returns items
- [ ] ✅ `remove_from_unclustered()` removes items from set (but not storage)
- [ ] ✅ All sources (reddit, sentry, manual, github) add to unclustered
- [ ] ✅ Duplicate external_ids don't add multiple unclustered entries
- [ ] ✅ No linting errors
- [ ] ✅ Interactive test passes all 6 checks

---

## Common Issues & Solutions

### Issue: "Module not found: backend.store"
**Solution:** Make sure you're in the right directory:
```bash
cd /Users/nagakarumuri/Documents/Hackathon/soulcaster/worktrees/system-readiness
```

### Issue: "Redis connection refused"
**Solution:** Tests use in-memory store by default. This is fine! Tests will pass without Redis.

### Issue: "Port 8002 already in use"
**Solution:** 
```bash
# Kill existing process
lsof -ti:8002 | xargs kill -9

# Or use a different port
uvicorn main:app --reload --port 8003
```

### Issue: Tests fail with old data
**Solution:** Clear test data:
```bash
cd backend
python -c "from backend.store import clear_feedback_items; clear_feedback_items()"
```

---

## What Each Test Proves

### Automated Tests (test_ingestion.py)

| Test | What It Proves |
|------|---------------|
| `test_add_feedback_writes_to_unclustered` | Items are added to unclustered set on ingestion |
| `test_all_sources_add_to_unclustered` | Reddit, Sentry, AND Manual all add to unclustered |
| `test_remove_from_unclustered` | Items can be removed from unclustered set |
| `test_get_unclustered_feedback_empty` | Empty state handled correctly |
| `test_duplicate_ingestion_does_not_duplicate_unclustered` | Duplicates don't create multiple entries |

### Interactive Test (test_phase1_interactive.py)

| Test | What It Proves |
|------|---------------|
| Test 1 | Can add items from multiple sources |
| Test 2 | All items are stored correctly |
| Test 3 | **All items appear in unclustered set** (KEY TEST) |
| Test 4 | Can remove items from unclustered |
| Test 5 | Removal is reflected in get_unclustered_feedback() |
| Test 6 | Removed items still exist in storage (not deleted) |

---

## Performance Testing (Optional)

Test with many items:

```python
cd backend
python -c "
from backend.models import FeedbackItem
from backend.store import add_feedback_item, get_unclustered_feedback
from uuid import uuid4
from datetime import datetime
import time

# Add 1000 items
start = time.time()
for i in range(1000):
    add_feedback_item(FeedbackItem(
        id=uuid4(),
        source='manual',
        title=f'Test {i}',
        body=f'Body {i}',
        metadata={},
        created_at=datetime.now()
    ))
duration = time.time() - start
print(f'Added 1000 items in {duration:.2f}s')

# Get unclustered
start = time.time()
unclustered = get_unclustered_feedback()
duration = time.time() - start
print(f'Retrieved {len(unclustered)} unclustered items in {duration:.2f}s')
"
```

**Expected:** Sub-second performance for 1000 items with in-memory store.

---

## Next Steps After Testing

Once all tests pass:

1. **Commit your work** (already done ✅)
   ```bash
   git log --oneline -1
   ```

2. **Move to Day 2**
   ```bash
   cat ../tasks/PHASE1_CHECKLIST.md | grep -A 20 "Day 2"
   ```

3. **Review endpoints**
   ```bash
   code backend/main.py
   ```

---

## Quick Reference

```bash
# Fastest test
pytest tests/test_ingestion.py -k unclustered -v

# Most visual test
python test_phase1_interactive.py

# Real-world test
./test_phase1_manual.sh  # (requires backend running)

# Full suite
pytest tests/ -v
```

**All tests passing? You're ready for Phase 1 Day 2!** 🚀


