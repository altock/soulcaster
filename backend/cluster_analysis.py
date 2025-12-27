"""
Cluster quality analysis and split detection for overly-broad clusters.

This module provides tools to analyze existing clusters and detect when they
should be split into more focused sub-clusters. It's designed for post-hoc
analysis, not real-time clustering.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from clustering import cluster_agglomerative
from vector_store import (
    VectorStore,
    calculate_cluster_cohesion,
    ClusterCohesion,
    _cosine_similarity,
)

logger = logging.getLogger(__name__)

# Thresholds for detecting clusters that need splitting
LOOSE_CLUSTER_THRESHOLD = 0.65  # Below this avg similarity = "loose"
SPLIT_SIMILARITY_THRESHOLD = 0.80  # Use higher threshold when finding sub-clusters


@dataclass
class SplitRecommendation:
    """Recommendation for splitting a cluster."""

    cluster_id: str
    should_split: bool
    reason: str
    current_cohesion: ClusterCohesion
    suggested_subclusters: List[List[str]] = field(default_factory=list)
    subcluster_cohesions: List[float] = field(default_factory=list)


@dataclass
class ClusterHealthReport:
    """Overall health report for a project's clusters."""

    project_id: str
    total_clusters: int
    healthy_clusters: int
    loose_clusters: int
    split_recommendations: List[SplitRecommendation] = field(default_factory=list)


def analyze_cluster_for_split(
    cluster_id: str,
    feedback_ids: List[str],
    embeddings: Dict[str, List[float]],
    split_threshold: float = SPLIT_SIMILARITY_THRESHOLD,
) -> SplitRecommendation:
    """
    Analyze a cluster to determine if it should be split.

    Uses agglomerative clustering with a higher similarity threshold to find
    natural sub-groups within a loose cluster.

    Parameters:
        cluster_id (str): ID of the cluster to analyze.
        feedback_ids (List[str]): IDs of feedback items in the cluster.
        embeddings (Dict[str, List[float]]): Map of feedback_id to embedding.
        split_threshold (float): Similarity threshold for sub-cluster detection.

    Returns:
        SplitRecommendation: Analysis result with split suggestion if applicable.
    """
    # Get embeddings for cluster members
    cluster_embeddings = []
    valid_ids = []
    for fid in feedback_ids:
        if fid in embeddings:
            cluster_embeddings.append(embeddings[fid])
            valid_ids.append(fid)

    if len(cluster_embeddings) < 2:
        return SplitRecommendation(
            cluster_id=cluster_id,
            should_split=False,
            reason="Cluster too small to analyze",
            current_cohesion=ClusterCohesion(
                cluster_id=cluster_id,
                avg_similarity=1.0,
                min_similarity=1.0,
                max_similarity=1.0,
                item_count=len(cluster_embeddings),
                quality="tight",
            ),
        )

    # Calculate current cohesion
    cohesion = calculate_cluster_cohesion(cluster_embeddings, cluster_id)

    # If cluster is already tight, no split needed
    if cohesion.avg_similarity >= 0.75:
        return SplitRecommendation(
            cluster_id=cluster_id,
            should_split=False,
            reason=f"Cluster is already cohesive (avg_sim={cohesion.avg_similarity:.3f})",
            current_cohesion=cohesion,
        )

    # Try to find natural sub-clusters using higher threshold
    emb_array = np.array(cluster_embeddings, dtype=np.float32)
    labels = cluster_agglomerative(emb_array, sim_threshold=split_threshold)

    n_subclusters = len(set(labels))

    if n_subclusters <= 1:
        return SplitRecommendation(
            cluster_id=cluster_id,
            should_split=False,
            reason=f"No natural sub-clusters found at threshold {split_threshold}",
            current_cohesion=cohesion,
        )

    # Build sub-cluster groups
    subclusters: Dict[int, List[str]] = {}
    subcluster_embeddings: Dict[int, List[List[float]]] = {}

    for i, label in enumerate(labels):
        label_int = int(label)
        if label_int not in subclusters:
            subclusters[label_int] = []
            subcluster_embeddings[label_int] = []
        subclusters[label_int].append(valid_ids[i])
        subcluster_embeddings[label_int].append(cluster_embeddings[i])

    # Calculate cohesion for each sub-cluster
    subcluster_cohesions = []
    for label, embs in subcluster_embeddings.items():
        if len(embs) >= 2:
            sub_cohesion = calculate_cluster_cohesion(embs, f"sub_{label}")
            subcluster_cohesions.append(sub_cohesion.avg_similarity)
        else:
            subcluster_cohesions.append(1.0)

    avg_subcluster_cohesion = sum(subcluster_cohesions) / len(subcluster_cohesions)

    # Only recommend split if sub-clusters are significantly tighter
    improvement = avg_subcluster_cohesion - cohesion.avg_similarity
    if improvement < 0.05:
        return SplitRecommendation(
            cluster_id=cluster_id,
            should_split=False,
            reason=f"Split would not significantly improve cohesion (improvement={improvement:.3f})",
            current_cohesion=cohesion,
        )

    return SplitRecommendation(
        cluster_id=cluster_id,
        should_split=True,
        reason=f"Found {n_subclusters} natural sub-clusters with avg cohesion {avg_subcluster_cohesion:.3f} (vs current {cohesion.avg_similarity:.3f})",
        current_cohesion=cohesion,
        suggested_subclusters=list(subclusters.values()),
        subcluster_cohesions=subcluster_cohesions,
    )


def analyze_project_clusters(
    project_id: str,
    clusters: List[Dict],
    vector_store: Optional[VectorStore] = None,
    loose_threshold: float = LOOSE_CLUSTER_THRESHOLD,
) -> ClusterHealthReport:
    """
    Analyze all clusters in a project for quality issues.

    Parameters:
        project_id (str): Project ID to analyze.
        clusters (List[Dict]): List of cluster dicts with 'id' and 'feedback_ids'.
        vector_store (Optional[VectorStore]): VectorStore instance for fetching embeddings.
        loose_threshold (float): Avg similarity below this = "loose" cluster.

    Returns:
        ClusterHealthReport: Summary of cluster health with split recommendations.
    """
    if vector_store is None:
        vector_store = VectorStore()

    report = ClusterHealthReport(
        project_id=project_id,
        total_clusters=len(clusters),
        healthy_clusters=0,
        loose_clusters=0,
    )

    for cluster in clusters:
        cluster_id = cluster["id"]
        feedback_ids = cluster.get("feedback_ids", [])

        if len(feedback_ids) < 2:
            report.healthy_clusters += 1
            continue

        # Fetch embeddings for this cluster
        try:
            # Use a query approach to get embeddings
            embeddings_list = vector_store.fetch_cluster_embeddings(
                cluster_id=cluster_id,
                project_id=project_id,
                max_samples=50,  # Limit for performance
            )

            if len(embeddings_list) < 2:
                report.healthy_clusters += 1
                continue

            # Build embeddings dict (we don't have IDs from fetch, use indices)
            # For proper analysis we'd need to fetch IDs too, but this works for cohesion calc
            cohesion = calculate_cluster_cohesion(embeddings_list, cluster_id)

            if cohesion.avg_similarity >= loose_threshold:
                report.healthy_clusters += 1
            else:
                report.loose_clusters += 1

                # For loose clusters, do detailed split analysis
                # Note: This is simplified - in production we'd need proper ID mapping
                embeddings_dict = {str(i): emb for i, emb in enumerate(embeddings_list)}
                fake_ids = [str(i) for i in range(len(embeddings_list))]

                recommendation = analyze_cluster_for_split(
                    cluster_id=cluster_id,
                    feedback_ids=fake_ids,
                    embeddings=embeddings_dict,
                )

                if recommendation.should_split:
                    report.split_recommendations.append(recommendation)

        except Exception as e:
            logger.warning(f"Failed to analyze cluster {cluster_id}: {e}")
            continue

    return report


def find_outliers_in_cluster(
    feedback_ids: List[str],
    embeddings: Dict[str, List[float]],
    outlier_threshold: float = 0.60,
) -> List[Tuple[str, float]]:
    """
    Find items that don't fit well in a cluster (potential outliers).

    An outlier is an item whose average similarity to other cluster members
    is below the threshold.

    Parameters:
        feedback_ids (List[str]): IDs of feedback items in the cluster.
        embeddings (Dict[str, List[float]]): Map of feedback_id to embedding.
        outlier_threshold (float): Below this avg similarity = outlier.

    Returns:
        List[Tuple[str, float]]: List of (feedback_id, avg_similarity) for outliers,
            sorted by similarity (worst first).
    """
    outliers = []

    # Get valid embeddings
    valid_items = [(fid, embeddings[fid]) for fid in feedback_ids if fid in embeddings]

    if len(valid_items) < 2:
        return []

    for i, (fid, emb) in enumerate(valid_items):
        # Calculate average similarity to other items
        similarities = []
        for j, (other_fid, other_emb) in enumerate(valid_items):
            if i != j:
                similarities.append(_cosine_similarity(emb, other_emb))

        avg_sim = sum(similarities) / len(similarities)

        if avg_sim < outlier_threshold:
            outliers.append((fid, avg_sim))

    # Sort by similarity (worst first)
    outliers.sort(key=lambda x: x[1])

    return outliers


__all__ = [
    "SplitRecommendation",
    "ClusterHealthReport",
    "analyze_cluster_for_split",
    "analyze_project_clusters",
    "find_outliers_in_cluster",
    "LOOSE_CLUSTER_THRESHOLD",
    "SPLIT_SIMILARITY_THRESHOLD",
]
