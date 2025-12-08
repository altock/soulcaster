# COGS (Cost of Goods Sold) Analysis

This document provides a cost analysis for the Soulcaster architecture based on the current implementation and planned migration to Sevalla for the backend.

## 1. Executive Summary

**Estimated Monthly Cost (MVP / Low Volume):** ~$100 - $150 / month
**Estimated Monthly Cost (Growth / Medium Volume):** ~$300 - $500 / month

**Key Cost Drivers:**
1.  **LLM Usage (Variable):** The "Generate Fix" feature is the most expensive per-unit operation due to large context windows (reading repo files) and complex reasoning.
2.  **Vercel Team (Fixed):** $40/mo base for 2 members.
3.  **Backend Hosting (Fixed/Step):** Sevalla container costs.

---

## 2. Infrastructure Breakdown

### A. Dashboard (Frontend)
**Provider:** Vercel
**Plan:** Pro Team (2 members)

| Item | Cost Basis | Monthly Estimate | Notes |
|------|------------|------------------|-------|
| **Seat Pricing** | $20 / user / month | **$40.00** | Fixed cost for 2 team members. |
| **Bandwidth** | 1TB included | $0.00 | Unlikely to exceed in MVP. |
| **Serverless Functions** | 1M GB-hours included | $0.00 | Dashboard API routes are lightweight. |
| **Total** | | **$40.00** | |

### B. Backend & Ingestion
**Provider:** Sevalla (Application Hosting)
**Architecture:** FastAPI backend (`backend/main.py`) + Reddit Poller.

*Assumption: Sevalla pricing is comparable to standard PaaS (e.g., Heroku/Render/Railway) where a decent production container is ~$20-30/mo.*

| Component | Spec Estimate | Monthly Estimate | Notes |
|-----------|---------------|------------------|-------|
| **Backend API** | Standard Container (e.g., 1 vCPU, 512MB-1GB RAM) | **$25.00** | Handles ingestion & coordination. |
| **Reddit Poller** | Small Container (e.g., Shared CPU, 512MB RAM) | **$10.00** | Can be consolidated into the Backend container to save costs initially. |
| **Total** | | **$35.00** | |

### C. Data Layer (Option 1: Upstash - Current Plan)
**Provider:** Upstash (Serverless Redis & Vector)

| Component | Usage Estimate (MVP) | Monthly Estimate | Notes |
|-----------|----------------------|------------------|-------|
| **Redis** | ~100k commands/day | **$10.00** | Capped plan or pay-as-you-go. Free tier might suffice initially. |
| **Vector** | ~10k vectors | **$10.00** | Storing embeddings for feedback clustering. |
| **Total** | | **$20.00** | |

### C. Data Layer (Option 2: MongoDB Atlas - Credit Applied)
**Provider:** MongoDB Atlas
**Credits Available:** $100

| Component | Spec Estimate | Monthly Estimate | Notes |
|-----------|---------------|------------------|-------|
| **Database** | M10 Cluster (General Purpose) | ~$60.00 | Good starting point for production. |
| **Vector Search** | Atlas Vector Search | Included | Part of the cluster resources. |
| **Net Cost** | (After Credits) | **$0.00** | **Free for ~1.5 months** with $100 credit. |
| **Total (Post-Credit)** | | **$60.00** | More expensive than Upstash long-term, but more powerful. |

### D. Compute & Workers (Fargate)
**Provider:** AWS Fargate (ECS)
**Workload:**
1.  **Coding Agent:** Ephemeral tasks. Runs only when "Generate Fix" is clicked.
2.  **Clustering Worker:** Planned to move to Fargate (per `clustering_worker_architecture_plan.md`) to run on-schedule or on-demand.

*Assumptions:*
*   **Coding Agent:** 5 mins/run, 1 vCPU, 2GB RAM. 5 runs/day.
*   **Clustering Worker:** 2 mins/run, 0.5 vCPU, 1GB RAM. Runs every 15 mins (96 runs/day).

| Item | Calculation | Monthly Estimate | Notes |
|------|-------------|------------------|-------|
| **Coding Agent** | (Low volume) | < $2.00 | Very cheap at low volume. |
| **Clustering Worker** | ~100 runs/day * 2 mins | < $3.00 | Cheaper than a 24/7 Sevalla container ($15+) for this workload. |
| **NAT Gateway** | (Optional) | **$30.00** | **Warning:** If running in private subnets, NAT Gateway is expensive. Use Public Subnets for MVP to save this cost. |
| **Total** | | **$5.00 - $35.00** | Depends heavily on VPC networking choice. |

### E. AI & LLM Costs (The Variable Beast)
**Provider:** Google Gemini (via Vertex AI or AI Studio) / Minimax
**Models:** Gemini 1.5 Pro (Coding), Gemini 1.5 Flash (Clustering/Summarization)

#### 1. Clustering & Summarization (Cheap)
*   **Volume:** 100 feedback items/day.
*   **Model:** Gemini 1.5 Flash (High speed, low cost).
*   **Cost:** ~$0.35 / 1M tokens.
*   **Estimate:** **<$5.00 / month**.

#### 2. Coding Agent "Generate Fix" (Expensive)
*   **Volume:** 5 fixes / day.
*   **Context:** The agent reads code files. A small repo might be 50k tokens. A large one 200k+.
*   **Model:** Gemini 1.5 Pro (Required for reasoning/coding capability).
*   **Pricing (Approx):** Input: $3.50 / 1M tokens. Output: $10.50 / 1M tokens.
*   **Per Run Cost:**
    *   Input: 100k tokens * $3.50/1M = $0.35
    *   Output: 2k tokens * $10.50/1M = $0.02
    *   Total: ~$0.37 per fix.
*   **Monthly Cost:** 5 fixes/day * 30 days * $0.37 = **$55.50**.

---

## 3. Alternative Options & Modern Stack (2025 Edition)

### A. Compute Alternatives (Coding Agent)

If AWS Fargate feels too heavy or you want faster startup times:

1.  **Fly.io (Firecracker MicroVMs):**
    *   **Tech:** Runs Docker containers on Firecracker microVMs. Fast boot (<300ms).
    *   **Cost:** Pay for active CPU/RAM seconds. A "Performance" machine (1 vCPU, 2GB RAM) is ~$0.000005/sec.
    *   **Pros:** No NAT gateway costs, global distribution, very fast.
    *   **Cons:** Ephemeral storage handling requires care (Volumes).

2.  **DigitalOcean (Droplets / App Platform):**
    *   **Tech:** Standard VPS or PaaS.
    *   **Cost:** Basic Droplet starts at **$4/mo**. App Platform container ~$5-10/mo.
    *   **Pros:** Simple, predictable pricing.
    *   **Cons:** Slower scaling than Fargate/Fly; you pay for idle time unless you spin up/down dynamically via API (which is slow).

3.  **Modal (Serverless Python):**
    *   **Tech:** Specialized serverless platform for Python/AI workloads.
    *   **Cost:** Pay strictly for execution time.
    *   **Pros:** Incredible developer experience for Python agents, instant startup, built-in mounting of secrets/volumes.
    *   **Cons:** Vendor lock-in to their SDK.

4.  **E2B (Sandboxed Environments):**
    *   **Tech:** Secure, sandboxed cloud environments specifically for AI agents.
    *   **Cost:** Usage-based (~$0.005/min).
    *   **Pros:** Best-in-class security for running untrusted code (e.g., if the agent runs tests).

### B. LLM Alternatives (Coding & Reasoning - 2025 Frontier)

*Pricing sourced from OpenRouter and official provider docs (Late 2024/2025).*

1.  **DeepSeek V3.2 Family (The Budget Revolution):**
    *   **DeepSeek V3.2 Speciale:** Pushes open-source reasoning to the limit, achieving performance comparable to top proprietary models on competitive benchmarks. Highly effective for agentic tasks requiring multi-step planning and formal logic.
    *   **DeepSeek V3.2 Standard:** An efficient, general-purpose model suitable for everyday tasks (chat, content creation).
    *   **DeepSeek-Coder-V2:** A specialized Mixture-of-Experts (MoE) model with performance comparable to models like GPT-4 Turbo in code-specific tasks, supporting over 300 programming languages.
    *   **Cost:** **$0.27 / 1M Input**, **$1.10 / 1M Output**.
    *   **Verdict:** **~10x cheaper** than Claude 4.5 Sonnet. The clear winner for high-volume loops or self-correcting agents.

2.  **Anthropic Claude 4.5 Sonnet (The Premium Standard):**
    *   **Performance:** The flagship for complex agents and coding reliability.
    *   **Cost:** **$3.00 / 1M Input**, **$15.00 / 1M Output**.
    *   **Verdict:** Use this when you need the absolute highest reliability and reasoning capability.

3.  **Google Gemini 3 Pro:**
    *   **Performance:** Strong multimodal reasoning (text, image, video, audio) with a massive 1M+ context window.
    *   **Cost:** **$2.00 / 1M Input**, **$12.00 / 1M Output**.
    *   **Verdict:** Excellent value for large-context tasks (e.g., analyzing entire repos at once).

4.  **OpenAI GPT-5.1:**
    *   **Performance:** Top-tier model for coding and agentic tasks.
    *   **Cost:** **$1.25 / 1M Input**, **$10.00 / 1M Output**.
    *   **Verdict:** Surprisingly competitive pricing for a flagship model, undercutting Claude 4.5 Sonnet on input costs.

### C. OpenAI GPT-OSS Models (Open Weights)

*Pricing varies significantly by provider. "gpt-oss-120b" is the flagship MoE, "gpt-oss-20b" is the efficient mid-tier.*

| Provider | Model | Input / 1M | Output / 1M | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **OpenRouter** | gpt-oss-120b | **$0.039** | **$0.19** | **Cheapest Option.** Aggressive pricing for high volume. |
| **DeepInfra** | gpt-oss-120b | $0.05 | $0.45 | Reliable infrastructure, good middle ground. |
| **Groq** | gpt-oss-120b | $0.15 | $0.75 | Premium for extreme speed (LPU inference). |
| **Bedrock** | gpt-oss-120b | $0.15 | $0.60 | Enterprise-grade SLA via AWS. |
| **DeepInfra** | gpt-oss-20b | **$0.04** | **$0.15** | Extremely cheap for simpler tasks. |
| **Groq** | gpt-oss-20b | $0.10 | $0.50 | Fast inference for mid-tier tasks. |

**Verdict:** Use **OpenRouter** for bulk processing of `gpt-oss-120b` to get the absolute lowest price ($0.039/1M input). Use **Groq** if latency is critical.

### D. LLM Alternatives (Ingestion & Real-Time)

1.  **Meta Llama 4 Maverick (via Groq/Cerebras):**
    *   **Performance:** The latest major release (April 2025). When run on **Cerebras CS-3** or **Groq LPUs**, achieves inference speeds >1000 tokens/sec.
    *   **Verdict:** The only choice for real-time, user-facing ingestion pipelines where latency must be sub-100ms.

2.  **Gemini 2.0 Flash:**
    *   **Pros:** Designed specifically for the agentic era with fast responses and strong performance.
    *   **Verdict:** Excellent middle ground for ingestion that requires some reasoning capability.

### E. Reddit Data Alternatives

Since the official Reddit API is expensive and restricted:

1.  **Apify (Reddit Scraper):**
    *   **Method:** Pre-built "Actors" that scrape Reddit pages.
    *   **Cost:** Usage-based. ~$5 for 1000s of results.
    *   **Pros:** Easy to integrate, handles proxies/rotation for you.

2.  **Bright Data / ZenRows:**
    *   **Method:** Scraping Browser APIs. You send a URL, they return HTML/JSON.
    *   **Cost:** CPM (Cost Per Mille) model. ~$2-3 per 1000 successful requests.
    *   **Pros:** extremely reliable, enterprise-grade compliance.

3.  **RapidAPI (Third-party wrappers):**
    *   **Method:** Various unofficial APIs.
    *   **Cost:** Subscription based ($10-$50/mo).
    *   **Pros:** Simple REST API.
    *   **Cons:** Reliability depends on the individual maintainer.

---

## 4. Total Cost Projection (With MongoDB Credits)

| Category | MVP (Low Volume) | Growth (Medium Volume) |
|----------|------------------|------------------------|
| **Frontend (Vercel)** | $40 | $40 (assuming same team size) |
| **Backend (Sevalla)** | $35 | $70 (Scale up containers) |
| **Data (MongoDB)** | **$0** (Credits) | $60 (Post-credits) |
| **Compute (AWS)** | $5 | $30 (More fixes + NAT Gateway) |
| **AI / LLM** | $60 | $300 (50 fixes/day) |
| **TOTAL** | **~$140 / month** | **~$500 / month** |

*Note: Using MongoDB credits saves ~$20/mo initially compared to Upstash, but the long-term run rate for a production Atlas cluster (~$60/mo) is higher than serverless Redis (~$20/mo) for low volumes.*

---

## 5. Optimization Opportunities

1.  **Networking (AWS):** Ensure your Fargate tasks run in **Public Subnets** with "Auto-assign Public IP" enabled. This avoids the need for a NAT Gateway (~$30/mo) or VPC Endpoints.
2.  **LLM Selection:**
    *   Use **Gemini 1.5 Flash** for the initial "Analysis" phase of the coding agent if possible. Only switch to Pro for the final code generation.
    *   Cache repo context if the provider supports context caching (Gemini does) to reduce input token costs on repeated runs for the same repo.
3.  **Sevalla Consolidation:** Run the Reddit Poller as a background thread within the main Backend container to save the $10/mo worker container cost.
4.  **Upstash Free Tier:** Utilize the free tier for development/staging environments.

## 6. Unit Economics (Per "Fix")

To understand your margins, it is helpful to look at the cost per "Unit of Value" (a generated fix).

*   **Compute:** ~$0.05
*   **AI/LLM:** ~$0.40 - $1.00 (depending on repo size)
*   **Overhead:** ~$0.10 (amortized hosting)

**Total Cost per Fix:** **~$0.55 - $1.15**

*If you plan to charge for this service, pricing should likely be in the $5 - $10 per fix range (or a subscription covering X fixes) to cover these costs and development time.*