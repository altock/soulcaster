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
    Construct text snippets for embedding from issue/feedback dictionaries.

    Each issue is expected to contain title/body/raw_text keys; body is
    truncated to `truncate_body_chars` to bound embedding payload size.
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
    Lazily construct a Gemini client. Separated for testability/mocking.
    Prefers GEMINI_API_KEY, falls back to GOOGLE_API_KEY.
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
    Embed a list of texts using Gemini embeddings (cosine-normalized).

    Raises RuntimeError when the Google API key is missing or the client is
    unavailable. Complexity: O(n) embedding calls; normalization O(n·d).
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
    """Cosine similarity for L2-normalized vectors."""
    return float(np.dot(a, b))


# ---------------------------------------------------------------------------
# Clustering strategies
# ---------------------------------------------------------------------------
def cluster_agglomerative(embeddings: np.ndarray, sim_threshold: float = DEFAULT_SIM_THRESHOLD) -> np.ndarray:
    """
    Agglomerative clustering (average linkage, cosine distance threshold).

    Time: ~O(n^2)–O(n^3); Memory: ~O(n^2); n = items.
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
    Greedy centroid assignment.

    Time: O(n·k·d); n = items, k = clusters, d = embedding dim.
    """
    if embeddings.size == 0:
        return np.array([], dtype=int)

    centroids: List[np.ndarray] = []
    labels: List[int] = []
    for emb in embeddings:
        if not centroids:
            labels.append(0)
            centroids.append(emb.copy())
            continue
        sims = [cosine(emb, c) for c in centroids]
        best_idx = int(np.argmax(sims))
        if sims[best_idx] >= sim_threshold:
            k = best_idx
            count_k = labels.count(k)
            centroids[k] = (centroids[k] * count_k + emb) / (count_k + 1)
            labels.append(k)
        else:
            labels.append(len(centroids))
            centroids.append(emb.copy())
    return np.asarray(labels, dtype=int)


def cluster_vector_like(embeddings: np.ndarray, sim_threshold: float = DEFAULT_SIM_THRESHOLD) -> np.ndarray:
    """
    Greedy nearest-prior baseline (vector-like).

    Time: O(n^2·d); baseline for experiments, not ANN.
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
    Cluster issues using the selected strategy.

    Returns a dict containing:
        - labels: np.ndarray of cluster labels per issue (singletons allowed)
        - clusters: list[list[int]] index groups (filtered by min_cluster_size)
        - singletons: list[int] of singleton indices
        - texts: list[str] prepared text payloads
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
