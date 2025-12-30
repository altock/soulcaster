# Clustering Decision Guide for Soulcaster

## Quick Decision Tree

```
START
  |
  ├─ Priority: User Trust & Explainability?
  |  YES → HDBSCAN (comprehensive explainability)
  |        Effort: Medium | Impact: Very High
  |
  ├─ Priority: Identify Bad/Noisy Clusters?
  |  YES → DBSCAN (outlier detection)
  |        Effort: Low | Impact: High
  |
  ├─ Priority: Minimize Implementation Changes?
  |  YES → Agglomerative + Dendrogram
  |        Effort: Low | Impact: Medium
  |
  └─ Priority: Maximum Speed (10k+ items)?
      → Keep current with silhouette scores
      Effort: Very Low | Impact: Medium
```

## Implementation Difficulty Assessment

### Tier 1: "Turn on metrics" (1-2 days)
```
Current State → Add silhouette scoring
- No algorithm change
- Compute scores post-clustering
- Add badge to UI
Result: Same clusters, but with confidence indicator
```

### Tier 2: "Add dendrograms" (2-3 days)
```
Current State → Add dendrogram visualization
- Generate scipy linkage matrix alongside clustering
- Render interactive dendrogram in UI
- Allow users to "cut at height" to merge/split
Result: More understandable cluster formation
```

### Tier 3: "Switch clustering library" (3-5 days)
```
Current agglomerative → HDBSCAN
- Install hdbscan package
- Rewrite cluster_hdbscan() function
- Update API to return exemplars + soft scores
- Update UI to show exemplar items
Result: Outlier detection + representative examples
```

### Tier 4: "Two-stage refinement" (1-2 weeks)
```
Current → Vector DB (coarse) + DBSCAN (fine)
- Already partially implemented
- Add DBSCAN stage after vector DB query
- Auto-tune epsilon parameter
- Dashboard confidence trends
Result: Best accuracy + explainability + performance
```

## Impact vs. Effort Matrix

```
         HIGH
         IMPACT
           |
      HDBSCAN ★
           |
      Dendro
           |
      Silhouette ★  ←  Two-Stage
           |
           |
      -----+--------- LOW EFFORT → HIGH EFFORT
         LOW
         IMPACT

★ = Quick wins (start here)
```

## Visual: Current vs. Proposed Flow

### Current Soulcaster Clustering

```
Feedback Items (64-5000)
    ↓
Prepare texts (title + body)
    ↓
Embed via Gemini (768-dim vectors)
    ↓
Query Upstash Vector (find existing similar)
    ↓
In-memory clustering (agglomerative/centroid/vector-like)
    ├─ Cosine similarity ≥ 0.72 → same cluster
    └─ Otherwise → new cluster
    ↓
Store clusters in Redis
    ↓
Dashboard displays
    ├─ Title (from first item)
    ├─ Count
    ├─ Sources
    └─ Status (new/fixing/pr_opened)

MISSING: Why grouped? Confidence? Quality?
```

### Proposed Flow with Explainability (Tier 1)

```
Feedback Items (64-5000)
    ↓
[Same as current...]
    ↓
Store clusters in Redis
    ↓
COMPUTE QUALITY METRICS ★ NEW
    ├─ Silhouette score (-1 to 1)
    ├─ Per-item silhouette
    └─ Identify outliers (< 0.25)
    ↓
Store metrics with cluster
    ↓
Dashboard displays
    ├─ Title
    ├─ Count
    ├─ Sources
    ├─ Status
    ├─ Confidence badge ★ "High/Medium/Low"
    ├─ "Why grouped?" explanation ★
    └─ Low-confidence items flagged ★

GAIN: User confidence + understanding
```

### Proposed Flow with HDBSCAN (Tier 3)

```
Feedback Items (64-5000)
    ↓
[Same as current...]
    ↓
RUN HDBSCAN ★ REPLACES agglomerative
    ├─ Hierarchical density-based
    ├─ Auto cluster count
    ├─ Returns noise points (-1) ★
    ├─ Returns exemplars ★
    └─ Returns soft scores ★
    ↓
Store in Redis with new fields:
    ├─ exemplar_ids
    ├─ soft_scores
    └─ outlier_count
    ↓
Dashboard displays
    ├─ Title (from exemplar)
    ├─ Representative items ★ (2-3 exemplars)
    ├─ Soft confidence per item ★
    ├─ Outliers separated ★
    ├─ Edit: "Split cluster" ★
    └─ Edit: "Merge clusters" ★

GAIN: Exemplary transparency + manual refinement
```

## Dashboard UI Mockup

### Current Cluster Card

```
┌──────────────────────────────────────────┐
│ Error handling in async functions        │ (title)
│ Cluster of 12 feedback items             │ (count)
│ Sentry (8) Reddit (4)                    │ (sources)
│ [new] [pr_opened] [failing]              │ (status)
└──────────────────────────────────────────┘
```

### With Tier 1 (Confidence Badge)

```
┌──────────────────────────────────────────┐
│ Error handling in async functions        │
│ Cluster of 12 feedback items             │
│ Sentry (8) Reddit (4)                    │
│ Status: new | ✓ High Confidence (0.78)  │ ← NEW
│                                          │
│ [Info] Why grouped? / [Explain]          │ ← NEW
└──────────────────────────────────────────┘
```

### With Tier 3 (Exemplars)

```
┌──────────────────────────────────────────┐
│ Error handling in async functions        │
│ Cluster of 12 feedback items             │
│                                          │
│ Representative Examples:                 │ ← NEW
│ 1. "Timeout in async/await Promise"      │
│    From: Sentry | Confidence: 92%        │
│ 2. "Help: my async function hangs"       │
│    From: Reddit | Confidence: 88%        │
│                                          │
│ Sentry (8) Reddit (4) | ✓ High (0.78)   │
│ Status: new | [Split] [Edit] [Fix]      │
└──────────────────────────────────────────┘
```

## Algorithm Selection by Feature

### Do you need...

| Feature | Current | +Silhouette | +HDBSCAN | +DBSCAN |
|---------|---------|-------------|----------|---------|
| Confidence score? | ❌ | ✅ | ✅ | ❌ |
| Outlier detection? | ❌ | ❌ | ✅ | ✅ |
| Exemplar items? | ❌ | ❌ | ✅ | ❌ |
| Hierarchy/dendrogram? | ❌ | ❌ | ✅ | ❌ |
| Soft probabilities? | ❌ | ❌ | ✅ | ❌ |
| Auto cluster count? | ❌ | ❌ | ✅ | ✅ |
| No parameter tuning? | ✅ | ✅ | ✅ | ❌ |
| Handles 10k+ items? | ✅ | ✅ | ✅ | ✅ |
| Can merge/split UI? | ❌ | ❌ | ✅ | ❌ |
| Implementation ease | — | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

### Recommended Combinations

#### Option A: "Trust Builder" (7 days)
```
Agglomerative + Silhouette Scores + Dendrogram
├─ Day 1-2: Add silhouette metric computation
├─ Day 3-4: Generate linkage matrix for dendrograms
├─ Day 5-7: Build interactive dendrogram UI
└─ Result: Same algorithm, much more understandable
```

#### Option B: "Best in Class" (10 days)
```
HDBSCAN + Exemplars + Soft Scores + Manual Edits
├─ Day 1-2: Install hdbscan, write cluster_hdbscan()
├─ Day 3-4: Update models to store exemplars/soft scores
├─ Day 5-7: Update API endpoints
├─ Day 8-10: Build exemplar UI + split/merge dialogs
└─ Result: Most explainable, handles outliers
```

#### Option C: "Safe Upgrade" (4 days)
```
Agglomerative + Silhouette + Add DBSCAN option
├─ Day 1: Add silhouette scoring
├─ Day 2: Implement DBSCAN clustering function
├─ Day 3: Add method selector in clustering settings
├─ Day 4: A/B test both approaches
└─ Result: Keep current, test alternative with live data
```

## Production Readiness Checklist

### Before Switching Algorithms

- [ ] Tested on production data volume (5k-10k items)
- [ ] Compared clustering quality with current approach (silhouette vs. old threshold)
- [ ] Verified performance (<5 seconds for 5k items)
- [ ] Added monitoring: cluster count distribution, outlier percentage
- [ ] Documented how to rollback if clustering degrades
- [ ] Trained team on new metrics/interpretability
- [ ] Updated API docs with new response fields
- [ ] Dashboard changes tested at different screen sizes
- [ ] No regression in accuracy metrics (if you have labels)

### Before Shipping Explainability UI

- [ ] Silhouette score computed for all clusters
- [ ] Confidence badge colored correctly (>0.6=green, etc.)
- [ ] "Why grouped" explanation is clear to non-ML users
- [ ] Exemplar items display first in cluster view
- [ ] Soft score percentages shown as "X% confidence"
- [ ] Users can see which items are low-confidence
- [ ] Mobile-responsive confidence badges
- [ ] Tooltip explains what silhouette score means

## Testing Strategy

### Unit Tests

```python
def test_silhouette_score_high_quality_cluster():
    """Very similar items should have high silhouette."""
    embeddings = np.array([
        [1, 0, 0],
        [1, 0, 0],  # Nearly identical
        [0, 1, 0],
        [0, 1, 0],  # Different from above
    ], dtype=np.float32)
    labels = np.array([0, 0, 1, 1])

    score = silhouette_score(embeddings, labels)
    assert score > 0.7  # Should be very confident

def test_hdbscan_identifies_outliers():
    """Isolated item should be marked as noise."""
    embeddings = np.array([
        [1, 0],
        [1, 0],  # Cluster A
        [0, 1],
        [0, 1],  # Cluster B
        [10, 10],  # Outlier
    ], dtype=np.float32)

    clusterer = hdbscan.HDBSCAN(min_cluster_size=2)
    labels = clusterer.fit_predict(embeddings)

    assert labels[-1] == -1  # Last item marked as noise
```

### Integration Tests

```python
def test_clustering_with_quality_metrics(sample_feedback):
    """End-to-end: items → clusters → metrics."""
    result = cluster_issues_with_quality(
        issues=sample_feedback,
        method="agglomerative"
    )

    assert "silhouette_score" in result
    assert -1 <= result["silhouette_score"] <= 1
    assert len(result["outlier_indices"]) <= len(sample_feedback)

    # Verify audio trail can be generated
    audit = generate_audit_trail(result["labels"], sample_feedback)
    assert len(audit) > 0
```

### Manual Testing Checklist

```
[ ] Run clustering on 100 real feedback items
[ ] Verify silhouette scores are reasonable (typically 0.3-0.8)
[ ] Check that very similar items have high confidence
[ ] Verify mixed clusters get medium/low confidence
[ ] Test edge cases:
    [ ] Single item → no cluster
    [ ] Two identical items → high confidence
    [ ] 10 items of 10 different topics → low confidence
[ ] Test HDBSCAN:
    [ ] Noise points actually separated
    [ ] Exemplars are representative
    [ ] Soft scores range 0-1
```

## Monitoring & Alerts

### Metrics to Track

```
Per clustering job:
├─ cluster_count (should be 2-20 for 64 items, 5-50 for 1000 items)
├─ avg_cluster_size (watch for 1-2 = bad threshold)
├─ avg_silhouette_score (track over time, target >0.5)
├─ outlier_percentage (if using HDBSCAN, expect 5-15%)
├─ processing_time (should be <5s for 5k items)
└─ failed_clusters (items in clusters with score <0.2)

Alerts:
├─ silhouette_score < 0.3 (cluster quality degrading?)
├─ outlier_percentage > 30% (too many noise points?)
├─ processing_time > 10s (performance regression?)
└─ cluster_count > expected (clustering is too fine?)
```

## Rollback Plan

If new clustering algorithm doesn't work:

```
1. Identify problem:
   - Silhouette score <0.2? (low quality)
   - Too many outliers? (>25%)
   - Slow? (>10s for 5k items)

2. Immediate rollback:
   - Revert clustering_runner.py to use agglomerative
   - Set CLUSTERING_METHOD=agglomerative in env
   - Clear Redis cache: DEL clusters:*

3. Investigate:
   - Compare cluster results on 1000-item test set
   - Compute silhouette for both old/new
   - Check parameter values (eps, min_samples, etc.)

4. Retry:
   - Adjust parameters and test again
   - Or switch to different algorithm
```

## Success Criteria

### For Tier 1 (Silhouette Scores)
- [ ] All clusters have silhouette score (-1 to 1)
- [ ] Scores visible in API responses
- [ ] UI shows confidence badge based on score
- [ ] Users understand what score means
- **Target**: 2x increase in cluster detail page views

### For Tier 2 (Dendrograms)
- [ ] Dendrograms generate for clusters >3 items
- [ ] Visualization loads in <500ms
- [ ] Users can understand merge history
- **Target**: Users "get why items grouped" without asking

### For Tier 3 (HDBSCAN)
- [ ] Exemplars computed and stored
- [ ] Soft scores tracked per item
- [ ] API returns all new fields
- [ ] UI shows representative examples
- [ ] Manual split/merge functionality works
- **Target**: 10% improvement in clustering accuracy (if you have labels)

### For Tier 4 (Two-Stage)
- [ ] DBSCAN fine-tuning works with vector DB coarse
- [ ] Outlier detection improves spam filtering
- [ ] Parameters auto-tune based on data distribution
- [ ] Dashboard shows clustering confidence trends
- **Target**: Reduce bad cluster complaints by 50%

---

## FAQ

**Q: Should we switch from agglomerative to HDBSCAN now?**
A: Start with Tier 1 (silhouette scores). If users understand silhouette badge, upgrade to HDBSCAN. Don't skip both.

**Q: Does HDBSCAN work with cosine similarity?**
A: Yes. Use `metric="cosine"` in HDBSCAN. Internally converts to cosine distance.

**Q: What if HDBSCAN creates too many clusters?**
A: Increase `min_cluster_size` (default 2). Try 3-5 for more aggressive merging.

**Q: Can we use both silhouette AND exemplars?**
A: Yes! HDBSCAN gives both. Exemplars show "why", silhouette shows "confidence".

**Q: Is exemplar ranking deterministic?**
A: HDBSCAN's exemplars are deterministic given same data + parameters. Good for reproducibility.

**Q: How much slower is HDBSCAN than agglomerative?**
A: Roughly 2-3x slower on 1000 items, but still <2s. On 5000 items: comparable speed due to better complexity.

**Q: What if we don't like the outlier detection?**
A: Set `allow_single_cluster=True` to force all items into clusters (no noise). But loses outlier benefit.

**Q: Can users reject/fix clusters?**
A: Yes. With HDBSCAN exemplars, add "Split" and "Merge" buttons (tier 3+).

**Q: Should we show raw silhouette scores or badge?**
A: Badge for UX. Raw score in API for users who want details. Hover tooltip shows both.

---

## Quick Start Guide

### Implement Tier 1 (Today)

1. Copy silhouette code from CLUSTERING_RESEARCH.md Part 5
2. Add to `cluster_issues_with_quality()` in clustering.py
3. Call from clustering_runner.py
4. Store silhouette_score in IssueCluster model
5. Add confidence_badge field to frontend

**Time**: 2-4 hours
**Value**: Users see confidence, understand grouping quality

### Implement Tier 3 (This Week)

1. `pip install hdbscan`
2. Copy cluster_hdbscan() code from CLUSTERING_RESEARCH.md
3. Update models.py with exemplar_ids, soft_scores fields
4. Update API routes to return new fields
5. Build exemplar view in dashboard

**Time**: 2-3 days
**Value**: Outlier detection + representative items

Good luck! 🚀
