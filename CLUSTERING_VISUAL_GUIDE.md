# Clustering Visual Guide - References & Diagrams

## Algorithm Comparison Visual

```
                    SPEED ➜
        ┌─────────────────────────────────────┐
        │  Fast         Medium        Slow    │
    H   │ DBSCAN      Agglom      Spectral   │
    I   │ Vector-like  HDBSCAN    Affinity   │
    G   │                         Prop        │
    H   │                                     │
        │  BEST FOR:              BEST FOR:   │
        │  • High volume          • Best UX   │
    E   │  • Outliers            • Exemplars │
    X   │  • Real-time           • Hierarchy │
    P   │                                     │
    L   │  BEST FOR:              BEST FOR:   │
    A   │  • Known K              • Non-metric
    I   │  • Any shape            • Slow data
    N   │  • Simple threshold                 │
    A   │                                     │
    B   │  K-Means              Hierarchical │
    I   │  (Not recommended)     + Dendrogram│
    L   │                                     │
    I   │                                     │
    T   └─────────────────────────────────────┘
    Y

        ← LOW                  INTERPRETABILITY ➜
```

---

## Silhouette Score Scale

```
SILHOUETTE SCORE: -1.0 to 1.0

 1.0 ┌─ PERFECT (1.0)
     │   ✓ All items perfectly grouped
 0.8 │   ✓ Very confident clustering
     │   ████████░░░░░░░░░░░░
 0.6 │   ✓ HIGH CONFIDENCE 🟢
     │   ██████░░░░░░░░░░░░░░
 0.4 │   ◐ MEDIUM confidence
     │   ████░░░░░░░░░░░░░░░░
 0.2 │   ◐ Medium confidence
     │   ██░░░░░░░░░░░░░░░░░░
 0.0 │   ✗ Overlapping clusters
     │
-0.2 │   ✗ LOW confidence 🔴
     │   ░░░░░░░░░░░░░░░░░░░░
-0.5 │   ✗ Wrong clusters
     │   ░░░░░░░░░░░░░░░░░░░░
-1.0 └─ VERY WRONG (-1.0)

     ← Bad | Marginal | Good | Very Good →
```

---

## Current Soulcaster Flow

```
                    ┌─────────────────────┐
                    │   User Feedback     │
                    │ (64-5000 items)     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Prepare Texts       │
                    │ (title + body)      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Embed via Gemini    │
                    │ (768-dim vectors)   │
                    └──────────┬──────────┘
                               │
                               ▼
         ┌─────────────────────────────────────────┐
         │  Vector DB Query (Upstash)              │
         │  Find existing similar items (ANN)      │
         └──────────┬──────────────────────────────┘
                    │
                    ▼
         ┌─────────────────────────────────────────┐
         │ In-Memory Clustering                    │
         │ ├─ Agglomerative      (CURRENT DEFAULT)│
         │ ├─ Centroid           (ALTERNATIVE)    │
         │ └─ Vector-Like        (ALTERNATIVE)    │
         │                                         │
         │ Rule: similarity >= 0.72 → same cluster │
         └──────────┬──────────────────────────────┘
                    │
                    ▼
         ┌─────────────────────────────────────────┐
         │ Store Clusters in Redis                 │
         │ ├─ cluster:{id}        (cluster data)   │
         │ ├─ cluster:items:{id}  (feedback IDs)   │
         │ └─ clusters:all:{proj} (all cluster IDs)│
         └──────────┬──────────────────────────────┘
                    │
                    ▼
         ┌─────────────────────────────────────────┐
         │ Display on Dashboard                    │
         │ ├─ Title (from first item)              │
         │ ├─ Count                                │
         │ ├─ Sources                              │
         │ ├─ Status                               │
         │ └─ ❌ No quality indicator              │
         └─────────────────────────────────────────┘

PROBLEM: Users don't know why items grouped!
```

---

## Proposed Flow with Improvements

```
              [Same as above until Redis storage]
                               │
                               ▼
         ┌─────────────────────────────────────────┐
         │ TIER 1: Compute Quality Metrics 🟢      │
         │ ├─ Silhouette score (-1 to 1)          │
         │ ├─ Confidence badge (High/Med/Low)     │
         │ ├─ Explanation (human-readable)        │
         │ └─ Low-confidence items list            │
         └──────────┬──────────────────────────────┘
                    │
         ┌──────────▼──────────┐
         │   TIER 2: Upgrade   │
         │   to HDBSCAN 🟡     │
         │   ├─ Auto cluster count
         │   ├─ Exemplars (top items)
         │   ├─ Soft scores (probability)
         │   └─ Outlier detection
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────────────────────────┐
         │ TIER 3: Two-Stage Clustering 🟠        │
         │ ├─ Vector DB coarse grouping           │
         │ ├─ DBSCAN fine-grained clustering      │
         │ ├─ Auto-eps parameter tuning           │
         │ └─ Confidence trends over time         │
         └──────────┬──────────────────────────────┘
                    │
                    ▼
         ┌─────────────────────────────────────────┐
         │ Store Clusters in Redis (Enhanced)      │
         │ ├─ cluster:{id}              (data)     │
         │ ├─ cluster:metrics:{id}      (NEW)      │
         │ │  ├─ silhouette_score                  │
         │ │  ├─ confidence_badge                  │
         │ │  ├─ exemplar_ids                      │
         │ │  └─ soft_scores                       │
         │ └─ cluster:items:{id}        (items)    │
         └──────────┬──────────────────────────────┘
                    │
                    ▼
         ┌─────────────────────────────────────────┐
         │ Display on Dashboard (Enhanced)         │
         │ ├─ Title                                │
         │ ├─ Count                                │
         │ ├─ Sources                              │
         │ ├─ Status                               │
         │ ├─ ✓ Confidence Badge 🟢                │
         │ ├─ ✓ Explanation (why grouped)          │
         │ ├─ ✓ Representative items               │
         │ └─ ✓ Manual split/merge (HDBSCAN only)  │
         └─────────────────────────────────────────┘

SOLUTION: Users understand why items grouped!
```

---

## UI Evolution

### Week 0: Current
```
┌─────────────────────────────────┐
│ Async error handling in Node.js  │
│ 12 items • sentry, reddit        │
│ Status: new                       │
│ [Generate Plan] [Start Fix]       │
└─────────────────────────────────┘
```

### Week 1: Add Confidence Badge (30 min)
```
┌─────────────────────────────────┐
│ Async error handling in Node.js  │
│ 12 items • sentry, reddit        │
│ Status: new                       │
│ ✓ HIGH CONFIDENCE (0.82) ← NEW  │
│ [Generate Plan] [Start Fix]       │
└─────────────────────────────────┘
```

### Week 2-3: Add Exemplars (3-5 days)
```
┌─────────────────────────────────┐
│ Async error handling in Node.js  │
│ 12 items • sentry, reddit        │
│                                  │
│ Why grouped:                      │
│ • "Connection timeout in async"  │
│ • "Promise.all pool error"        │
│ • "Async/await deadlock"          │
│ ────────────────────────────────  │
│ Status: new | ✓ HIGH (0.82)      │
│ [Generate Plan] [Start Fix]       │
└─────────────────────────────────┘
```

---

## Algorithm Selection Flowchart

```
                        START
                          │
                    ┌─────▼─────┐
                    │ Pick Tier  │
                    └─────┬─────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
    TIER 1          TIER 2-3           TIER 4
   (Week 1)        (Week 2-3)        (Month 2)
        │                 │                 │
        ▼                 ▼                 ▼
   Silhouette        HDBSCAN        Two-Stage
   + Badge         + Exemplars     (Coarse+Fine)
        │                 │                 │
        ├─ Keep algo      ├─ New algorithm  ├─ Vector DB
        ├─ Add metrics    ├─ Drop outliers  ├─ DBSCAN fine
        ├─ Show score     ├─ Show examples  ├─ Auto-tune
        └─ Users happy    └─ Users very ♥   └─ Best result
```

---

## HDBSCAN vs Current Approach

```
CURRENT (Agglomerative + Threshold):

Items    ├─ Item A [similarity 0.89] ─┐
         ├─ Item B [similarity 0.88] ─┤
         ├─ Item C [similarity 0.71] ──┤ CLUSTER 1
         ├─ Item D [similarity 0.68] ──┘ (forced in)
         └─ Item E [similarity 0.15] ──→ CLUSTER 2

Problem: Item D doesn't really fit (0.68 < 0.72)
         Item E forced into new cluster despite low sim


HDBSCAN (Hierarchical Density-Based):

Items    ├─ Item A ┐
         ├─ Item B ├─ CLUSTER 1 (high density)
         ├─ Item C ┐ Exemplars: A, C (most stable)
         │         │ Soft scores: A(0.98), B(0.92)
         ├─ Item D ── NOISE (don't belong)
         └─ Item E ┐
                   └─ CLUSTER 2 (if item E joins)
                     Soft score: E(0.45) - uncertain

Benefit: Item D clearly marked as outlier
         Soft scores show uncertainty
         Exemplars show what defines cluster
```

---

## Complexity Comparison

```
Algorithm       Time        Space       Notes
────────────────────────────────────────────────
K-Means         O(nkd)      O(nk)       ← Not recommended
Agglomerative   O(n²)       O(n²)       ← Current default
DBSCAN          O(n²)       O(n)        ← Fast on large data
HDBSCAN         O(n log n)  O(n)        ← Best complexity
Affinity Prop   O(n²dI)     O(n²)       ← Very slow
Spectral        O(n³)       O(n²)       ← Slowest

For Soulcaster typical (5000 items):
─────────────────────────────────────
Current: ~3 seconds
HDBSCAN: ~1-2 seconds (faster!)
DBSCAN: ~1 second
Affinity Prop: ~30+ seconds (too slow)

n = number of items, k = clusters, d = dimensions
```

---

## Feature Checklist

```
FEATURE                   CURRENT  TIER1+  HDBSCAN  TWO-STAGE
───────────────────────────────────────────────────────────
Clustering speed          ✓        ✓       ✓        ✓
No parameter tuning       ✓        ✓       ✓        ✓
Confidence score          ✗        ✓       ✓        ✓
Outlier detection         ✗        ✗       ✓        ✓
Exemplar items           ✗        ✗       ✓        ✓
Soft scores (probability) ✗        ✗       ✓        ✓
Manual split/merge        ✗        ✗       ✓        ✓
Auto cluster count        ✗        ✗       ✓        ✓
Dendrogram visualization  ✗        (~)     ✓        ~
Audit trail               ✗        ✓       ✓        ✓
Very easy to implement    ✓        ✓       ✗        ✗

✓ = Yes, ✗ = No, ~ = Optional, (~) = Possible but hard
```

---

## Confidence Badge Colors

```
┌─────────────────────────────────────────────────┐
│ Silhouette Score   Color    Text    Explanation│
├─────────────────────────────────────────────────┤
│ 0.60 - 1.00       🟢 Green  HIGH    Items are  │
│                                      well-      │
│                                      grouped    │
├─────────────────────────────────────────────────┤
│ 0.30 - 0.60       🟡 Yellow MEDIUM  Items are  │
│                                      somewhat   │
│                                      together   │
├─────────────────────────────────────────────────┤
│ -1.0 - 0.30       🔴 Red    LOW     Items may  │
│                                      not belong │
│                                      together   │
└─────────────────────────────────────────────────┘

Example scores for Soulcaster:
───────────────────────────────
Well-matched: 0.75-0.85 (HIGH)
Normal cluster: 0.45-0.60 (MEDIUM)
Poor grouping: 0.15-0.30 (LOW)
Bad cluster: < 0.15 (VERY LOW, consider splitting)
```

---

## Timeline Recommendation

```
WEEK 1: Silhouette Scores                  (LOW RISK)
├─ Day 1-2: Implement compute_cluster_metrics()
├─ Day 3: Update models.py
├─ Day 4: Update frontend components
├─ Day 5: Test & deploy
└─ Users see confidence badges

                    ↓

WEEK 2-3: HDBSCAN                         (MEDIUM RISK)
├─ Day 1: Install hdbscan, write functions
├─ Day 2-3: Update clustering_runner.py
├─ Day 4: Update API & models
├─ Day 5-7: Build exemplar UI
└─ Users see representative examples

                    ↓

MONTH 2: Two-Stage Refinement              (HIGHER EFFORT)
├─ Week 1: Benchmark vector DB + DBSCAN
├─ Week 2: Auto-eps parameter estimation
└─ Week 3: Dashboard confidence trends

TOTAL EFFORT: ~3-4 weeks for full stack with HDBSCAN
             ~1-2 weeks for Tier 1 + Tier 2 quick wins
```

---

## Production Deployment Checklist

```
PRE-DEPLOYMENT:
  ☐ Code reviewed by 2 team members
  ☐ All tests passing (unit + integration)
  ☐ Benchmarked on production-like volume
  ☐ Silhouette scores computed for 100 real clusters
  ☐ Compare old vs new on same data
  ☐ Documented parameter changes
  ☐ Updated API docs
  ☐ Updated README/CLAUDE.md

DURING DEPLOYMENT:
  ☐ Deploy backend first (API backward compatible)
  ☐ Monitor Redis memory usage
  ☐ Monitor clustering task queue
  ☐ Check for errors in logs
  ☐ Verify silhouette scores computed correctly
  ☐ Deploy frontend in next release cycle
  ☐ Announce changes to users

POST-DEPLOYMENT:
  ☐ Monitor silhouette_score distribution
  ☐ Track outlier percentage
  ☐ Check user feedback on confidence badge
  ☐ Verify cluster count stayed reasonable
  ☐ Alert if silhouette_score < 0.2 (degradation)

ROLLBACK PLAN:
  ☐ If silhouette < 0.2: revert to previous version
  ☐ If performance issue: disable new metrics
  ☐ Document what went wrong
  ☐ Plan retry for next sprint
```

---

## Common Issues & Solutions

```
PROBLEM                 CAUSE               SOLUTION
────────────────────────────────────────────────────────
Low silhouette scores   Mixed items in      Add audit trail
(< 0.3)                 cluster              Review grouping
                                            Consider HDBSCAN

Too many clusters       Threshold too       Lower threshold
(> expected)            high (0.72)         from 0.72 to 0.65

Too few clusters        Threshold too       Raise threshold
                        low                 from 0.72 to 0.78

No exemplars showing    HDBSCAN not         Check installation:
                        installed/imported  pip install hdbscan

Slow clustering         High volume         Batch processing
(> 5 seconds)           (> 5000 items)      or reduce items

Outliers not detected   Using agglomerative Switch to HDBSCAN
                        or centroid         or use DBSCAN

Users confused by       Silhouette score    Use badge color
metrics                 raw number          (high/med/low)
```

---

## References

### Industry Examples
- Sentry: https://docs.sentry.io/product/data-management-settings/event-grouping/
- GitHub: Issue duplicate detection
- Slack: Message threading logic

### Algorithms
- [Agglomerative Clustering - scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.AgglomerativeClustering.html)
- [HDBSCAN Documentation](https://hdbscan.readthedocs.io/)
- [DBSCAN - scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html)

### Metrics
- [Silhouette Score - scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html)
- [Davies-Bouldin Index - scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.davies_bouldin_score.html)

### Papers
- HDBSCAN: "Hierarchical Density-Based Clustering" (2013)
- Agglomerative: "Elements of Statistical Learning" (2009)

---

Good luck implementing! Start with silhouette scores this week. 🚀
