import { GoogleGenAI } from '@google/genai';
import { randomUUID } from 'crypto';
import type { FeedbackItem } from '@/types';

// Initialize Gemini
// The client gets the API key from the environment variable `GEMINI_API_KEY` automatically if not provided,
// but we can also pass it explicitly if we want to support both or verify it.
const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_GENERATIVE_AI_API_KEY || '';

if (!apiKey) {
  console.error('[Clustering] GEMINI_API_KEY is missing!');
} else {
  console.log(`[Clustering] API Key found (starts with: ${apiKey.substring(0, 4)}...)`);
}

const ai = new GoogleGenAI({ apiKey });

/**
 * Generate embedding for a piece of text
 */
async function generateEmbedding(text: string): Promise<number[]> {
  try {
    const response = await ai.models.embedContent({
      model: 'gemini-embedding-001',
      // Correct usage for @google/genai (v0.1.0+):
      // It expects `contents` (plural) as an array of `Part` objects.
      contents: [{ parts: [{ text }] }],
    });

    // Check for embedding in response.embedding or response.embeddings
    // The error suggested 'embeddings', but let's be safe and check what's actually there if possible,
    // or just follow the error suggestion.
    // Actually, checking the error: "Property 'embedding' does not exist... Did you mean 'embeddings'?"
    // So it is likely 'embeddings'.
    // However, for a single content, it might still be 'embedding' in some versions, but let's try 'embeddings'.
    // Wait, if I pass a single content, I expect a single embedding.
    // Let's try to inspect the type or just go with 'embeddings' and take the first one.

    // NOTE: The SDK might return `embeddings` as an array if multiple contents are passed.
    // Since I passed `content` (singular) in my previous attempt and it failed with "Did you mean 'contents'?",
    // I should probably use `contents` and expect `embeddings`.

    /* 
      Correct usage for @google/genai (v0.1.0+):
      const result = await client.models.embedContent({
        model: '...',
        contents: [...]
      });
      result.embeddings[0].values
    */

    // Let's correct the call structure as well.

    // The new SDK response structure might be slightly different
    // Based on docs/examples, it usually returns embedding directly or in a structure
    // Let's assume standard response structure for now, but might need adjustment if SDK differs significantly
    // from previous one.
    // Actually, for @google/genai, it's likely: response.embeddings[0].values

    if (!response || !response.embeddings || response.embeddings.length === 0 || !response.embeddings[0].values) {
      throw new Error('Invalid embedding response');
    }

    return response.embeddings[0].values;
  } catch (error) {
    console.error('[Clustering] Error generating embedding:', error);
    throw error;
  }
}

/**
 * Calculate cosine similarity between two embeddings
 */
function cosineSimilarity(embedding1: number[], embedding2: number[]): number {
  if (embedding1.length !== embedding2.length) {
    // Handle mismatch if necessary, or just return 0
    return 0;
  }

  let dotProduct = 0;
  let magnitude1 = 0;
  let magnitude2 = 0;

  for (let i = 0; i < embedding1.length; i++) {
    dotProduct += embedding1[i] * embedding2[i];
    magnitude1 += embedding1[i] * embedding1[i];
    magnitude2 += embedding2[i] * embedding2[i];
  }

  magnitude1 = Math.sqrt(magnitude1);
  magnitude2 = Math.sqrt(magnitude2);

  if (magnitude1 === 0 || magnitude2 === 0) return 0;

  return dotProduct / (magnitude1 * magnitude2);
}

/**
 * Calculate centroid (mean) of multiple embeddings
 */
function calculateCentroid(embeddings: number[][]): number[] {
  if (embeddings.length === 0) return [];
  if (embeddings.length === 1) return embeddings[0];

  const dimensions = embeddings[0].length;
  const centroid = new Array(dimensions).fill(0);

  for (const embedding of embeddings) {
    // Handle potential dimension mismatch if models changed
    if (embedding.length !== dimensions) continue;

    for (let i = 0; i < dimensions; i++) {
      centroid[i] += embedding[i];
    }
  }

  // Average
  for (let i = 0; i < dimensions; i++) {
    centroid[i] /= embeddings.length;
  }

  return centroid;
}

/**
 * Prepare text for embedding (combine title and body)
 */
function prepareTextForEmbedding(feedback: FeedbackItem): string {
  const title = feedback.title || '';
  const body = feedback.body || '';
  return `Title: ${title}\nBody: ${body}`.trim();
}

export interface ClusteringResult {
  clusterId: string;
  feedbackId: string;
  isNewCluster: boolean;
  similarity?: number;
}

export interface ClusterData {
  id: string;
  feedbackIds: string[];
  centroid: number[];
}

export interface ClusterSummaryResult {
  title: string;
  summary: string;
  issueTitle?: string;
  issueDescription?: string;
  repoUrl?: string;
}

function normalizeRepoUrl(value?: string | null): string | null {
  if (!value || typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed) return null;

  const repoMatch = trimmed.match(/github\.com\/([\w.-]+)\/([\w.-]+)/i);
  if (repoMatch) {
    const owner = repoMatch[1];
    const repo = repoMatch[2].replace(/\.git$/i, '');
    return `https://github.com/${owner}/${repo}`;
  }

  if (/^[\w.-]+\/[\w.-]+(\.git)?$/.test(trimmed)) {
    return `https://github.com/${trimmed.replace(/\.git$/i, '')}`;
  }

  return null;
}

function extractRepoHints(feedbackItems: FeedbackItem[]): string[] {
  const hints = new Set<string>();
  for (const item of feedbackItems) {
    const direct = normalizeRepoUrl(item.github_repo_url || (item.metadata?.github_repo_url as string));
    if (direct) hints.add(direct);

    const metadataRepo = typeof item.metadata?.repo_url === 'string' ? normalizeRepoUrl(item.metadata.repo_url) : null;
    if (metadataRepo) hints.add(metadataRepo);

    const bodyMatches = item.body.matchAll(/github\.com\/([\w.-]+)\/([\w.-]+)/gi);
    for (const match of bodyMatches) {
      const normalized = normalizeRepoUrl(`https://github.com/${match[1]}/${match[2]}`);
      if (normalized) hints.add(normalized);
    }
  }
  return Array.from(hints);
}

function buildFallbackSummary(feedbackItems: FeedbackItem[], repoHints: string[]): ClusterSummaryResult {
  const titles = feedbackItems.map((item) => item.title || 'Untitled');
  const summaryText = feedbackItems
    .map((item) => `• ${item.title}: ${item.body.substring(0, 140)}`)
    .slice(0, 4)
    .join('\n');

  const fallbackTitle = titles[0]?.substring(0, 50) || 'Cluster Summary';
  const fallbackSummary = `${feedbackItems.length} reports. First: ${feedbackItems[0]?.body.substring(0, 140) || ''}`;

  return {
    title: fallbackTitle,
    summary: fallbackSummary,
    issueTitle: fallbackTitle,
    issueDescription: summaryText || fallbackSummary,
    repoUrl: repoHints[0],
  };
}

/**
 * Cluster a single feedback item against existing clusters
 * Returns which cluster it should belong to (or if it should create a new one)
 */
export async function clusterFeedback(
  feedback: FeedbackItem,
  existingClusters: ClusterData[],
  similarityThreshold: number = 0.75 // Slightly lower threshold for Gemini embeddings usually works better
): Promise<ClusteringResult> {
  const text = prepareTextForEmbedding(feedback);
  const embedding = await generateEmbedding(text);

  if (existingClusters.length === 0) {
    // First cluster
    const clusterId = randomUUID();
    return {
      clusterId,
      feedbackId: feedback.id,
      isNewCluster: true,
    };
  }

  // Find most similar cluster
  let maxSimilarity = 0;
  let bestClusterId: string | null = null;

  for (const cluster of existingClusters) {
    if (cluster.centroid.length === 0) continue;

    const similarity = cosineSimilarity(embedding, cluster.centroid);
    if (similarity > maxSimilarity) {
      maxSimilarity = similarity;
      bestClusterId = cluster.id;
    }
  }

  // Check if similarity meets threshold
  if (maxSimilarity >= similarityThreshold && bestClusterId) {
    return {
      clusterId: bestClusterId,
      feedbackId: feedback.id,
      isNewCluster: false,
      similarity: maxSimilarity,
    };
  }

  // Create new cluster
  const clusterId = randomUUID();
  return {
    clusterId,
    feedbackId: feedback.id,
    isNewCluster: true,
  };
}

/**
 * Batch cluster multiple feedback items - OPTIMIZED VERSION
 *
 * Key optimizations:
 * 1. Uses embedding cache to avoid regenerating embeddings
 * 2. Incremental centroid updates (weighted average, no re-filtering)
 * 3. Batch embedding generation for uncached items only
 * 4. Stores new embeddings in cache for future use
 */
export async function clusterFeedbackBatch(
  feedbackItems: FeedbackItem[],
  existingClusters: ClusterData[],
  similarityThreshold: number = 0.75
): Promise<{
  results: ClusteringResult[];
  updatedClusters: ClusterData[];
}> {
  const results: ClusteringResult[] = [];
  const clusters = [...existingClusters];

  console.log(`[Clustering] Processing ${feedbackItems.length} items against ${clusters.length} clusters`);

  // OPTIMIZATION 1: Batch fetch cached embeddings
  const { batchGetEmbeddings, batchSetEmbeddings } = await import('./embedding-cache');
  const cachedEmbeddings = await batchGetEmbeddings(feedbackItems.map((item) => item.id));

  // OPTIMIZATION 2: Generate embeddings only for uncached items
  const embeddingsToGenerate: Array<{ index: number; item: FeedbackItem }> = [];
  const finalEmbeddings: Array<{ feedbackId: string; embedding: number[] }> = [];

  for (let i = 0; i < feedbackItems.length; i++) {
    const item = feedbackItems[i];
    const cachedEmbedding = cachedEmbeddings[i];

    if (cachedEmbedding) {
      // Use cached embedding
      finalEmbeddings.push({
        feedbackId: item.id,
        embedding: cachedEmbedding,
      });
    } else {
      // Need to generate
      embeddingsToGenerate.push({ index: i, item });
    }
  }

  console.log(
    `[Clustering] Cache hit: ${finalEmbeddings.length}/${feedbackItems.length}, generating ${embeddingsToGenerate.length} new embeddings`
  );

  // Generate embeddings for uncached items
  if (embeddingsToGenerate.length > 0) {
    const newEmbeddings = await Promise.all(
      embeddingsToGenerate.map(async ({ item }) => {
        const text = prepareTextForEmbedding(item);
        try {
          const embedding = await generateEmbedding(text);
          return {
            feedbackId: item.id,
            embedding,
          };
        } catch (e) {
          console.error(`[Clustering] Failed to generate embedding for ${item.id}`, e);
          return null;
        }
      })
    );

    // Filter out failures and add to final embeddings
    const validNewEmbeddings = newEmbeddings.filter(
      (e): e is { feedbackId: string; embedding: number[] } => e !== null
    );

    finalEmbeddings.push(...validNewEmbeddings);

    // OPTIMIZATION 3: Cache newly generated embeddings
    if (validNewEmbeddings.length > 0) {
      await batchSetEmbeddings(validNewEmbeddings);
      console.log(`[Clustering] Cached ${validNewEmbeddings.length} new embeddings`);
    }
  }

  // Import clustering utilities
  const { cosineSimilarity: utilCosineSimilarity, calculateWeightedCentroid } = await import(
    './clustering-utils'
  );

  // OPTIMIZATION 4: Use incremental centroid updates
  for (const { feedbackId, embedding } of finalEmbeddings) {
    let maxSimilarity = 0;
    let bestClusterIndex: number | null = null;

    // Find best matching cluster
    for (let i = 0; i < clusters.length; i++) {
      if (clusters[i].centroid.length === 0) continue;

      const similarity = utilCosineSimilarity(embedding, clusters[i].centroid);
      if (similarity > maxSimilarity) {
        maxSimilarity = similarity;
        bestClusterIndex = i;
      }
    }

    // Assign to cluster or create new one
    if (maxSimilarity >= similarityThreshold && bestClusterIndex !== null) {
      const cluster = clusters[bestClusterIndex];
      console.log(
        `[Clustering] Adding feedback ${feedbackId} to cluster ${cluster.id} (similarity: ${maxSimilarity.toFixed(3)})`
      );

      const oldCount = cluster.feedbackIds.length;
      cluster.feedbackIds.push(feedbackId);

      // OPTIMIZATION 5: Incremental centroid update (no re-filtering!)
      cluster.centroid = calculateWeightedCentroid(cluster.centroid, oldCount, embedding);

      results.push({
        clusterId: cluster.id,
        feedbackId,
        isNewCluster: false,
        similarity: maxSimilarity,
      });
    } else {
      // Create new cluster
      console.log(
        `[Clustering] Creating new cluster for ${feedbackId} (max similarity: ${maxSimilarity.toFixed(3)})`
      );
      const clusterId = randomUUID();
      clusters.push({
        id: clusterId,
        feedbackIds: [feedbackId],
        centroid: embedding,
      });

      results.push({
        clusterId,
        feedbackId,
        isNewCluster: true,
      });
    }
  }

  console.log(`[Clustering] Created ${results.filter((r) => r.isNewCluster).length} new clusters`);

  return {
    results,
    updatedClusters: clusters,
  };
}

/**
 * Determine if a cluster summary should be regenerated
 * This saves expensive LLM calls by only regenerating when necessary
 *
 * @param oldCount Previous number of items in cluster
 * @param newCount Current number of items in cluster
 * @returns True if summary should be regenerated
 */
function shouldRegenerateSummary(oldCount: number, newCount: number): boolean {
  // Always generate for new clusters
  if (oldCount === 0) {
    return true;
  }

  // Regenerate if cluster grew by more than 50%
  const growthRate = (newCount - oldCount) / oldCount;
  if (growthRate > 0.5) {
    return true;
  }

  // Regenerate every 10 items (for very large clusters)
  if (newCount % 10 === 0 && newCount !== oldCount) {
    return true;
  }

  return false;
}

/**
 * Generate a summary for a cluster using the feedback items - OPTIMIZED VERSION
 *
 * Key optimization: Skip regeneration if cluster hasn't changed significantly
 */
export async function generateClusterSummary(
  feedbackItems: FeedbackItem[],
  options?: {
    existingSummary?: ClusterSummaryResult;
    oldCount?: number;
    newCount?: number;
    forceRegenerate?: boolean;
  }
): Promise<ClusterSummaryResult> {
  if (feedbackItems.length === 0) {
    return {
      title: 'Empty cluster',
      summary: 'No feedback items',
      issueTitle: 'Empty cluster',
      issueDescription: 'No feedback items were provided to summarize.',
    };
  }

  // OPTIMIZATION: Check if we should skip regeneration
  const oldCount = options?.oldCount ?? 0;
  const newCount = options?.newCount ?? feedbackItems.length;
  const forceRegenerate = options?.forceRegenerate ?? false;

  if (!forceRegenerate && options?.existingSummary && !shouldRegenerateSummary(oldCount, newCount)) {
    console.log(
      `[Clustering] Skipping summary regeneration (${oldCount} -> ${newCount} items, growth rate: ${((newCount - oldCount) / oldCount * 100).toFixed(1)}%)`
    );
    return options.existingSummary;
  }

  console.log(`[Clustering] Regenerating summary for ${newCount} items`);

  const repoHints = extractRepoHints(feedbackItems);

  const feedbackTexts = feedbackItems
    .map((item) => {
      const title = item.title || 'No Title';
      const body = item.body || '';
      return `- ${title}: ${body.substring(0, 400)}`;
    })
    .join('\n');

  const repoSection = repoHints.length
    ? `\nRepository hints (if relevant): ${repoHints.join(', ')}`
    : '';

  const prompt = `
You are helping triage product feedback into engineering-ready work items.
Given these feedback excerpts, produce a JSON object with the following shape:
{
  "cluster_title": "Friendly name for the cluster (<=50 chars)",
  "cluster_description": "High-level summary focused on user impact (<=300 chars)",
  "issue_title": "GitHub-appropriate issue title (<=72 chars)",
  "issue_description": "Markdown body that explains impact, evidence, and acceptance hints (<=1200 chars)",
  "repo_url": "https://github.com/owner/repo value if you can infer it, otherwise null"
}

Feedback Items:
${feedbackTexts}
${repoSection}

Return ONLY valid JSON.
`;

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-3-pro-preview',
      contents: [
        {
          role: 'user',
          parts: [{ text: prompt }],
        },
      ],
      config: {
        responseMimeType: 'application/json',
      },
    });

    const text = typeof response.text === 'string' ? response.text : '';

    if (!text) {
      throw new Error('Empty response from Gemini');
    }

    const jsonStr = text.replace(/```json/gi, '').replace(/```/g, '').trim();
    const data = JSON.parse(jsonStr);

    return {
      title: data.cluster_title || data.title || 'Cluster Summary',
      summary: data.cluster_description || data.summary || 'No summary available',
      issueTitle: data.issue_title || data.cluster_title || 'Cluster Issue',
      issueDescription: data.issue_description || data.cluster_description || data.summary || 'No summary available',
      repoUrl: normalizeRepoUrl(data.repo_url) || repoHints[0],
    };
  } catch (error) {
    console.error('[Clustering] Error generating summary with Gemini:', error);
    return buildFallbackSummary(feedbackItems, repoHints);
  }
}
