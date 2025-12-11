# COGS (Cost of Goods Sold) Analysis

This document provides a cost analysis for the Soulcaster architecture based on the current implementation and planned migration to Sevalla for the backend.

## 1. Executive Summary

**Estimated Monthly Cost (MVP / Low Volume):** ~$115 - $150 / month
**Estimated Monthly Cost (Growth / Medium Volume):** ~$500 - $600 / month

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
**Provider:** Google Gemini (Vertex AI / AI Studio) + alternatives
**Primary models:** Gemini 3 Pro (coding/reasoning), Gemini 2.5 Flash (clustering/summarization). No 3.0 Flash exists; 1.5 Flash/Pro are deprecated for new usage.

#### 1. Clustering & Summarization (Cheap)
*   **Volume:** 100 feedback items/day.
*   **Model:** Gemini 2.5 Flash (fast/cheap).
*   **Official pricing (text, per-1k-char billing converted to tokens @~4 chars/token):** Input **~$0.30 / 1M tokens eq.**, Output **~$2.50 / 1M tokens eq.**
*   **Estimate:** **~$1.50 - $2.00 / month** for ~100 feedback items/day (assumes ~100k input + ~10k output tokens/day); still comfortably <$3.00 at this volume.

#### 2. Coding Agent "Generate Fix" (Expensive)
*   **Volume:** 5 fixes / day.
*   **Context:** The agent reads code files. A small repo might be 50k tokens. A large one 200k+.
*   **Model:** Gemini 3 Pro (billed per 1k characters; shown here as per-1M-token equivalents using ~4 chars/token).
*   **Pricing (Vertex AI, ≤200k context):** Input **~$2.00 / 1M tokens eq.** (=$0.0005 per 1k chars), Output **~$12.00 / 1M tokens eq.** (=$0.003 per 1k chars). **Contexts >200k tokens are priced higher (~$4.00 in / ~$18.00 out per 1M).**
*   **Per Run Cost (example, ≤200k ctx):**
    *   Input: 100k tokens * $2.00/1M = **$0.20**
    *   Output: 2k tokens * $12.00/1M = **$0.024**
    *   **Total:** **~$0.22 per fix** (large repos >200k ctx can be ~$0.80+ per run with the higher tier).
*   **Monthly Cost (example):** 5 fixes/day * 30 days * ~$0.22 = **~$33.00** (assumes ≤200k ctx; heavy repos will be higher).

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

*Pricing sourced from official provider/broker docs (checked Dec 2025).*

1.  **DeepSeek V3 (The Budget Workhorse):**
    *   **DeepSeek V3 (chat/coder):** Cache miss **$0.27 / 1M input**, cache hit **$0.07 / 1M input**, output **$1.10 / 1M**. Off-peak discounts may apply.
    *   **Verdict:** Extremely cheap for high-volume loops; plan around cache-hit vs. miss.

2.  **Anthropic Claude (Reliability):**
    *   **Claude Sonnet (current gen):** **$3.00 / 1M input**, **$15.00 / 1M output** (higher for very large prompts).
    *   **Claude Haiku (lightweight):** **$1.00 / 1M input**, **$5.00 / 1M output**.
    *   **Verdict:** Sonnet for complex agents; Haiku for cheap/fast summaries.

3.  **Google Gemini (Current line):**
*   **Gemini 3 Pro:** Billed per 1k chars; ≈ **$2.00 / 1M tokens eq. input**, **$12.00 / 1M tokens eq. output** (contexts >200k tokens price at ~$4.00 / ~$18.00 respectively).
*   **Gemini 2.5 Flash:** **~$0.30 / 1M input**, **~$2.50 / 1M output** (per-token equivalent; billed per 1k chars).
*   **Verdict:** Use 2.5 Flash for clustering/summaries; 3 Pro for coding.

4.  **OpenAI GPT (Flagship + Mini):**
    *   **GPT-5.1:** **$1.25 / 1M input**, **$10.00 / 1M output**.
    *   **GPT-5.1 mini (or GPT-5 mini):** **$0.25 / 1M input**, **$2.00 / 1M output**.
    *   **Verdict:** Mini for cheap loops; 5.1 for hardest coding tasks.

### C. OpenAI GPT-OSS Models (Open Weights)

*Pricing varies significantly by provider. "gpt-oss-120b" is the flagship MoE, "gpt-oss-20b" is the efficient mid-tier.*

| Provider | Model | Input / 1M | Output / 1M | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **OpenRouter** | gpt-oss-120b | **$0.07** | **$0.28** | Low cost, broad routing. |
| **DeepInfra** | gpt-oss-120b | **$0.04** | **$0.16** | Often the cheapest for 120B. |
| **Groq** | gpt-oss-120b | $0.15 | $0.75 | Pay more for ultra-low latency. |
| **Bedrock** | gpt-oss-120b | $0.15 | $0.60 | Enterprise SLA via AWS. |
| **Cerebras** | gpt-oss-120b | $0.35 | $0.75 | High throughput OSS inference. |
| **DeepInfra** | gpt-oss-20b | **$0.04** | **$0.15** | Cheap mid-tier option. |
| **Groq** | gpt-oss-20b | $0.10 | $0.50 | Fast inference for mid-tier tasks. |

**Verdict:** Use **DeepInfra/OpenRouter** for lowest cost; **Groq/Cerebras** when latency/throughput matters; **Bedrock** for AWS-native SLA.

### D. LLM Alternatives (Ingestion & Real-Time)

1.  **Meta Llama (brokered OSS, low-latency options):**
    *   **OpenRouter (examples):** Llama 3.2 90B Vision Instruct ~**$0.37 in / $0.42 out per 1M**; Llama 3.2 3B Instruct ~**$0.021 in/out per 1M**.
    *   **Groq:** Ultra-low latency; pricing varies by model (often higher than OpenRouter).
    *   **Cerebras:** Offers OSS inference; pricing varies by model (e.g., GPT-OSS 120B ~**$0.35 in / $0.75 out per 1M** on Cerebras hardware).
    *   **Verdict:** Use OpenRouter for lowest cost; Groq/Cerebras when you need speed.

2.  **Gemini 2.5 Flash:**
    *   **Pros:** Fast responses, low cost; good for ingestion and light reasoning.
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

### F. Pricing Sources (checked Dec 2025)
* Google Vertex/AI Studio pricing pages (Gemini 3 Pro per-1k-char billing; Gemini 2.5 Flash per-1k-char billing; token equivalents assume ~4 chars/token).
* OpenAI pricing (GPT-5.1, GPT-5.1 mini / GPT-5 mini).
* Anthropic pricing (Claude Sonnet, Claude Haiku).
* DeepSeek API pricing (cache miss/hit rates; off-peak discounts).
* OpenRouter broker tables; DeepInfra/Groq/Bedrock/Cerebras where applicable for OSS (gpt-oss-120b/20b) and Meta Llama 3.2 family.

---

## 4. Total Cost Projection (With MongoDB Credits)

| Category | MVP (Low Volume) | Growth (Medium Volume) |
|----------|------------------|------------------------|
| **Frontend (Vercel)** | $40 | $40 (assuming same team size) |
| **Backend (Sevalla)** | $35 | $70 (Scale up containers) |
| **Data (MongoDB)** | **$0** (Credits) | $60 (Post-credits) |
| **Compute (AWS)** | $5 | $30 (More fixes + NAT Gateway) |
| **AI / LLM** | ~$35 (5 fixes/day, ≤200k ctx) | ~$330 (50 fixes/day, ≤200k ctx) |
| **TOTAL** | **~$115 / month** | **~$530 / month** |

*Note: Using MongoDB credits saves ~$20/mo initially compared to Upstash, but the long-term run rate for a production Atlas cluster (~$60/mo) is higher than serverless Redis (~$20/mo) for low volumes.*

---

## 5. Optimization Opportunities

1.  **Networking (AWS):** Ensure your Fargate tasks run in **Public Subnets** with "Auto-assign Public IP" enabled. This avoids the need for a NAT Gateway (~$30/mo) or VPC Endpoints.
2.  **LLM Selection:**
    *   Use **Gemini 2.5 Flash** for the initial "Analysis" phase of the coding agent when possible. Switch to **Gemini 3 Pro** (or another flagship) for final code generation.
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