"""
Backend clustering core strategies and embedding helpers.

Implements three clustering strategies (agglomerative, centroid, vector_like)
behind a shared interface. This module is intentionally pure/testable and does
not access Redis. It mirrors the reference snippets in
`documentation/clustering_worker_architecture_plan.md` (see “Reference code
snippets (Python)”) which originate from the local experiment notebook.
"""

import os
from typing import Iterable, List, Literal, Sequence, Tuple, Union

import numpy as np
import sklearn
from packaging import version
from sklearn.cluster import AgglomerativeClustering

try:
    from google import genai  # type: ignore
except ImportError:  # pragma: no cover - guard for environments without google-genai installed
    genai = None

# ---------------------------------------------------------------------------
# Config defaults (can be overridden by env vars)
# ---------------------------------------------------------------------------
DEFAULT_METHOD: Literal["agglomerative", "centroid", "vector_like"] = os.getenv(
    "CLUSTERING_METHOD", "agglomerative"
).lower()  # type: ignore[assignment]
DEFAULT_SIM_THRESHOLD: float = float(os.getenv("CLUSTERING_SIM_THRESHOLD", "0.72"))
DEFAULT_MIN_CLUSTER_SIZE: int = int(os.getenv("CLUSTERING_MIN_CLUSTER_SIZE", "2"))
DEFAULT_TRUNCATE_BODY_CHARS: int = int(os.getenv("CLUSTERING_TRUNCATE_BODY_CHARS", "1500"))


# ---------------------------------------------------------------------------
# Text preparation
# ---------------------------------------------------------------------------
def prepare_issue_texts(
    issues: Iterable[dict], truncate_body_chars: int = DEFAULT_TRUNCATE_BODY_CHARS
) -> List[str]:
    """
    Create text snippets from issue dictionaries for embedding.
    
    For each issue, uses the "title" and either "body" or "raw_text" to produce a single string:
    - If both title and body/raw_text are present: "title\n\nbody"
    - If only title is present: "title"
    - If only body/raw_text is present: "body"
    
    Parameters:
        issues (Iterable[dict]): Iterable of issue/feedback dictionaries.
        truncate_body_chars (int): Maximum number of characters to keep from the body/raw_text;
            a falsy value (e.g., 0 or None) disables truncation.
    
    Returns:
        List[str]: Prepared text snippets, one per input issue.
    """
    texts: List[str] = []
    for issue in issues:
        title = (issue.get("title") or "").strip()
        body = (issue.get("body") or issue.get("raw_text") or "").strip()
        if truncate_body_chars and len(body) > truncate_body_chars:
            body = body[:truncate_body_chars]
        if title and body:
            texts.append(f"{title}\n\n{body}")
        elif title:
            texts.append(title)
        else:
            texts.append(body)
    return texts


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
def _get_genai_client():
    """
    Constructs a Gemini client using the GEMINI_API_KEY or GOOGLE_API_KEY environment variables.
    
    Returns:
        genai.Client: Authenticated Gemini client.
    
    Raises:
        RuntimeError: if neither GEMINI_API_KEY nor GOOGLE_API_KEY is set.
        RuntimeError: if the `google-genai` library is not installed.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    if genai is None:
        raise RuntimeError("google-genai is not installed")
    return genai.Client(api_key=api_key)


def embed_texts_gemini(
    texts: Sequence[str],
    model: str = "gemini-embedding-001",
    output_dimensionality: int = 768,
) -> np.ndarray:
    """
    Compute L2-normalized Gemini embeddings for a sequence of texts.
    
    Parameters:
        texts (Sequence[str]): Texts to embed.
        model (str): Gemini embedding model name to use.
        output_dimensionality (int): Desired dimensionality of each embedding.
    
    Returns:
        np.ndarray: Float32 array of shape (n_texts, output_dimensionality) where each row is an L2-normalized embedding.
    
    Raises:
        RuntimeError: If the Gemini/Google API key is not set or the Gemini client is unavailable.
    """
    if not texts:
        return np.empty((0, output_dimensionality), dtype=np.float32)

    client = _get_genai_client()
    resp = client.models.embed_content(
        model=model,
        contents=list(texts),
        config={"output_dimensionality": output_dimensionality},
    )
    embeddings = np.asarray([e.values for e in resp.embeddings], dtype=np.float32)

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return embeddings / norms


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------
def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two L2-normalized vectors.
    
    Parameters:
        a (np.ndarray): First L2-normalized vector.
        b (np.ndarray): Second L2-normalized vector.
    
    Returns:
        similarity (float): Cosine similarity (dot product) of `a` and `b`.
    """
    return float(np.dot(a, b))


def _normalize_vector(vec: np.ndarray) -> np.ndarray:
    """
    Return a copy of the vector scaled to unit length when possible.
    
    Parameters:
        vec (np.ndarray): Vector to normalize.
    
    Returns:
        np.ndarray: L2-normalized vector (or the original vector when norm == 0).
    """
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


# ---------------------------------------------------------------------------
# Clustering strategies
# ---------------------------------------------------------------------------
def cluster_agglomerative(embeddings: np.ndarray, sim_threshold: float = DEFAULT_SIM_THRESHOLD) -> np.ndarray:
    """
    Group embeddings into clusters using agglomerative clustering with average linkage and a cosine-similarity threshold.
    
    Parameters:
        embeddings (np.ndarray): 2D array of L2-normalized embeddings with shape (n_samples, dim).
        sim_threshold (float): Similarity cutoff in the range [-1.0, 1.0]; two items with cosine similarity >= this value may be merged.
    
    Returns:
        np.ndarray: Integer label array of length n_samples assigning a cluster index to each embedding. Returns an empty integer array when `embeddings` is empty.
    """
    if embeddings.size == 0:
        return np.array([], dtype=int)

    dist_threshold = 1.0 - float(sim_threshold)
    kwargs = dict(n_clusters=None, linkage="average", distance_threshold=dist_threshold)
    if version.parse(sklearn.__version__) >= version.parse("1.2"):
        kwargs["metric"] = "cosine"
    else:  # pragma: no cover - compatibility path
        kwargs["affinity"] = "cosine"

    model = AgglomerativeClustering(**kwargs)
    return model.fit_predict(embeddings)


def cluster_centroid(embeddings: np.ndarray, sim_threshold: float = DEFAULT_SIM_THRESHOLD) -> np.ndarray:
    """
    Assign embeddings to clusters using a greedy centroid-based strategy.
    
    Each embedding is compared to existing cluster centroids by cosine similarity; if the highest similarity is greater than or equal to `sim_threshold`, the embedding is assigned to that cluster and the centroid is updated as the cluster's incremental average. If no centroid meets the threshold, a new cluster is created. If `embeddings` is empty, an empty integer array is returned.
    
    Parameters:
        sim_threshold (float): Cosine similarity threshold required to join an existing cluster.
    
    Returns:
        labels (np.ndarray): Integer array of cluster indices for each input embedding.
    """
    if embeddings.size == 0:
        return np.array([], dtype=int)

    centroids: List[np.ndarray] = []
    labels: List[int] = []
    for emb in embeddings:
        if not centroids:
            labels.append(0)
            centroids.append(_normalize_vector(emb.copy()))
            continue
        sims = [cosine(emb, c) for c in centroids]
        best_idx = int(np.argmax(sims))
        if sims[best_idx] >= sim_threshold:
            k = best_idx
            count_k = labels.count(k)
            updated = (centroids[k] * count_k + emb) / (count_k + 1)
            centroids[k] = _normalize_vector(updated)
            labels.append(k)
        else:
            labels.append(len(centroids))
            centroids.append(_normalize_vector(emb.copy()))
    return np.asarray(labels, dtype=int)


def cluster_vector_like(embeddings: np.ndarray, sim_threshold: float = DEFAULT_SIM_THRESHOLD) -> np.ndarray:
    """
    Assigns each embedding to the first earlier embedding whose cosine similarity meets the threshold, creating a new cluster when no prior match exists.
    
    Parameters:
        embeddings (np.ndarray): L2-normalized embedding vectors with shape (n_samples, dim).
        sim_threshold (float): Similarity cutoff in [−1, 1]; an embedding joins the first prior embedding with cosine similarity >= this value.
    
    Returns:
        np.ndarray: Integer array of cluster labels with length equal to the number of input embeddings. An empty input yields an empty integer array.
    """
    if embeddings.size == 0:
        return np.array([], dtype=int)

    labels: List[int] = []
    next_cluster = 0
    for i, emb in enumerate(embeddings):
        sims = [cosine(emb, embeddings[j]) for j in range(i)]
        similars = [j for j, s in enumerate(sims) if s >= sim_threshold]
        if similars:
            labels.append(labels[similars[0]])
        else:
            labels.append(next_cluster)
            next_cluster += 1
    return np.asarray(labels, dtype=int)


# ---------------------------------------------------------------------------
# Orchestration helper
# ---------------------------------------------------------------------------
def cluster_issues(
    issues: Iterable[dict],
    method: Literal["agglomerative", "centroid", "vector_like"] = DEFAULT_METHOD,
    sim_threshold: float = DEFAULT_SIM_THRESHOLD,
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    truncate_body_chars: int = DEFAULT_TRUNCATE_BODY_CHARS,
    embed_fn=embed_texts_gemini,
) -> dict:
    """
    Cluster prepared issue texts into groups using the chosen clustering strategy.
    
    Parameters:
        issues (Iterable[dict]): Iterable of issue/feedback mappings; each dict may contain title, body, or raw_text used to build the text payloads.
        method (Literal["agglomerative","centroid","vector_like"]): Clustering strategy to apply.
        sim_threshold (float): Similarity threshold in [0, 1] used to decide whether items belong to the same cluster.
        min_cluster_size (int): Minimum number of items for a group to be returned as a cluster; groups smaller than this become singletons.
        truncate_body_chars (int): Maximum number of characters to keep from each issue body when preparing texts (no truncation if None or 0).
        embed_fn (Callable[[Sequence[str]], np.ndarray]): Function that converts prepared texts into L2-normalized embedding vectors of shape (n_items, dim).
    
    Returns:
        dict: A mapping with the following keys:
            - "labels" (np.ndarray): Integer cluster label for each input issue.
            - "clusters" (List[List[int]]): Lists of indices for clusters whose size >= min_cluster_size.
            - "singletons" (List[int]): Indices of items assigned to groups smaller than min_cluster_size.
            - "texts" (List[str]): Prepared text payloads used as input to the embedding function.
    """
    texts = prepare_issue_texts(issues, truncate_body_chars=truncate_body_chars)
    embeddings = embed_fn(texts)

    if method == "agglomerative":
        labels = cluster_agglomerative(embeddings, sim_threshold=sim_threshold)
    elif method == "centroid":
        labels = cluster_centroid(embeddings, sim_threshold=sim_threshold)
    elif method == "vector_like":
        labels = cluster_vector_like(embeddings, sim_threshold=sim_threshold)
    else:  # pragma: no cover - defensive guard
        raise ValueError(f"Unknown clustering method: {method}")

    clusters: List[List[int]] = []
    singletons: List[int] = []
    for label in np.unique(labels):
        idxs = [i for i, lbl in enumerate(labels) if lbl == label]
        if len(idxs) >= min_cluster_size:
            clusters.append(idxs)
        else:
            singletons.extend(idxs)

    return {
        "labels": labels,
        "clusters": clusters,
        "singletons": singletons,
        "texts": texts,
    }


__all__ = [
    "prepare_issue_texts",
    "embed_texts_gemini",
    "cluster_agglomerative",
    "cluster_centroid",
    "cluster_vector_like",
    "cluster_issues",
    "DEFAULT_METHOD",
    "DEFAULT_SIM_THRESHOLD",
    "DEFAULT_MIN_CLUSTER_SIZE",
    "DEFAULT_TRUNCATE_BODY_CHARS",
]
