# Clustering Implementation Guide - Ready-to-Run Code

This document contains complete, production-ready code snippets for implementing clustering improvements in Soulcaster.

## Implementation 1: Add Silhouette Scores (30 minutes)

### Step 1: Update `backend/clustering.py`

Add this function at the end of the file:

```python
# At top of file, add import
from sklearn.metrics import silhouette_samples, silhouette_score

def compute_cluster_metrics(embeddings: np.ndarray, labels: np.ndarray) -> dict:
    """
    Compute cluster quality metrics for user-facing explanations.

    Args:
        embeddings: (n_samples, dim) normalized embeddings
        labels: (n_samples,) cluster labels

    Returns:
        dict with keys:
        - silhouette_avg: Global silhouette score (-1 to 1)
        - sample_silhouettes: Per-sample scores
        - confidence_badge: "high" / "medium" / "low"
        - low_confidence_indices: Items with score < 0.25
        - explanation: Human-readable summary
    """
    unique_labels = set(labels)

    # Handle edge cases
    if len(unique_labels) <= 1:
        return {
            "silhouette_avg": 0.0,
            "sample_silhouettes": np.zeros(len(labels)).tolist(),
            "confidence_badge": "medium",
            "low_confidence_indices": [],
            "explanation": "Single cluster or no items.",
        }

    # Compute silhouette scores
    try:
        silhouette_avg = float(silhouette_score(embeddings, labels, metric="cosine"))
        sample_silhouettes = silhouette_samples(embeddings, labels, metric="cosine")
    except Exception as e:
        logger.error(f"Failed to compute silhouette: {e}")
        return {
            "silhouette_avg": 0.0,
            "sample_silhouettes": np.zeros(len(labels)).tolist(),
            "confidence_badge": "unknown",
            "low_confidence_indices": [],
            "explanation": "Could not compute cluster quality.",
        }

    # Determine confidence level
    if silhouette_avg >= 0.6:
        confidence = "high"
        qual_text = "very well-grouped"
    elif silhouette_avg >= 0.3:
        confidence = "medium"
        qual_text = "moderately well-grouped"
    else:
        confidence = "low"
        qual_text = "loosely grouped"

    # Find low-confidence items
    threshold = 0.25
    low_conf_indices = np.where(sample_silhouettes < threshold)[0].tolist()

    # Build explanation
    n_clusters = len(unique_labels)
    explanation = (
        f"This cluster is {qual_text} ({silhouette_avg:.2f}/1.0). "
        f"{n_clusters} groups, {len(labels)} items. "
        f"{len(low_conf_indices)} items may not fully belong here."
    )

    return {
        "silhouette_avg": silhouette_avg,
        "sample_silhouettes": sample_silhouettes.tolist(),
        "confidence_badge": confidence,
        "low_confidence_indices": low_conf_indices,
        "explanation": explanation,
    }


def cluster_issues_with_metrics(
    issues: Iterable[dict],
    method: Literal["agglomerative", "centroid", "vector_like"] = DEFAULT_METHOD,
    sim_threshold: float = DEFAULT_SIM_THRESHOLD,
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    truncate_body_chars: int = DEFAULT_TRUNCATE_BODY_CHARS,
    embed_fn=embed_texts_gemini,
) -> dict:
    """
    Cluster issues and compute quality metrics.

    Returns:
        dict with all fields from cluster_issues() plus:
        - metrics: Result from compute_cluster_metrics()
        - silhouette_score: Float, convenience field
        - confidence_badge: String ("high", "medium", "low")
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

    # Compute embeddings again (slight inefficiency, could be optimized)
    texts = result["texts"]
    if len(texts) > 0:
        embeddings = embed_fn(texts)
    else:
        embeddings = np.empty((0, 768), dtype=np.float32)

    # Compute metrics
    metrics = compute_cluster_metrics(embeddings, result["labels"])

    result.update({
        "metrics": metrics,
        "silhouette_score": metrics["silhouette_avg"],
        "confidence_badge": metrics["confidence_badge"],
    })

    return result


# Export new function
__all__.extend(["compute_cluster_metrics", "cluster_issues_with_metrics"])
```

### Step 2: Update `backend/models.py`

Add these fields to `IssueCluster`:

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

    # NEW FIELDS FOR EXPLAINABILITY
    silhouette_score: Optional[float] = None  # -1 to 1, confidence indicator
    confidence_badge: Optional[Literal["high", "medium", "low"]] = "medium"  # UI label
    explanation: Optional[str] = None  # Human-readable summary
    low_confidence_item_ids: Optional[List[str]] = None  # Items with score < 0.25
```

### Step 3: Update `backend/main.py`

Modify the clustering endpoint to use new metrics:

```python
# Find the /clusters endpoint and update it
@app.get("/clusters/{project_id}")
async def get_clusters(project_id: str) -> List[dict]:
    """Get all clusters for a project, including quality metrics."""
    clusters = store.get_all_clusters(project_id)

    result = []
    for cluster in clusters:
        cluster_dict = cluster.model_dump(by_alias=True)
        # silhouette_score already in cluster if computed
        result.append(cluster_dict)

    return result
```

### Step 4: Update `backend/clustering_runner.py`

Modify `_build_cluster()` to accept metrics:

```python
def _build_cluster(
    item_group: List[FeedbackItem],
    silhouette_score: Optional[float] = None,
    confidence_badge: Optional[str] = None,
    explanation: Optional[str] = None,
    low_conf_indices: Optional[List[int]] = None,
) -> IssueCluster:
    """
    Builds a new IssueCluster from feedback items with metrics.
    """
    now = datetime.now(timezone.utc)
    first = item_group[0]
    raw_title = first.title or "Feedback cluster"
    raw_summary = first.body or "Feedback cluster"
    title = raw_title[:80]
    summary = raw_summary[:300]
    feedback_ids = [str(item.id) for item in item_group]
    github_repo_url = _derive_github_repo_url(item_group)
    sources = sorted({item.source for item in item_group})

    # Map low_conf_indices to item IDs
    low_conf_ids = None
    if low_conf_indices:
        low_conf_ids = [str(item_group[i].id) for i in low_conf_indices if i < len(item_group)]

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
        # NEW: Quality metrics
        silhouette_score=silhouette_score,
        confidence_badge=confidence_badge,
        explanation=explanation,
        low_confidence_item_ids=low_conf_ids,
    )
```

### Step 5: Update Dashboard Component

Create new component `dashboard/components/ConfidenceBadge.tsx`:

```typescript
'use client';

interface ConfidenceBadgeProps {
  score: number | null | undefined;
  badge?: 'high' | 'medium' | 'low';
  explanation?: string;
}

export default function ConfidenceBadge({
  score,
  badge = 'medium',
  explanation,
}: ConfidenceBadgeProps) {
  const badgeColor = {
    high: 'bg-emerald-900/30 text-emerald-400 border-emerald-900/50',
    medium: 'bg-yellow-900/30 text-yellow-400 border-yellow-900/50',
    low: 'bg-red-900/30 text-red-400 border-red-900/50',
  }[badge];

  const badgeText = {
    high: '✓ High Confidence',
    medium: '◐ Medium Confidence',
    low: '⚠ Low Confidence',
  }[badge];

  const scoreText = score !== null && score !== undefined ?
    `(${(score * 100).toFixed(0)}%)` : '';

  return (
    <div className="group relative">
      <span className={`inline-flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-md border ${badgeColor}`}>
        {badgeText}
        {scoreText && <span className="opacity-70">{scoreText}</span>}
      </span>

      {explanation && (
        <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10 bg-gray-900 text-gray-100 text-xs rounded px-2 py-1 w-max max-w-xs border border-gray-700">
          {explanation}
        </div>
      )}
    </div>
  );
}
```

Update `dashboard/app/(dashboard)/dashboard/clusters/[id]/components/ClusterHeader.tsx`:

```typescript
'use client';

import ConfidenceBadge from '@/components/ConfidenceBadge';
import type { ClusterDetail } from '@/types';

export default function ClusterHeader({
  cluster,
  selectedRepo,
  onRepoSelect,
}: ClusterHeaderProps) {
  // ... existing code ...

  return (
    <div className="bg-[#0A0A0A] shadow-lg rounded-2xl overflow-hidden border border-white/10 mb-6">
      <div className="px-6 py-6">
        {/* Title and Status */}
        <div className="flex flex-wrap items-start gap-3 mb-4">
          <h1 className="text-2xl font-bold text-white tracking-tight flex-1 min-w-0">
            {cluster.issue_title || cluster.title || 'Untitled Cluster'}
          </h1>
          <div className="flex gap-2">
            <span className={getStatusBadgeClass(cluster.status)}>
              {cluster.status.replace('_', ' ')}
            </span>
            {/* NEW: Confidence badge */}
            <ConfidenceBadge
              score={cluster.silhouette_score}
              badge={cluster.confidence_badge as any}
              explanation={cluster.explanation}
            />
          </div>
        </div>

        {/* Description */}
        <p className="text-slate-400 leading-relaxed mb-6">
          {cluster.issue_description || cluster.summary}
        </p>

        {/* Explanation section */}
        {cluster.explanation && (
          <div className="mb-6 p-3 bg-blue-900/20 rounded-lg border border-blue-900/50">
            <p className="text-xs text-blue-300">
              <strong>Why grouped:</strong> {cluster.explanation}
            </p>
          </div>
        )}

        {/* ... rest of existing code ... */}
      </div>
    </div>
  );
}
```

---

## Implementation 2: Add HDBSCAN Support (2-3 days)

### Step 1: Install Package

```bash
cd backend
pip install hdbscan
# Update requirements.txt or pyproject.toml
```

### Step 2: Add HDBSCAN Clustering Function

Add to `backend/clustering.py`:

```python
try:
    import hdbscan
except ImportError:
    hdbscan = None


def cluster_hdbscan(
    embeddings: np.ndarray,
    min_cluster_size: int = 2,
    cluster_selection_epsilon: float = 0.28,  # 1 - 0.72
) -> Tuple[np.ndarray, Dict[int, List[int]], Dict[int, List[float]], int]:
    """
    Cluster using HDBSCAN with exemplar and soft score support.

    Args:
        embeddings: (n_samples, dim) L2-normalized vectors
        min_cluster_size: Minimum points per cluster (default 2)
        cluster_selection_epsilon: Distance threshold (default 0.28 for cosine)

    Returns:
        labels: Cluster label per embedding (-1 = noise)
        exemplars: Dict[cluster_id] -> List[exemplar_indices]
        soft_scores: Dict[cluster_id] -> List[probabilities]
        outlier_count: Number of noise points
    """
    if hdbscan is None:
        raise RuntimeError("hdbscan not installed. Run: pip install hdbscan")

    if embeddings.size == 0:
        return np.array([], dtype=int), {}, {}, 0

    if len(embeddings) < min_cluster_size:
        return np.array([0], dtype=int), {0: [0]}, {0: [1.0]}, 0

    try:
        # Run HDBSCAN
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            metric="cosine",
            cluster_selection_epsilon=cluster_selection_epsilon,
            allow_single_cluster=False,
        )
        labels = clusterer.fit_predict(embeddings)

        # Extract exemplars and soft scores
        exemplars: Dict[int, List[int]] = {}
        soft_scores: Dict[int, List[float]] = {}

        for cluster_id in set(labels):
            if cluster_id == -1:  # Skip noise
                continue

            cluster_mask = labels == cluster_id
            cluster_indices = np.where(cluster_mask)[0]

            # Get exemplar indices
            if hasattr(clusterer, 'exemplars_') and cluster_id in clusterer.exemplars_:
                exemplar_list = clusterer.exemplars_[cluster_id]
                exemplars[int(cluster_id)] = [int(i) for i in exemplar_list]
            else:
                # Fallback: find closest to centroid
                centroid = embeddings[cluster_mask].mean(axis=0)
                norm = np.linalg.norm(centroid)
                if norm > 0:
                    centroid = centroid / norm
                sims = embeddings[cluster_mask] @ centroid
                closest_idx = np.argmax(sims)
                exemplars[int(cluster_id)] = [cluster_indices[closest_idx].item()]

            # Get soft scores
            if hasattr(clusterer, 'soft_clusters_'):
                scores = clusterer.soft_clusters_[cluster_mask, cluster_id]
                soft_scores[int(cluster_id)] = scores.tolist()
            else:
                soft_scores[int(cluster_id)] = [1.0] * len(cluster_indices)

        outlier_count = (labels == -1).sum()
        return labels, exemplars, soft_scores, int(outlier_count)

    except Exception as e:
        logger.error(f"HDBSCAN clustering failed: {e}")
        raise


def cluster_issues_hdbscan(
    issues: Iterable[dict],
    min_cluster_size: int = 2,
    cluster_selection_epsilon: float = 0.28,
    truncate_body_chars: int = DEFAULT_TRUNCATE_BODY_CHARS,
    embed_fn=embed_texts_gemini,
) -> dict:
    """
    Cluster issues using HDBSCAN.

    Returns:
        dict with keys:
        - labels: array of cluster labels
        - clusters: list of cluster index lists (size >= min_cluster_size)
        - singletons: list of outlier indices
        - texts: prepared texts
        - exemplars: {cluster_id: [exemplar_indices]}
        - soft_scores: {cluster_id: [probabilities]}
        - outliers: count of noise points
        - metrics: dict with quality information
    """
    texts = prepare_issue_texts(issues, truncate_body_chars=truncate_body_chars)
    embeddings = embed_fn(texts)

    labels, exemplars, soft_scores, outlier_count = cluster_hdbscan(
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
            if len(idxs) >= min_cluster_size:
                clusters.append(idxs)
            else:
                singletons.extend(idxs)

    # Compute quality metrics
    metrics = compute_cluster_metrics(embeddings, labels)

    return {
        "labels": labels,
        "clusters": clusters,
        "singletons": singletons,
        "texts": texts,
        "exemplars": exemplars,
        "soft_scores": soft_scores,
        "outliers": outlier_count,
        "metrics": metrics,
    }
```

### Step 3: Update Models

Update `backend/models.py`:

```python
class IssueCluster(BaseModel):
    """Represents a cluster of related feedback items."""

    # ... existing fields ...

    # NEW: HDBSCAN-specific fields
    exemplar_feedback_ids: Optional[List[str]] = None  # Most representative items
    soft_membership_scores: Optional[Dict[str, float]] = None  # {item_id: prob}
    outlier_count: Optional[int] = None  # Number of noise points
```

### Step 4: Update Clustering Runner

Modify `backend/clustering_runner.py`:

```python
def _build_cluster_from_result(
    item_group: List[FeedbackItem],
    exemplar_indices: Optional[List[int]] = None,
    soft_scores: Optional[List[float]] = None,
    outlier_count: Optional[int] = None,
    metrics: Optional[dict] = None,
) -> IssueCluster:
    """Build cluster with HDBSCAN results."""
    now = datetime.now(timezone.utc)
    first = item_group[0]

    # Prefer exemplar as source of title if available
    if exemplar_indices and len(exemplar_indices) > 0:
        exemplar_item = item_group[exemplar_indices[0]]
        title_source = exemplar_item
    else:
        title_source = first

    raw_title = title_source.title or "Feedback cluster"
    raw_summary = title_source.body or "Feedback cluster"
    title = raw_title[:80]
    summary = raw_summary[:300]
    feedback_ids = [str(item.id) for item in item_group]
    exemplar_ids = (
        [str(item_group[i].id) for i in exemplar_indices]
        if exemplar_indices else None
    )

    # Create soft membership dict
    soft_membership = {}
    if soft_scores:
        for item, score in zip(item_group, soft_scores):
            soft_membership[str(item.id)] = float(score)

    github_repo_url = _derive_github_repo_url(item_group)
    sources = sorted({item.source for item in item_group})

    # Extract metrics if provided
    silhouette = metrics.get("silhouette_avg") if metrics else None
    confidence = metrics.get("confidence_badge") if metrics else None
    explanation = metrics.get("explanation") if metrics else None

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
        exemplar_feedback_ids=exemplar_ids,
        soft_membership_scores=soft_membership if soft_membership else None,
        outlier_count=outlier_count,
        silhouette_score=silhouette,
        confidence_badge=confidence,
        explanation=explanation,
    )
```

### Step 5: Add Configuration Option

Update `backend/clustering.py` to select method:

```python
# At top of file
CLUSTERING_METHOD_OPTIONS = {
    "agglomerative": cluster_agglomerative,
    "centroid": cluster_centroid,
    "vector_like": cluster_vector_like,
    "hdbscan": cluster_hdbscan,
}

def cluster_issues_auto(
    issues: Iterable[dict],
    method: str = DEFAULT_METHOD,
    **kwargs
) -> dict:
    """Auto-select clustering method and params."""
    if method == "hdbscan":
        return cluster_issues_hdbscan(issues, **kwargs)
    else:
        return cluster_issues(issues, method=method, **kwargs)
```

Update `backend/clustering_runner.py` to use HDBSCAN:

```python
# In run_clustering_job or _run_vector_clustering
clustering_method = os.getenv("CLUSTERING_METHOD", "hdbscan").lower()

if clustering_method == "hdbscan":
    result = _run_hdbscan_clustering(items, project_id)
else:
    result = _run_vector_clustering(items, project_id)
```

### Step 6: Add Exemplar Display in Dashboard

Create `dashboard/components/ExemplarItems.tsx`:

```typescript
'use client';

import type { FeedbackItem } from '@/types';

interface ExemplarItemsProps {
  items: FeedbackItem[];
  exemplarIds: string[];
}

export default function ExemplarItems({
  items,
  exemplarIds,
}: ExemplarItemsProps) {
  const exemplarItems = items.filter(item =>
    exemplarIds.includes(String(item.id))
  );

  if (exemplarItems.length === 0) {
    return null;
  }

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider mb-3">
        Representative Examples
      </h3>
      <div className="space-y-3">
        {exemplarItems.map((item, idx) => (
          <div
            key={item.id}
            className="p-3 bg-emerald-900/20 border border-emerald-900/50 rounded-lg"
          >
            <div className="flex items-start gap-2">
              <div className="flex-shrink-0 mt-0.5">
                <span className="inline-flex items-center justify-center h-6 w-6 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-bold">
                  {idx + 1}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-emerald-300">
                  {item.title}
                </p>
                <p className="text-xs text-emerald-200/70 mt-1 line-clamp-2">
                  {item.body}
                </p>
                <div className="flex gap-2 mt-2">
                  <span className="inline-block text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                    {item.source}
                  </span>
                  {item.created_at && (
                    <span className="inline-block text-[10px] text-emerald-200/50">
                      {new Date(item.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## Implementation 3: Two-Stage Clustering (Optional, Advanced)

For production deployments with high volume, combine vector DB search with local DBSCAN:

```python
# In backend/clustering_runner.py

def _run_two_stage_clustering(
    items: List[FeedbackItem],
    project_id: str,
) -> dict:
    """
    Two-stage clustering:
    1. Vector DB coarse search (fast)
    2. Local DBSCAN fine clustering
    """
    from sklearn.cluster import DBSCAN

    # Phase 1: Generate embeddings
    issues_payload = _prepare_issue_payloads(items)
    texts = clustering.prepare_issue_texts(issues_payload)
    embeddings = clustering.embed_texts_gemini(texts)
    embeddings_list = [emb.tolist() for emb in embeddings]

    # Phase 2: Vector DB query for candidates
    vector_store = VectorStore()
    candidates = {}
    for i, item in enumerate(items):
        similar = vector_store.find_similar(
            embedding=embeddings_list[i],
            project_id=project_id,
            top_k=20,
            min_score=0.5,  # Coarse threshold
        )
        candidates[str(item.id)] = similar

    # Phase 3: DBSCAN on full embedding matrix
    distances = 1 - embeddings  # Convert cosine similarity to distance

    # Auto-estimate eps from data distribution
    from scipy.spatial.distance import pdist
    all_distances = pdist(embeddings, metric='cosine')
    eps = np.percentile(all_distances, 70)  # 70th percentile

    dbscan = DBSCAN(eps=eps, min_samples=2, metric='cosine')
    labels = dbscan.fit_predict(embeddings)

    # Process results similar to _run_vector_clustering
    item_cluster_map = {}
    for i, item in enumerate(items):
        item_id = str(item.id)
        cluster_id = labels[i]
        if cluster_id == -1:  # Noise
            cluster_id = str(uuid4())  # Assign new cluster
        item_cluster_map[item_id] = str(cluster_id)

    # ... rest same as _run_vector_clustering ...

    return result
```

---

## Testing the Implementation

### Unit Test Example

```python
# backend/tests/test_silhouette.py

import numpy as np
from clustering import compute_cluster_metrics

def test_silhouette_high_quality():
    """High-quality cluster should have high silhouette."""
    embeddings = np.array([
        [1, 0, 0],
        [1, 0, 0],
        [0, 1, 0],
        [0, 1, 0],
    ], dtype=np.float32)
    labels = np.array([0, 0, 1, 1])

    metrics = compute_cluster_metrics(embeddings, labels)

    assert metrics["silhouette_avg"] > 0.7
    assert metrics["confidence_badge"] == "high"
    assert len(metrics["low_confidence_indices"]) == 0

def test_silhouette_poor_quality():
    """Mixed cluster should have low silhouette."""
    embeddings = np.array([
        [1, 0],
        [0, 1],
        [1, 1],
        [0.5, 0.5],
    ], dtype=np.float32)
    labels = np.array([0, 0, 0, 0])  # All same cluster

    metrics = compute_cluster_metrics(embeddings, labels)

    assert metrics["silhouette_avg"] < 0.3
    assert metrics["confidence_badge"] == "low"
```

### Integration Test

```python
# backend/tests/test_clustering_with_metrics.py

async def test_clustering_pipeline_with_metrics(sample_feedback):
    """End-to-end: ingest → cluster → metrics."""
    from clustering import cluster_issues_with_metrics

    result = cluster_issues_with_metrics(
        issues=sample_feedback,
        method="agglomerative",
    )

    assert "metrics" in result
    assert "silhouette_score" in result
    assert -1 <= result["silhouette_score"] <= 1
    assert result["confidence_badge"] in ["high", "medium", "low"]
    assert "explanation" in result["metrics"]
```

---

## Deployment Checklist

- [ ] Install new packages (hdbscan if using it)
- [ ] Add environment variables for method selection
- [ ] Run full test suite
- [ ] Benchmark clustering on production volume
- [ ] Update API documentation
- [ ] Deploy backend changes
- [ ] Update dashboard components
- [ ] Test UI with confidence badges
- [ ] Test exemplar display (if using HDBSCAN)
- [ ] Monitor clustering metrics post-deployment
- [ ] Gather user feedback on new UI

---

Good luck with the implementation!
