"""
Upstash Vector-based storage for feedback embeddings.

This module provides vector similarity search for feedback clustering.
Instead of storing centroids and doing O(n) comparisons, we use a vector DB
for efficient approximate nearest neighbor (ANN) search.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence
from uuid import uuid4

import numpy as np

try:
    from upstash_vector import Index
except ImportError:
    Index = None  # type: ignore

logger = logging.getLogger(__name__)

# Clustering thresholds (single source of truth)
VECTOR_CLUSTERING_THRESHOLD = 0.72
CLEANUP_MERGE_THRESHOLD = 0.65

# Embedding dimension for Gemini
EMBEDDING_DIMENSION = 768


@dataclass
class FeedbackVectorMetadata:
    """Metadata stored with each feedback embedding in the vector store."""

    title: str
    source: str  # 'reddit', 'manual', 'github', 'sentry'
    cluster_id: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class SimilarFeedback:
    """Result from a similarity search."""

    id: str
    score: float
    metadata: Optional[FeedbackVectorMetadata] = None


@dataclass
class ClusteringResult:
    """Result from clustering a single feedback item."""

    feedback_id: str
    cluster_id: str
    is_new_cluster: bool
    similarity: Optional[float] = None
    grouped_feedback_ids: Optional[List[str]] = None


@dataclass
class ClusterCohesion:
    """Cohesion metrics for a cluster."""

    cluster_id: str
    avg_similarity: float
    min_similarity: float
    max_similarity: float
    item_count: int
    quality: str  # 'tight', 'moderate', 'loose'


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a, dtype=np.float32)
    b_arr = np.array(b, dtype=np.float32)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def calculate_cluster_cohesion(
    embeddings: List[List[float]], cluster_id: str
) -> ClusterCohesion:
    """
    Calculate cohesion score for a cluster.

    Cohesion = average pairwise similarity between all items in the cluster.
    Quality thresholds:
      - tight (>0.85): Items are very similar, clear cluster
      - moderate (0.70-0.85): Related items, good for triage
      - loose (<0.70): Broad grouping, consider splitting
    """
    if len(embeddings) <= 1:
        return ClusterCohesion(
            cluster_id=cluster_id,
            avg_similarity=1.0,
            min_similarity=1.0,
            max_similarity=1.0,
            item_count=len(embeddings),
            quality="tight",
        )

    total_similarity = 0.0
    pair_count = 0
    min_sim = 1.0
    max_sim = 0.0

    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            sim = _cosine_similarity(embeddings[i], embeddings[j])
            total_similarity += sim
            pair_count += 1
            min_sim = min(min_sim, sim)
            max_sim = max(max_sim, sim)

    avg_similarity = total_similarity / pair_count if pair_count > 0 else 1.0

    if avg_similarity >= 0.85:
        quality = "tight"
    elif avg_similarity >= 0.70:
        quality = "moderate"
    else:
        quality = "loose"

    return ClusterCohesion(
        cluster_id=cluster_id,
        avg_similarity=avg_similarity,
        min_similarity=min_sim,
        max_similarity=max_sim,
        item_count=len(embeddings),
        quality=quality,
    )


class VectorStore:
    """
    VectorStore wraps Upstash Vector for feedback embedding storage and search.

    Key operations:
    - Store feedback embeddings with metadata (cluster_id, source, etc.)
    - Find similar feedback items by embedding
    - Update cluster assignments
    - Query cluster membership
    """

    def __init__(self):
        url = os.getenv("UPSTASH_VECTOR_REST_URL")
        token = os.getenv("UPSTASH_VECTOR_REST_TOKEN")

        if not url or not token:
            logger.warning("[VectorStore] UPSTASH_VECTOR credentials not set")

        if Index is None:
            raise RuntimeError("upstash-vector is not installed")

        self.index = Index(url=url or "", token=token or "")

    def upsert_feedback(
        self,
        feedback_id: str,
        embedding: List[float],
        metadata: FeedbackVectorMetadata,
    ) -> None:
        """Store a single feedback embedding."""
        self.index.upsert(
            vectors=[
                {
                    "id": feedback_id,
                    "vector": embedding,
                    "metadata": {
                        "title": metadata.title,
                        "source": metadata.source,
                        "cluster_id": metadata.cluster_id or "",
                        "created_at": metadata.created_at or "",
                    },
                }
            ]
        )

    def upsert_feedback_batch(
        self,
        items: List[Dict],
    ) -> None:
        """
        Store multiple feedback embeddings in batch.

        Each item should have: id, embedding, metadata (FeedbackVectorMetadata)
        """
        vectors = [
            {
                "id": item["id"],
                "vector": item["embedding"],
                "metadata": {
                    "title": item["metadata"].title,
                    "source": item["metadata"].source,
                    "cluster_id": item["metadata"].cluster_id or "",
                    "created_at": item["metadata"].created_at or "",
                },
            }
            for item in items
        ]
        self.index.upsert(vectors=vectors)

    def find_similar(
        self,
        embedding: List[float],
        top_k: int = 10,
        min_score: float = 0.0,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[SimilarFeedback]:
        """
        Find similar feedback items by embedding.

        Args:
            embedding: Query embedding vector
            top_k: Maximum number of results to return
            min_score: Minimum similarity score (0-1)
            exclude_ids: IDs to exclude from results
        """
        results = self.index.query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
            include_vectors=False,
        )

        exclude_set = set(exclude_ids or [])
        similar = []

        for r in results:
            if r.score < min_score:
                continue
            if r.id in exclude_set:
                continue

            metadata = None
            if r.metadata:
                metadata = FeedbackVectorMetadata(
                    title=r.metadata.get("title", ""),
                    source=r.metadata.get("source", ""),
                    cluster_id=r.metadata.get("cluster_id") or None,
                    created_at=r.metadata.get("created_at") or None,
                )

            similar.append(SimilarFeedback(id=r.id, score=r.score, metadata=metadata))

        return similar

    def find_similar_in_cluster(
        self,
        embedding: List[float],
        cluster_id: str,
        top_k: int = 10,
    ) -> List[SimilarFeedback]:
        """Find similar items within a specific cluster."""
        # Query more items since we'll filter by cluster
        results = self.index.query(
            vector=embedding,
            top_k=top_k * 3,
            include_metadata=True,
            include_vectors=False,
        )

        similar = []
        for r in results:
            if r.metadata and r.metadata.get("cluster_id") == cluster_id:
                metadata = FeedbackVectorMetadata(
                    title=r.metadata.get("title", ""),
                    source=r.metadata.get("source", ""),
                    cluster_id=r.metadata.get("cluster_id") or None,
                    created_at=r.metadata.get("created_at") or None,
                )
                similar.append(SimilarFeedback(id=r.id, score=r.score, metadata=metadata))
                if len(similar) >= top_k:
                    break

        return similar

    def update_cluster_assignment(self, feedback_id: str, cluster_id: str) -> None:
        """Update the cluster assignment for a single feedback item."""
        # Fetch current vector and metadata
        existing = self.index.fetch(ids=[feedback_id], include_metadata=True, include_vectors=True)

        if not existing or len(existing) == 0:
            raise ValueError(f"Feedback {feedback_id} not found in vector store")

        item = existing[0]
        if item is None:
            raise ValueError(f"Feedback {feedback_id} not found in vector store")

        old_metadata = item.metadata or {}
        new_metadata = {
            "title": old_metadata.get("title", ""),
            "source": old_metadata.get("source", ""),
            "cluster_id": cluster_id,
            "created_at": old_metadata.get("created_at", ""),
        }

        # Re-upsert with updated metadata
        self.index.upsert(
            vectors=[
                {
                    "id": feedback_id,
                    "vector": item.vector,
                    "metadata": new_metadata,
                }
            ]
        )

    def update_cluster_assignment_batch(
        self, assignments: List[Dict[str, str]]
    ) -> None:
        """
        Batch update cluster assignments.

        Args:
            assignments: List of {"feedback_id": str, "cluster_id": str}
        """
        feedback_ids = [a["feedback_id"] for a in assignments]
        existing = self.index.fetch(ids=feedback_ids, include_metadata=True, include_vectors=True)

        updates = []
        for item in existing:
            if item is None:
                continue

            assignment = next(
                (a for a in assignments if a["feedback_id"] == item.id), None
            )
            if assignment is None:
                continue

            old_metadata = item.metadata or {}
            new_metadata = {
                "title": old_metadata.get("title", ""),
                "source": old_metadata.get("source", ""),
                "cluster_id": assignment["cluster_id"],
                "created_at": old_metadata.get("created_at", ""),
            }
            updates.append(
                {
                    "id": item.id,
                    "vector": item.vector,
                    "metadata": new_metadata,
                }
            )

        if updates:
            self.index.upsert(vectors=updates)

    def delete_feedback(self, feedback_id: str) -> None:
        """Delete a single feedback from the vector store."""
        self.index.delete(ids=[feedback_id])

    def delete_feedback_batch(self, feedback_ids: List[str]) -> None:
        """Delete multiple feedback items from the vector store."""
        self.index.delete(ids=feedback_ids)

    def reset(self) -> None:
        """Reset the entire vector store (use with caution!)."""
        self.index.reset()


def cluster_with_vector_db(
    feedback_id: str,
    embedding: List[float],
    source: str,
    title: str,
    threshold: float = VECTOR_CLUSTERING_THRESHOLD,
    vector_store: Optional[VectorStore] = None,
) -> ClusteringResult:
    """
    Cluster a single feedback item using vector similarity search.

    Algorithm:
    1. Query vector DB for similar items
    2. If top match is above threshold AND is already clustered -> join that cluster
    3. If top matches are above threshold but unclustered -> create new cluster with them
    4. If no matches above threshold -> create new single-item cluster
    """
    if vector_store is None:
        vector_store = VectorStore()

    # Find similar items (exclude self)
    similar = vector_store.find_similar(
        embedding=embedding,
        top_k=20,
        min_score=threshold,
        exclude_ids=[feedback_id],
    )

    if len(similar) == 0:
        # No similar items - create new cluster
        cluster_id = str(uuid4())
        return ClusteringResult(
            feedback_id=feedback_id,
            cluster_id=cluster_id,
            is_new_cluster=True,
            grouped_feedback_ids=[],
        )

    # Check if any similar item is already clustered
    clustered_items = [s for s in similar if s.metadata and s.metadata.cluster_id]

    if clustered_items:
        # Join the cluster of the most similar clustered item
        best_match = clustered_items[0]
        return ClusteringResult(
            feedback_id=feedback_id,
            cluster_id=best_match.metadata.cluster_id,  # type: ignore
            is_new_cluster=False,
            similarity=best_match.score,
        )

    # All similar items are unclustered - create new cluster and group them
    cluster_id = str(uuid4())
    grouped_ids = [s.id for s in similar]

    return ClusteringResult(
        feedback_id=feedback_id,
        cluster_id=cluster_id,
        is_new_cluster=True,
        grouped_feedback_ids=grouped_ids,
    )


def find_similar_clusters(
    cluster_centroids: Dict[str, List[float]],
    threshold: float = CLEANUP_MERGE_THRESHOLD,
) -> List[Dict]:
    """
    Find clusters that should potentially be merged based on centroid similarity.

    Uses direct centroid-to-centroid comparison.

    Returns:
        List of {"cluster1": str, "cluster2": str, "similarity": float}
    """
    merge_candidates = []
    cluster_ids = list(cluster_centroids.keys())

    for i in range(len(cluster_ids)):
        id1 = cluster_ids[i]
        centroid1 = cluster_centroids[id1]
        if len(centroid1) == 0:
            continue

        for j in range(i + 1, len(cluster_ids)):
            id2 = cluster_ids[j]
            centroid2 = cluster_centroids[id2]
            if len(centroid2) == 0:
                continue

            similarity = _cosine_similarity(centroid1, centroid2)
            if similarity >= threshold:
                merge_candidates.append(
                    {"cluster1": id1, "cluster2": id2, "similarity": similarity}
                )

    return merge_candidates


# Singleton instance
_vector_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the singleton VectorStore instance."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
