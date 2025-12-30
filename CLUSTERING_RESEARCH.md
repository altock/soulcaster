# Clustering Explainability & Algorithm Research for Soulcaster

## Executive Summary

This research examines:
1. **Part 1**: Best practices for making clustering decisions interpretable to users
2. **Part 2**: Alternative clustering algorithms and their suitability for Soulcaster

### Key Findings

**Current State**: Soulcaster uses vector-database-based clustering with cosine similarity threshold (0.72) and three strategies (agglomerative, centroid, vector-like). The UI currently shows cluster counts, sources, and status but lacks explainability of *why* items are grouped.

**Recommendations**:
- **Explainability**: Add similarity scores, audit trails, and representative items to clusters
- **Algorithm**: Consider two-stage clustering (Vector DB + DBSCAN) for better interpretability and outlier handling
- **Metrics**: Display silhouette scores as simple confidence indicators (not technical jargon)

---

## Part 1: Clustering Explainability Best Practices

### 1.1 Industry Approaches to Clustering Explanation

#### Sentry Error Grouping
Sentry uses a multi-layer approach:
- **Fingerprinting**: Stack trace → fingerprint → issue group (deterministic)
- **AI Enhancement**: Semantic similarity on top of fingerprints to catch similar errors with different stacks
- **Transparency**: Shows "Event grouping information" at bottom of each issue (why grouped, fingerprint algorithm used)
- **Confidence**: Users can see if AI adjusted grouping vs. deterministic grouping

**What Soulcaster can learn**: Users trust explanations when they're simple (fingerprint) + supplemented (AI layer). Transparency breeds confidence.

#### GitHub Issue Duplicate Detection
- Marks potential duplicates with confidence levels
- Links to similar issues with similarity reasoning
- Shows only when high confidence (>80%)

#### Slack Message Threading
- Simple: first message defines thread
- Transparency: users can see thread root and understand grouping
- Manual override: drag/rethreading available

**Common pattern**: Simplicity + Transparency + Manual Override = User Trust

### 1.2 Metrics for Cluster Quality

#### For Users (Simple Metrics)

**Silhouette Score** (-1 to +1)
- **Meaning**: How well does each item fit its cluster vs. other clusters?
- **Range**: -1 (wrong cluster) → 0 (border) → +1 (perfect fit)
- **User-friendly presentation**: Color-coded confidence badge
  - Green (0.6-1.0): "Very confident"
  - Yellow (0.3-0.6): "Moderately confident"
  - Red (-1-0.3): "Low confidence, might need review"
- **Computation**: O(n²) but fast for typical Soulcaster volumes (64-5000 items)

**Davies-Bouldin Index** (lower is better, 0-∞)
- **Meaning**: Ratio of within-cluster tightness to between-cluster separation
- **Easier to explain**: "Separation score: 0.5" (lower numbers mean better separation)
- **User-friendly presentation**: Simple "Cluster Quality: Good/Fair/Poor"

#### For Developers (Detailed Metrics)

**Calinski-Harabasz Index** (higher is better)
- Ratio of between-cluster to within-cluster variance
- Good for comparing algorithms on same data

**Dunn Index** (higher is better)
- Minimum separation / maximum diameter
- Detects well-separated, compact clusters

**Intra-cluster similarity** (average cosine sim within cluster)
- Shows how similar items are within their cluster
- Range: 0-1 (1 = identical)

### 1.3 UI Patterns for Cluster Explanation

#### Pattern 1: Similarity Badges (Confidence Indicators)
```
Cluster Card View:
┌─────────────────────────────────────────┐
│ Error handling in async functions       │ ← Title
│ Cluster of 12 feedback items           │ ← Count
│ Sources: sentry (8), reddit (4)       │ ← Sources
│ ✓ High confidence (0.78)              │ ← Silhouette score badge
└─────────────────────────────────────────┘
```

**Implementation**:
- Green check (0.6+): items belong together
- Yellow caution (0.3-0.6): borderline grouping
- Red warning (0-0.3): consider splitting
- Tooltip: "This cluster has similarity score 0.78. Items are well-grouped."

#### Pattern 2: Exemplar-Based View (Representative Items)
Show 2-3 most representative items from each cluster:
```
Cluster: "Database connection timeout"
├─ Representative Item #1 (most central)
│  └─ Title: "Connection pool exhaustion with async transactions"
│  └─ Source: Sentry, Confidence: 0.92
├─ Representative Item #2
│  └─ Title: "Timeout waiting for database connection"
│  └─ Source: Reddit, Confidence: 0.87
└─ Other 8 items...
```

**Why it works**: Users immediately understand cluster theme from exemplars. No need for averages/summaries.

#### Pattern 3: Audit Trail / Clustering Decision Path
```
Why were these items grouped together?

1. Item A (Sentry) — "timeout connecting to db"
2. Item B (Reddit) — "db pool exhausted"
   └─ Similarity to Item A: 0.89 ✓ (joined)
3. Item C (Sentry) — "connection refused on pool"
   └─ Similarity to Item A: 0.92 ✓ (joined)
4. Item D (Github) — "network error"
   └─ Similarity to nearest cluster: 0.45 ✗ (new cluster)
```

**Implementation**:
- Show first 1-2 items that seeded cluster
- Show next 2-3 items and why they joined
- Show rejected items if similarity score is publicly visible

#### Pattern 4: Confidence Timeline
For clusters evolving over time:
```
Cluster Stability Over Time:
Confidence: ████████░░ 0.82 (was 0.71 yesterday)
Last Updated: 2 hours ago (5 new items added)
Size: 12 items (was 7 yesterday)
```

Shows:
- Current silhouette score
- Trend (improving/degrading)
- Recent activity

### 1.4 Handling Bad Clusters

#### Detection
**Bad cluster indicators**:
- Silhouette score < 0.3 (low confidence)
- Mixed sources with contradictory metadata
- Very large clusters (>100 items) with low silhouette score
- High within-cluster variance in key metadata (e.g., error types)

#### User Actions
1. **"Explain This Cluster"** button → Shows audit trail (Pattern 3)
2. **"Split This Cluster"** → User selects items to move out
3. **"Merge Clusters"** → Dashboard suggests merges for very similar clusters
4. **"Mark as Noise"** → Items that don't belong in any cluster

#### Implementation in Dashboard
```
Alert if silhouette score < 0.3:
┌──────────────────────────────────────┐
│ ⚠️  Low Confidence Cluster (0.28)    │
│ This cluster may contain items that  │
│ don't belong together. Review the    │
│ items or manually split if needed.   │
│ [Learn More] [Explain] [Split]       │
└──────────────────────────────────────┘
```

### 1.5 Comparison with Existing Soulcaster UI

**Current Dashboard Shows**:
- Cluster title (from first item)
- Summary (from first item)
- Item count
- Source badges
- Status (new/fixing/pr_opened/failed)
- GitHub repo link

**Missing for Explainability**:
- WHY items grouped together
- Confidence/quality of grouping
- Representative examples beyond title/summary
- Ability to understand edge cases (why not item X?)

**Recommended Additions** (in order of impact):
1. Silhouette score badge on cluster cards (low effort, high value)
2. "Why grouped" tooltip on hover (medium effort)
3. Expandable audit trail on cluster detail page (medium effort)
4. Exemplar items view (shows top 3 most representative) (medium effort)
5. Manual cluster split/merge UI (high effort, moderate value)

---

## Part 2: Clustering Algorithm Alternatives

### 2.1 Current Approach Analysis

**Method**: Vector DB (Upstash) + in-memory agglomerative/centroid/vector-like clustering

**Strengths**:
- Fast for typical volumes (64-5000 items)
- Interpretable threshold (0.72 cosine similarity)
- No tuning of K or epsilon needed
- Works well for text embeddings

**Weaknesses**:
- Eventually-consistent vector DB (addressed with two-phase approach)
- Fixed threshold (0.72) regardless of data distribution
- No outlier detection (noise points forced into clusters)
- Agglomerative clustering is O(n²) memory/time at scale
- No exemplars or representativeness ranking
- Hard to explain why threshold is 0.72

### 2.2 Algorithm Comparison Matrix

| Aspect | Agglomerative | DBSCAN | HDBSCAN | Spectral | Affinity Prop | Vector-Like |
|--------|---------------|--------|---------|----------|--------------|------------|
| **Speed (1000 items)** | Medium | Fast | Medium | Slow | Slow | Fast |
| **Outlier Handling** | No (forces all in) | Yes (noise points) | Yes (soft assignment) | No | No | No |
| **Interpretability** | High (tree) | High (eps/min_samples) | Highest (soft scores) | Low | Medium (exemplars) | Medium (threshold-based) |
| **Parameter Tuning** | None (dist_thresh) | Medium (eps, min_samples) | Low (min_cluster_size) | Hard | Hard (preference, damping) | None |
| **Scalability >10k** | Poor | Good | Good | Poor | Poor | Good |
| **Exemplar Support** | No | No | Yes (cluster backbone) | No | Yes (explicit) | No |
| **Hierarchy/Dendrogram** | Yes | No | Yes | No | No | No |
| **Works w/ Cosine** | Yes | Yes (metric) | Yes (metric) | Yes | Yes | Yes |
| **Cluster Shape** | Any | Arbitrary | Arbitrary | Any | Globular | Any |

### 2.3 Detailed Algorithm Recommendations

#### Option A: Hierarchical (Agglomerative) - Keep Current, Add Dendrogram
**Current**: Already using this

**Enhancement**: Generate dendrogram for clusters with >3 items
- Shows merge history: "Items 1,2 merged at similarity 0.92, then merged with 3 at 0.85, then 4 at 0.78"
- User can visualize cluster formation
- Can implement "merge level slider" to split clusters

**Python**:
```python
from sklearn.cluster import AgglomerativeClustering
from scipy.cluster.hierarchy import dendrogram, linkage

# Already computed clustering
clustering = AgglomerativeClustering(
    n_clusters=None,
    linkage="average",
    distance_threshold=1-0.72,
    metric="cosine"
)
labels = clustering.fit_predict(embeddings)

# For visualization, also save linkage matrix
linkage_matrix = linkage(embeddings, method="average", metric="cosine")
```

**Pros**:
- No change to existing pipeline
- Dendrogram adds explainability
- Users see merge hierarchy

**Cons**:
- O(n²) memory scaling limits 10k+ items
- Still forces outliers into clusters

#### Option B: DBSCAN - For Outlier Detection
**When to use**: High-volume ingestion (>5000 items) with need to identify "noise" feedback

**How it works**:
- Density-based: clusters are dense regions
- Parameters:
  - `eps`: distance threshold (like cosine distance 1-0.72 = 0.28)
  - `min_samples`: minimum points to form cluster (suggest 2-3)
- Returns: cluster labels + noise points (-1)

**Python**:
```python
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances

# Convert cosine similarity to distance
distances = 1 - embeddings  # Cosine distance
clustering = DBSCAN(eps=0.28, min_samples=2, metric="precomputed")
labels = clustering.fit_predict(distances)

# -1 = noise (outliers)
noise_count = (labels == -1).sum()
cluster_count = len(set(labels)) - (1 if -1 in labels else 0)
```

**Pros**:
- Identifies outliers (noise points)
- Interpretable parameters (eps threshold)
- Fast for large datasets
- Works well for arbitrary shapes

**Cons**:
- Parameter tuning can be tricky (eps/min_samples)
- Less deterministic than threshold-based
- No exemplars by default

#### Option C: HDBSCAN - Best for Interpretability
**Best choice for Soulcaster** if interpretability is priority

**How it works**:
- Hierarchical + density-based
- Produces soft clustering: probability of membership
- Returns exemplar points (cluster backbone)
- Produces stability scores per point

**Python**:
```python
import hdbscan
import numpy as np

# Convert to distance matrix
distances = 1 - embeddings  # Cosine distance (precompute or use metric)

clusterer = hdbscan.HDBSCAN(
    min_cluster_size=2,
    metric="cosine",
    cluster_selection_epsilon=0.28,
)
labels = clusterer.fit_predict(embeddings)

# Get probabilities (soft assignments)
soft_clusters = clusterer.soft_clusters_  # [n_samples, n_clusters]

# Get exemplars (most representative points)
exemplars = clusterer.exemplars_  # List of lists: most stable points per cluster

# Get stability scores
stability = clusterer.cluster_persistence_  # How stable is each cluster
outliers = labels == -1  # Noise points

# Per-point probability
probs = np.max(soft_clusters, axis=1)  # Probability for assigned cluster
```

**Pros**:
- **Exemplars**: Get 1-5 most representative items per cluster
- **Soft scores**: Probability-based membership (explainable to users)
- **Outlier detection**: Noise points identified
- **Hierarchical**: Dendrogram shows cluster structure
- **Less tuning**: min_cluster_size is intuitive
- **Stability**: Can see which items are solidly in cluster vs. borderline

**Cons**:
- Slower for very large datasets (but still O(n log n))
- Requires package install (not in standard sklearn)
- Cluster count determined automatically (can vary)

**Soulcaster Integration**:
```python
# In clustering_runner.py, replace agglomerative option

import hdbscan

def cluster_hdbscan(embeddings: np.ndarray,
                    min_cluster_size: int = 2,
                    cluster_epsilon: float = 0.28) -> dict:
    """HDBSCAN clustering with soft assignments and exemplars."""
    if embeddings.size == 0:
        return {"labels": np.array([], dtype=int), "clusters": [], "singletons": []}

    if len(embeddings) < min_cluster_size:
        return {"labels": np.array([0], dtype=int), "clusters": [[0]], "singletons": []}

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric="cosine",
        cluster_selection_epsilon=cluster_epsilon,
    )
    labels = clusterer.fit_predict(embeddings)

    # Extract results
    clusters = []
    singletons = []
    exemplars = {}
    soft_scores = {}

    for label in set(labels):
        if label == -1:  # Noise
            singletons.extend(np.where(labels == label)[0].tolist())
        else:
            idxs = np.where(labels == label)[0].tolist()
            if len(idxs) >= min_cluster_size:
                clusters.append(idxs)
                # Store exemplars for this cluster
                exemplars[label] = clusterer.exemplars_.get(label, [])
                # Store soft scores
                soft_scores[label] = np.max(clusterer.soft_clusters_[idxs], axis=1)
            else:
                singletons.extend(idxs)

    return {
        "labels": labels,
        "clusters": clusters,
        "singletons": singletons,
        "exemplars": exemplars,  # NEW: most representative items
        "soft_scores": soft_scores,  # NEW: probability per item
        "outliers": (labels == -1).sum(),  # NEW: noise count
    }
```

#### Option D: Two-Stage Approach (Vector DB + Local Clustering)
**Recommended hybrid approach** for production

**Architecture**:
1. **Stage 1**: Vector DB (Upstash) does coarse ANN search
   - Each item queries vector DB for top-20 similar existing items
   - Fast, leverages existing infrastructure

2. **Stage 2**: Local clustering of candidates
   - Within each batch, apply DBSCAN or agglomerative
   - Compares batch items against found neighbors
   - Produces more interpretable clusters

**Benefits**:
- Combines speed of vector DB with interpretability of local algorithm
- Natural fallback to new clusters if no vector DB matches
- Can apply different clustering algorithm per "search result group"

**Soulcaster Implementation** (already partially implemented!):
```python
# In clustering_runner.py _run_vector_clustering

def cluster_with_two_stage(
    items: List[FeedbackItem],
    project_id: str,
) -> dict:
    """
    Two-stage clustering:
    1. Vector DB query for coarse grouping
    2. Local DBSCAN for fine-grained clustering
    """
    vector_store = VectorStore()
    embeddings = embed_texts_gemini(prepare_texts(items))

    # Stage 1: Get candidates from vector DB
    candidates_per_item = {}
    for i, item in enumerate(items):
        similar = vector_store.find_similar(
            embedding=embeddings[i],
            project_id=project_id,
            top_k=20,
        )
        candidates_per_item[str(item.id)] = similar

    # Stage 2: Apply DBSCAN to batch + candidates
    # Build distance matrix: batch items vs. batch + existing candidates
    batch_size = len(items)

    from sklearn.cluster import DBSCAN
    clustering = DBSCAN(eps=0.28, min_samples=2, metric="cosine")
    labels = clustering.fit_predict(embeddings)

    # Now labels incorporate both batch similarity AND
    # implicit vector DB suggestions
    return process_cluster_labels(items, labels, candidates_per_item)
```

**Current state**: Already doing this in `_run_vector_clustering()` - queries vector DB then does in-memory comparison.

#### Option E: Affinity Propagation - Exemplar-Explicit
**When to use**: If exemplar ranking is key feature

**How it works**:
- Finds "exemplars" (representative items) iteratively
- Each point sends messages about how good it is as exemplar
- Converges to best exemplars + assignments

**Python**:
```python
from sklearn.cluster import AffinityPropagation

# Compute similarity matrix (cosine)
similarity = embeddings @ embeddings.T  # Dot product on L2-normalized

ap = AffinityPropagation(affinity="precomputed", damping=0.9)
labels = ap.fit_predict(similarity)

# Get exemplars
exemplar_indices = ap.cluster_centers_indices_  # Indices of exemplar points
```

**Pros**:
- Explicit exemplars (most representative item in each cluster)
- No need to specify K (emerges from data)
- Interpretable: "Cluster 1 is exemplified by Item #5"

**Cons**:
- Slow for >1000 items (O(n²) both in time and space)
- Hard to tune preference parameter
- Assumes relatively globular clusters

**Not recommended** for Soulcaster (volume/speed issues)

### 2.4 Algorithm Recommendations by Use Case

#### Use Case 1: Typical Session (64-300 items)
**Recommended**: Keep current agglomerative OR switch to HDBSCAN
- Both work well
- HDBSCAN adds soft scores + exemplars
- Agglomerative already cached and stable

**Decision**: Upgrade agglomerative with dendrogram visualization

#### Use Case 2: High Volume Ingestion (>1000 items, sudden spikes)
**Recommended**: DBSCAN or HDBSCAN
- Need outlier detection to avoid spam clusters
- Fixed threshold (0.72) becomes problematic
- Parameters adapt to data density

**Decision**: Add DBSCAN as option with `eps_auto` parameter estimation

#### Use Case 3: Production + Maximum Explainability
**Recommended**: HDBSCAN + exemplars + soft scores
- Best explainability: "Why item X in cluster Y?" → soft score
- Best outlier handling: noise points separated
- Best UI story: exemplars show cluster theme

**Decision**: Implement HDBSCAN as new default method

### 2.5 Implementation Roadmap

#### Phase 1: Add Explainability to Current Approach (Week 1)
1. Compute silhouette scores for all clusters
2. Add confidence badge to frontend (green/yellow/red)
3. Show audit trail on cluster detail page
4. Identify outlier candidates (low silhouette score)

**Code**:
```python
from sklearn.metrics import silhouette_samples, silhouette_score

def compute_cluster_quality(embeddings: np.ndarray, labels: np.ndarray) -> dict:
    """Compute explainability metrics."""
    if len(set(labels)) == 1:  # Single cluster
        return {"silhouette": 0.0, "outlier_indices": []}

    # Global silhouette score
    silhouette_avg = silhouette_score(embeddings, labels)

    # Per-sample scores
    sample_scores = silhouette_samples(embeddings, labels)

    # Identify low-confidence items
    outlier_threshold = 0.2
    outlier_indices = np.where(sample_scores < outlier_threshold)[0]

    return {
        "silhouette": silhouette_avg,
        "sample_scores": sample_scores.tolist(),
        "outlier_indices": outlier_indices.tolist(),
        "confidence_badge": "high" if silhouette_avg > 0.6 else "medium" if silhouette_avg > 0.3 else "low",
    }
```

#### Phase 2: Switch to HDBSCAN (Week 2-3)
1. Install `hdbscan` package
2. Implement new clustering method
3. Store exemplars in IssueCluster model
4. Add soft scores to FeedbackItem
5. Update frontend to show exemplars

**Model changes**:
```python
class IssueCluster(BaseModel):
    # ... existing fields ...
    silhouette_score: Optional[float] = None
    exemplar_ids: Optional[List[str]] = None  # Most representative item IDs
    soft_scores: Optional[Dict[str, float]] = None  # Item ID -> probability
    outlier_count: Optional[int] = None
```

#### Phase 3: Two-Stage with DBSCAN Fine-Tuning (Week 4)
1. Benchmark DBSCAN vs HDBSCAN on production data
2. Implement auto-eps estimation based on data distribution
3. Add "confidence" column to cluster list view

---

## Part 3: Comprehensive Comparison Table

### Summary Comparison for Soulcaster

| Feature | Current | HDBSCAN | DBSCAN | Agglom+Dendro |
|---------|---------|---------|--------|--------------|
| **Outlier Detection** | No | Yes (soft) | Yes (hard) | No |
| **Explainability Score** | 2/5 | 5/5 | 3/5 | 4/5 |
| **Implementation Effort** | - | Medium | Low | Low |
| **Performance (5k items)** | 2-3s | 1-2s | 1s | 2-3s |
| **Cluster Count Auto?** | Manual threshold | Auto | Auto | Manual threshold |
| **Exemplars** | None | Yes | None | None |
| **Soft Scores** | None | Yes | None | None |
| **Parameter Tuning** | None | Low | Medium | None |
| **UI Friendliness** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## Part 4: Recommended Implementation Plan

### Short Term (1-2 weeks): Add Explainability to Current Code

**Goal**: Make existing agglomerative clustering transparent to users without algorithm change

1. **Compute Silhouette Scores** (backend)
   - Add metric computation to `cluster_issues()` function
   - Store in Redis alongside cluster data

2. **Update API** (backend)
   - Endpoint: `GET /clusters/{id}` returns new fields:
     ```json
     {
       "id": "...",
       "silhouette_score": 0.75,
       "confidence_badge": "high",
       "explanation": "12 items grouped by similarity (cosine 0.72+)"
     }
     ```

3. **Frontend Changes** (dashboard)
   - Add confidence badge next to status
   - Add expandable "Why grouped?" section
   - Show audit trail: "Item 1 created cluster, Item 2 joined (0.89), Item 3 joined (0.84)..."

**Effort**: 1-2 days of development

### Medium Term (2-4 weeks): Migrate to HDBSCAN

**Goal**: Better outlier detection + exemplar support

1. **Install package**: `pip install hdbscan`
2. **Implement clustering function** (see code above)
3. **Update storage model** to include exemplars and soft scores
4. **Update API responses** with new fields
5. **Update UI** to show exemplars as "Representative Examples"

**Effort**: 3-5 days of development + 1 day testing

### Long Term (1-2 months): Two-Stage Refinement

**Goal**: Leverage vector DB for coarse grouping, DBSCAN for fine-grained refinement

1. **Benchmark current vs. alternative approaches** on production data
2. **Implement auto-eps** parameter estimation
3. **Add user feedback loop**: "Did we group these correctly?" → improve threshold
4. **Dashboard**: "Cluster confidence" trending over time

**Effort**: 1-2 weeks

---

## Part 5: Code Examples for Top 2 Recommendations

### Recommendation 1: Add Silhouette Score to Current Approach

**File: `backend/clustering.py`**

```python
from sklearn.metrics import silhouette_samples, silhouette_score

def cluster_issues_with_quality(
    issues: Iterable[dict],
    method: Literal["agglomerative", "centroid", "vector_like"] = DEFAULT_METHOD,
    sim_threshold: float = DEFAULT_SIM_THRESHOLD,
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    truncate_body_chars: int = DEFAULT_TRUNCATE_BODY_CHARS,
    embed_fn=embed_texts_gemini,
) -> dict:
    """
    Cluster issues and compute quality metrics.

    Returns dict with additional keys:
    - silhouette_score: float [-1, 1]
    - sample_silhouettes: List[float] (per-sample scores)
    - outlier_indices: List[int] (low confidence items)
    """
    # Run existing clustering
    result = cluster_issues(
        issues=issues,
        method=method,
        sim_threshold=sim_threshold,
        min_cluster_size=min_cluster_size,
        truncate_body_chars=truncate_body_chars,
        embed_fn=embed_fn,
    )

    labels = result["labels"]
    embeddings = np.asarray([embed_fn([text])[0] for text in result["texts"]])

    # Compute quality metrics
    if len(set(labels)) == 1:
        # Single cluster or all noise
        silhouette_avg = 0.0
        sample_scores = np.zeros(len(labels))
    else:
        silhouette_avg = silhouette_score(embeddings, labels, metric="cosine")
        sample_scores = silhouette_samples(embeddings, labels, metric="cosine")

    # Identify low-confidence items
    outlier_threshold = 0.25
    outlier_indices = np.where(sample_scores < outlier_threshold)[0].tolist()

    result.update({
        "silhouette_score": float(silhouette_avg),
        "sample_silhouettes": sample_scores.tolist(),
        "outlier_indices": outlier_indices,
        "confidence_badge": "high" if silhouette_avg > 0.6 else "medium" if silhouette_avg > 0.3 else "low",
    })

    return result
```

**File: `backend/models.py`**

```python
class IssueCluster(BaseModel):
    """Represents a cluster of related feedback items."""

    id: str
    project_id: Union[str, UUID]
    title: str
    summary: str
    feedback_ids: List[str]
    status: str
    created_at: datetime
    updated_at: datetime
    centroid: Optional[List[float]] = Field(default=None, alias="embedding_centroid")
    github_branch: Optional[str] = None
    github_pr_url: Optional[str] = None
    error_message: Optional[str] = None
    issue_title: Optional[str] = None
    issue_description: Optional[str] = None
    github_repo_url: Optional[str] = None
    sources: Optional[List[str]] = None

    # NEW: Explainability fields
    silhouette_score: Optional[float] = None  # Confidence: -1 to 1
    confidence_badge: Optional[Literal["high", "medium", "low"]] = None  # UI label
    low_confidence_item_ids: Optional[List[str]] = None  # Items with silhouette < 0.25
```

**File: `backend/clustering_runner.py`**

```python
def _build_cluster(item_group: List[FeedbackItem],
                   silhouette_score: Optional[float] = None,
                   low_confidence_ids: Optional[List[str]] = None) -> IssueCluster:
    """Build cluster with explainability metrics."""
    now = datetime.now(timezone.utc)
    first = item_group[0]
    raw_title = first.title or "Feedback cluster"
    raw_summary = first.body or "Feedback cluster"
    title = raw_title[:80]
    summary = raw_summary[:300]
    feedback_ids = [str(item.id) for item in item_group]
    github_repo_url = _derive_github_repo_url(item_group)
    sources = sorted({item.source for item in item_group})

    # Determine confidence badge
    confidence_badge = "high"
    if silhouette_score is not None:
        if silhouette_score < 0.3:
            confidence_badge = "low"
        elif silhouette_score < 0.6:
            confidence_badge = "medium"

    return IssueCluster(
        id=str(uuid4()),
        project_id=first.project_id,
        title=title,
        summary=summary,
        feedback_ids=feedback_ids,
        status="new",
        created_at=now,
        updated_at=now,
        github_repo_url=github_repo_url,
        sources=sources,
        silhouette_score=silhouette_score,  # NEW
        confidence_badge=confidence_badge,  # NEW
        low_confidence_item_ids=low_confidence_ids,  # NEW
    )
```

### Recommendation 2: Implement HDBSCAN with Exemplars

**File: `backend/clustering.py`**

```python
import hdbscan
from typing import Dict, List, Tuple

def cluster_hdbscan(
    embeddings: np.ndarray,
    min_cluster_size: int = 2,
    cluster_selection_epsilon: float = 0.28,  # 1 - 0.72 threshold
) -> Tuple[np.ndarray, Dict[int, List[int]], Dict[int, List[float]]]:
    """
    Cluster using HDBSCAN with exemplar and soft score support.

    Returns:
        labels: Cluster label per embedding (-1 = noise)
        exemplars: Dict[cluster_id] -> List[embedding_indices]
        soft_scores: Dict[cluster_id] -> List[probabilities]
    """
    if embeddings.size == 0:
        return np.array([], dtype=int), {}, {}

    if len(embeddings) < min_cluster_size:
        return np.array([0], dtype=int), {0: [0]}, {0: [1.0]}

    # Run HDBSCAN
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric="cosine",
        cluster_selection_epsilon=cluster_selection_epsilon,
        allow_single_cluster=False,  # Prefer noise over forced clustering
    )
    labels = clusterer.fit_predict(embeddings)

    # Extract exemplars
    exemplars: Dict[int, List[int]] = {}
    soft_scores: Dict[int, List[float]] = {}

    for cluster_id in set(labels):
        if cluster_id == -1:  # Skip noise points
            continue

        cluster_mask = labels == cluster_id
        cluster_indices = np.where(cluster_mask)[0]

        # Exemplars are the points with highest stability
        if hasattr(clusterer, 'exemplars_'):
            # Get exemplar indices for this cluster
            cluster_exemplars = clusterer.exemplars_.get(cluster_id, [])
            exemplars[int(cluster_id)] = [int(i) for i in cluster_exemplars]
        else:
            # Fallback: use centroid-closest point
            centroid = embeddings[cluster_mask].mean(axis=0)
            centroid = centroid / np.linalg.norm(centroid)
            sims = embeddings[cluster_mask] @ centroid
            closest_idx = np.argmax(sims)
            exemplars[int(cluster_id)] = [cluster_indices[closest_idx].item()]

        # Soft scores: probability of cluster membership
        if hasattr(clusterer, 'soft_clusters_'):
            cluster_soft = clusterer.soft_clusters_[cluster_mask, cluster_id]
            soft_scores[int(cluster_id)] = cluster_soft.tolist()
        else:
            # Fallback: all assigned points get 1.0
            soft_scores[int(cluster_id)] = [1.0] * len(cluster_indices)

    return labels, exemplars, soft_scores


def cluster_issues_hdbscan(
    issues: Iterable[dict],
    min_cluster_size: int = 2,
    cluster_selection_epsilon: float = 0.28,
    truncate_body_chars: int = DEFAULT_TRUNCATE_BODY_CHARS,
    embed_fn=embed_texts_gemini,
) -> dict:
    """
    Cluster issues using HDBSCAN with exemplar support.

    Returns:
        labels: cluster per issue
        clusters: List of cluster indices (min_cluster_size+)
        singletons: orphaned items
        exemplars: {cluster_id: [exemplar_item_indices]}
        soft_scores: {cluster_id: [probabilities]}
        outliers: count of noise points
    """
    texts = prepare_issue_texts(issues, truncate_body_chars=truncate_body_chars)
    embeddings = embed_fn(texts)

    labels, exemplars, soft_scores = cluster_hdbscan(
        embeddings,
        min_cluster_size=min_cluster_size,
        cluster_selection_epsilon=cluster_selection_epsilon,
    )

    clusters: List[List[int]] = []
    singletons: List[int] = []

    for label in set(labels):
        if label == -1:  # Noise
            idxs = np.where(labels == label)[0].tolist()
            singletons.extend(idxs)
        else:
            idxs = np.where(labels == label)[0].tolist()
            clusters.append(idxs)

    return {
        "labels": labels,
        "clusters": clusters,
        "singletons": singletons,
        "texts": texts,
        "exemplars": exemplars,  # NEW
        "soft_scores": soft_scores,  # NEW
        "outliers": (labels == -1).sum(),  # NEW
    }
```

**File: `backend/models.py`**

```python
class IssueCluster(BaseModel):
    """Represents a cluster of related feedback items."""

    # ... existing fields ...

    # NEW: Exemplar and soft score fields
    exemplar_feedback_ids: Optional[List[str]] = None  # Most representative items
    soft_membership_scores: Optional[Dict[str, float]] = None  # {item_id: probability}
    outlier_count: Optional[int] = None  # Number of noise points excluded
```

**File: `backend/clustering_runner.py`**

```python
def _build_cluster_from_hdbscan_result(
    item_group: List[FeedbackItem],
    exemplar_indices: Optional[List[int]] = None,
    soft_scores: Optional[List[float]] = None,
) -> IssueCluster:
    """Build cluster with HDBSCAN exemplar information."""
    now = datetime.now(timezone.utc)
    first = item_group[0]

    # Use first exemplar as title seed if available
    if exemplar_indices:
        exemplar_item = item_group[exemplar_indices[0]]
        title_seed = exemplar_item.title or "Feedback cluster"
        summary_seed = exemplar_item.body or "Feedback cluster"
    else:
        title_seed = first.title or "Feedback cluster"
        summary_seed = first.body or "Feedback cluster"

    title = title_seed[:80]
    summary = summary_seed[:300]
    feedback_ids = [str(item.id) for item in item_group]
    exemplar_ids = [str(item_group[i].id) for i in exemplar_indices] if exemplar_indices else None

    # Create soft membership dict
    soft_membership = {}
    if soft_scores and exemplar_indices:
        for item, score in zip(item_group, soft_scores):
            soft_membership[str(item.id)] = float(score)

    github_repo_url = _derive_github_repo_url(item_group)
    sources = sorted({item.source for item in item_group})

    return IssueCluster(
        id=str(uuid4()),
        project_id=first.project_id,
        title=title,
        summary=summary,
        feedback_ids=feedback_ids,
        status="new",
        created_at=now,
        updated_at=now,
        github_repo_url=github_repo_url,
        sources=sources,
        exemplar_feedback_ids=exemplar_ids,  # NEW
        soft_membership_scores=soft_membership,  # NEW
    )
```

---

## References & Sources

### Sentry / Industry Patterns
- [Sentry Grouping Documentation](https://docs.sentry.io/product/data-management-settings/event-grouping)
- [Sentry Developer Grouping Guide](https://develop.sentry.dev/grouping/)

### Clustering Metrics
- [Silhouette Score - Towards Data Science](https://towardsdatascience.com/7-evaluation-metrics-for-clustering-algorithms-bdc537ff54d2/)
- [Davies-Bouldin Index - GeeksforGeeks](https://www.geeksforgeeks.org/machine-learning/davies-bouldin-index/)
- [Silhouette Analysis - NumberAnalytics](https://www.numberanalytics.com/blog/silhouette-score-clustering-evaluation)

### Algorithm Comparisons
- [HDBSCAN vs DBSCAN - HDBSCAN Documentation](https://hdbscan.readthedocs.io/en/latest/comparing_clustering_algorithms.html)
- [Clustering Algorithms - scikit-learn](https://scikit-learn.org/stable/modules/clustering.html)
- [State-of-Art Clustering - Medium](https://medium.com/@sina.nazeri/comparing-the-state-of-the-art-clustering-algorithms-1e65a08157a1)

### Vector Databases & Two-Stage Approaches
- [Vector Database Clustering - Milvus](https://milvus.io/ai-quick-reference/how-does-clustering-improve-vector-search/)
- [Vector Search Techniques - Emergent Mind](https://www.emergentmind.com/topics/efficient-vector-search)
- [MongoDB Vector Clustering](https://www.mongodb.com/developer/products/atlas/discover-latent-semantic-structure-with-vector-clustering/)

### HDBSCAN
- [How HDBSCAN Works - Official Docs](https://hdbscan.readthedocs.io/en/latest/how_hdbscan_works.html)
- [HDBSCAN Deep Dive - Arize AI](https://arize.com/blog-course/understanding-hdbscan-a-deep-dive-into-hierarchical-density-based-clustering/)
- [HDBSCAN with LLM - Medium](https://medium.com/@mrsirsh/cluster-chatter-hdbscan-llm-1ec89120eae6)
