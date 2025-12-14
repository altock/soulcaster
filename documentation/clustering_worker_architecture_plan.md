# Clustering Architecture Plan (Backend In-Process Async)

This document focuses on a single question:

> How do we move clustering off Vercel’s `/dashboard/app/api` and into the **backend**, while keeping the current Redis/Upstash data model **without introducing a separate clustering service**?

**Note:** This file originally proposed a separate “clustering worker” (ECS/Fargate task). That approach is now explicitly **deferred to a future scaling phase** (see §6). The near-term plan is **backend-owned, in-process async clustering**.

**Status:** ✅ **IMPLEMENTED** (Phase 4 complete). Backend in-process async clustering is now live. All clustering runs asynchronously in the backend process, with Redis locks preventing concurrent runs. Dashboard is status-only (no inline clustering). See `tasks/IMPLEMENTATION_ROADMAP.md` Phase 4 for completion checklist.

It builds on:

- `documentation/current_architecture.md` – snapshot of how things work today.
- `documentation/ingestion_polling_architecture_plan.md` – ingestion & Reddit poller.
- `documentation/api_workers_architecture_plan.md` – overall API + workers shaping.

---

## 1. Problem & Goals

### 1.1 Today’s pain points

- Clustering runs inside Next.js API routes:
  - `/app/api/clusters/run` – centroid-based clustering + summaries.
  - `/app/api/clusters/run-vector` – Upstash Vector + Gemini embeddings + summaries.
- Those routes:
  - Execute heavy embedding + clustering + summarization inside a Vercel runtime.
  - Hold open HTTP requests while doing work (fragile under time limits/concurrency).
  - Encourage a manual “Run clustering” button as an operational crutch.
- Backend (FastAPI) still does heuristic `_auto_cluster_feedback` on ingest, so there are **competing clustering stories**.

### 1.2 What we want instead

High-level objectives:

- **Backend is the single clustering engine**
  - Ingestion writes feedback and marks it unclustered.
  - Clustering reads unclustered and produces `cluster:*` state.
- **Async semantics without a separate service**
  - Clustering runs in the backend process as a background task.
  - UI never blocks on clustering.
- **Dashboard becomes status-only**
  - Remove the “Run clustering” button in production.
  - UI displays clustering status and results.
- **Keep the existing Redis/Upstash data model**
  - Continue using project-scoped keys (`feedback:unclustered:{projectId}`, `cluster:{projectId}:{id}`, etc.).

---

## 2. Target Responsibility Split (Updated)

```mermaid
graph TB
    subgraph "Backend (FastAPI)"
        B1[Ingestion API<br/>POST /ingest/*]
        B2[Cluster Reads<br/>GET /clusters]
        B3[Clustering Jobs<br/>POST /cluster-jobs<br/>GET /cluster-jobs/{id}]
        B4[In-process Runner<br/>async task + Redis lock]
    end
    
    subgraph "Dashboard (Next.js)"
        D1[UI Components]
        D2[Status Views<br/>poll job/status]
    end
    
    subgraph "Storage"
        R1[Redis<br/>feedback:*, cluster:*<br/>cluster_job:*<br/>cluster:lock:*]
        R2[Upstash Vector<br/>embeddings]
    end
    
    B1 -->|Write feedback<br/>SADD feedback:unclustered| R1
    B1 -->|Maybe start clustering| B4

    B4 -->|Read unclustered| R1
    B4 -->|Generate embeddings| R2
    B4 -->|Query similar| R2
    B4 -->|Write clusters + items| R1
    B4 -->|Update ClusterJob| R1

    D1 -->|Display clusters| B2
    D2 -->|Poll status| B3
    
    style B1 fill:#e1f5ff
    style B2 fill:#e1f5ff
    style B3 fill:#e1f5ff
    style B4 fill:#e8f5e9
    style D1 fill:#fff4e1
    style D2 fill:#fff4e1
```

---

## 3. Backend In-Process Design

### 3.1 Triggering: on ingest (Option B)

The backend should attempt to start clustering after ingest writes complete.

- Example triggers:
  - End of GitHub sync (`POST /ingest/github/sync/...`) after batch write + closed pruning.
  - Manual ingest (`POST /ingest/manual`) after write.
  - Reddit poller ingest callback after write.

Trigger rule:

- **If a clustering job is already running for this project, do nothing.**
- **If not running, start an async clustering job in-process.**

A manual trigger endpoint can exist for debugging (`POST /cluster-jobs`), but the dashboard should not require a “Run clustering” button.

### 3.2 Concurrency & locking (required)

Because the backend may run with multiple workers/replicas, the in-process runner must be guarded by a Redis lock.

Recommended key:

- `cluster:lock:{projectId}`

Recommended acquisition:

- `SET cluster:lock:{projectId} <job_id> NX EX <ttl_seconds>`

Notes:

- The lock TTL should be long enough for a typical run; refresh/heartbeat if runs may exceed TTL.
- On startup of a job, write `ClusterJob.status=running` and `started_at`.
- If the process crashes mid-run, the lock expires and a future ingest can restart clustering.

### 3.3 ClusterJob persistence (backend-owned)

Store job metadata in Redis so the UI can show status.

Suggested keys:

- `cluster_job:{projectId}:{jobId}` (hash)
- `cluster_jobs:{projectId}:recent` (sorted set; score=timestamp, member=jobId)

Suggested fields:

- `id`, `project_id`
- `status`: `pending | running | succeeded | failed`
- `created_at`, `started_at?`, `finished_at?`
- `stats`: clustered count, new/updated clusters, embedding failures, missing feedback, duration
- `error?`

### 3.4 Manual retry (dashboard-proxied)

Automatic kicks should cover 99% of cases, but operators still need a deterministic way to re-run clustering if they open the Clusters tab and see unclustered drift. The plan:

1. **Backend contract** — keep `POST /cluster-jobs?project_id=...` and `GET /cluster-jobs` as the single control plane for retries. If a job is already running the POST returns the existing job metadata so the UI can simply display status.
2. **Dashboard proxy** — add `/app/api/clusters/jobs` (POST + GET) that forward to the backend exactly like `/api/clusters` or the GitHub sync route. This avoids leaking backend credentials to the browser and keeps CORS simple.
   - `GET /cluster-jobs` responds with an envelope (`{"jobs": [...], "project_id": "<uuid>"}`) so we can tack on metadata later. The proxy simply forwards that body and the Clusters UI always reads from `.jobs` when showing the latest run.
3. **UI behavior** — when `unclusteredCount > 0`, show a “Retry clustering” button that calls the proxy POST. Disable it while a job is running and surface the last job’s timestamps + counters. The same proxy GET endpoint lets the UI poll job status (or fetch the latest job on page load).
4. **Empty-state messaging** — the Clusters page already shows “Clustering runs automatically after ingestion.” Extend that to include the retry affordance so operators know they can press the button only if something looks stuck.

This approach mirrors the new GitHub “Sync sources” UX: the dashboard never calls backend private routes directly from the browser, all actions are proxied through Next.js API handlers, and the backend stays the single owner of clustering orchestration.

### 3.5 Clustering strategies (backend implementation)

**Reference implementation (inlined):** The snippets below are copied from the local experiment notebook so this repo remains self-contained (no machine-specific paths).

The backend will implement *three* clustering strategies behind a single interface (e.g., `cluster_issues(..., method=...)`) so we can compare quality over time. **Production defaults to the best-performing method** from local experiments.

#### Strategy A — Agglomerative (default)

- **What**: Average-linkage hierarchical clustering over cosine distance, cut at `distance_threshold = 1 - sim_threshold`.
- **Why**: Best quality in the notebook sweep around `sim_threshold≈0.72`.
- **Complexity**:
  - Time: typically ~\(O(n^2)\)–\(O(n^3)\) depending on implementation details
  - Memory: typically ~\(O(n^2)\)
  - Where \(n\) = number of items clustered in the batch

#### Strategy B — Centroid (optional switch)

- **What**: Greedy incremental assignment: for each item, join the most similar centroid if `sim >= threshold`, else create a new cluster; update centroid incrementally.
- **Complexity**: \(O(n·k·d)\) where \(k\) is number of clusters, \(d\) is embedding dimension (768).
- **Notes**: Order-dependent; thresholds that are too low can over-merge (matches observed “nonsense” behavior in the current dashboard route when using ~0.65).

#### Strategy C — Vector-like (optional switch; baseline only)

- **What**: Greedy “nearest prior neighbor” assignment above threshold (the notebook’s `vector_like_cluster`).
- **Complexity**: \(O(n^2·d)\) (compares each item to all prior items).
- **Important**: This is **not** Upstash Vector ANN clustering; it is a simulation baseline for experiments.

#### Configuration

- `CLUSTERING_METHOD`: `agglomerative | centroid | vector_like` (default `agglomerative`)
- `CLUSTERING_SIM_THRESHOLD`: default `0.72`
- `CLUSTERING_MIN_CLUSTER_SIZE`: default `2`
- `CLUSTERING_TRUNCATE_BODY_CHARS`: default `1500`

#### Reference code snippets (Python)

These are intentionally minimal and “copy/paste-able” for backend implementation. They mirror the experiment logic:

**(1) Embedding + normalization**

```python
import os
import numpy as np
from google import genai

genai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY")) if os.getenv("GOOGLE_API_KEY") else None

def embed_texts(texts, model_name="gemini-embedding-001"):
    if model_name.lower().startswith("gemini"):
        if genai_client is None:
            raise RuntimeError("GOOGLE_API_KEY not set")
        resp = genai_client.models.embed_content(
            model=model_name,
            contents=texts,
            config={"output_dimensionality": 768},
        )
        emb = np.asarray([e.values for e in resp.embeddings], dtype=np.float32)
    else:
        # Optional fallback (not required for backend v1)
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        emb = model.encode(texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True)
        emb = np.asarray(emb, dtype=np.float32)

    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return emb / norms

def cosine(a, b):
    # With L2-normalized vectors this is cosine similarity
    return float(np.dot(a, b))
```

**(2) Agglomerative (average linkage, cosine distance threshold)**

```python
import sklearn
from packaging import version
from sklearn.cluster import AgglomerativeClustering

def agglomerative_cluster(embeddings, sim_threshold=0.72):
    # cosine distance = 1 - cosine similarity
    dist_threshold = 1.0 - float(sim_threshold)

    kwargs = dict(n_clusters=None, linkage="average", distance_threshold=dist_threshold)
    if version.parse(sklearn.__version__) >= version.parse("1.2"):
        kwargs["metric"] = "cosine"
    else:
        kwargs["affinity"] = "cosine"

    cl = AgglomerativeClustering(**kwargs)
    labels = cl.fit_predict(embeddings)
    return labels
```

**(3) Vector-like (greedy nearest prior neighbor baseline)**

```python
import numpy as np

def vector_like_cluster(embeddings, threshold=0.72):
    labels = []
    next_cluster = 0
    for i, emb in enumerate(embeddings):
        sims = [cosine(emb, embeddings[j]) for j in range(i)]
        similars = [j for j, s in enumerate(sims) if s >= threshold]
        if similars:
            labels.append(labels[similars[0]])
        else:
            labels.append(next_cluster)
            next_cluster += 1
    return np.array(labels, dtype=int)
```

**(4) Centroid-like (greedy assignment to best centroid)**

```python
import numpy as np

def centroid_cluster(embeddings, threshold=0.72):
    centroids = []
    labels = []
    for emb in embeddings:
        if not centroids:
            labels.append(0)
            centroids.append(emb.copy())
            continue
        sims = [cosine(emb, c) for c in centroids]
        best_idx = int(np.argmax(sims))
        if sims[best_idx] >= threshold:
            k = best_idx
            count_k = labels.count(k)
            centroids[k] = (centroids[k] * count_k + emb) / (count_k + 1)
            labels.append(k)
        else:
            labels.append(len(centroids))
            centroids.append(emb.copy())
    return np.array(labels, dtype=int)
```

### 3.5 Default production algorithm (how a run proceeds)

Regardless of strategy, the backend job follows the same outer loop:

1. **Fetch unclustered IDs**
   - `SMEMBERS feedback:unclustered:{projectId}`
   - If empty: mark job as `succeeded` with `clustered=0` and exit.
2. **Fetch feedback documents**
   - Load `feedback:{projectId}:{id}` for each id.
   - Track missing IDs and remove them from the unclustered set.
3. **Generate embeddings**
   - Use Gemini embeddings for each feedback item (normalize embeddings for cosine similarity).
   - If an item fails embedding, leave it in `feedback:unclustered` for retry.
4. **Assign clusters**
   - Run the selected strategy (default: agglomerative @ 0.72).
5. **Summarize clusters**
   - For each cluster we persist, summarize using Gemini text generation.
   - Store `title`, `summary`, `issue_title`, `issue_description`, and optional `github_repo_url`.
6. **Persist to Redis (batched/pipelined)**
   - Upsert `cluster:{projectId}:{clusterId}`
   - Replace `cluster:{projectId}:{clusterId}:items` membership set
   - Ensure `SADD clusters:{projectId}:all clusterId`
   - Mark processed feedback as clustered (optional, but consistent with dashboard)
   - `SREM feedback:unclustered:{projectId}` for successfully processed IDs and missing IDs

### 3.6 Failure modes and safety

- **Duplicate runs**: prevented by Redis lock.
- **Backend restarts mid-run**: lock TTL expires; unprocessed IDs remain in `feedback:unclustered`.
- **Partial failures (embeddings/LLM)**:
  - Keep failed IDs in `feedback:unclustered` for retry.
  - Update job stats to surface failures.
- **Idempotency**:
  - Re-running should converge because membership and cluster hashes are rewritten deterministically for changed clusters.

---

## 4. Dashboard Changes (Status Only)

- Remove the “Run clustering” button in production.
- Dashboard should:
  - Render clusters from backend `GET /clusters`.
  - Show clustering status from backend job endpoints.
  - Optionally display pending count: `|feedback:unclustered|`.

The dashboard must not perform embeddings, clustering, or summarization in production.

---

## 5. Migration Plan (Incremental)

### Phase A — Stop heuristic clustering on ingest

- Remove or gate `_auto_cluster_feedback` for all ingest paths.
- Ingest becomes: write feedback + mark unclustered.

### Phase B — Implement ClusterJob + in-process runner

- Add ClusterJob model + Redis persistence.
- Add Redis lock per project.
- Add background runner that consumes `feedback:unclustered:{projectId}`.

### Phase C — Deprecate dashboard clustering routes

- Remove or dev-gate `/app/api/clusters/run*`.
- UI becomes status-only.

---

## 6. Future (Deferred): External Clustering Worker Service

If/when clustering load outgrows the backend process, the next scaling step is to run clustering as a separate worker (ECS/Fargate task) triggered by `POST /cluster-jobs` or a schedule.

That future design would:

- Keep the same Redis/Upstash contract.
- Replace “in-process runner” with “external worker container”.
- Keep the same ClusterJob model and job status endpoints.

This is explicitly **not required** for the current plan and should not block shipping backend-owned clustering.
