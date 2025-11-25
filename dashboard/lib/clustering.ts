import { GoogleGenAI } from '@google/genai';
import { randomUUID } from 'crypto';
import type { FeedbackItem } from '@/types';

// Initialize Gemini
const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_GENERATIVE_AI_API_KEY || '';

if (!apiKey) {
  console.error('[Clustering] GEMINI_API_KEY is missing!');
} else {
  console.log(`[Clustering] API Key found (starts with: ${apiKey.substring(0, 4)}...)`);
}

const ai = new GoogleGenAI({ apiKey });

// ============================================================================
// PURE FUNCTIONS - Exported for testing and reuse
// ============================================================================

/**
 * Calculate cosine similarity between two embeddings
 * Returns a value between -1 and 1, where 1 means identical direction
 */
export function cosineSimilarity(embedding1: number[], embedding2: number[]): number {
  if (embedding1.length !== embedding2.length || embedding1.length === 0) {
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
 * Skips embeddings with mismatched dimensions
 */
export function calculateCentroid(embeddings: number[][]): number[] {
  if (embeddings.length === 0) return [];
  if (embeddings.length === 1) return embeddings[0];

  const dimensions = embeddings[0].length;
  const centroid = new Array(dimensions).fill(0);
  let validCount = 0;

  for (const embedding of embeddings) {
    // Skip embeddings with mismatched dimensions
    if (embedding.length !== dimensions) continue;

    validCount++;
    for (let i = 0; i < dimensions; i++) {
      centroid[i] += embedding[i];
    }
  }

  // Average - use validCount to handle skipped embeddings
  if (validCount === 0) return [];
  for (let i = 0; i < dimensions; i++) {
    centroid[i] /= validCount;
  }

  return centroid;
}

/**
 * Find the best matching cluster for an embedding
 * Returns null if no cluster meets the similarity threshold
 */
export interface ClusterMatch {
  clusterId: string;
  clusterIndex: number;
  similarity: number;
}

export function findBestCluster(
  embedding: number[],
  clusters: ClusterData[],
  similarityThreshold: number
): ClusterMatch | null {
  if (clusters.length === 0) return null;

  let maxSimilarity = 0;
  let bestClusterId: string | null = null;
  let bestClusterIndex = -1;

  for (let i = 0; i < clusters.length; i++) {
    const cluster = clusters[i];
    if (cluster.centroid.length === 0) continue;

    const similarity = cosineSimilarity(embedding, cluster.centroid);
    if (similarity > maxSimilarity) {
      maxSimilarity = similarity;
      bestClusterId = cluster.id;
      bestClusterIndex = i;
    }
  }

  if (maxSimilarity >= similarityThreshold && bestClusterId) {
    return {
      clusterId: bestClusterId,
      clusterIndex: bestClusterIndex,
      similarity: maxSimilarity,
    };
  }

  return null;
}

// ============================================================================
// TYPES
// ============================================================================

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
  issueTitle: string;
  issueDescription: string;
  repoUrl?: string;
}

export interface RedisOperation {
  type: 'sadd' | 'srem' | 'hset' | 'del';
  key: string;
  values?: string[];
  fields?: Record<string, string>;
}

// ============================================================================
// CLUSTERING BATCH - Optimized batch processing class
// ============================================================================

/**
 * ClusteringBatch manages efficient batch processing of clustering operations.
 *
 * Key optimizations:
 * 1. Tracks changed clusters to avoid regenerating summaries for unchanged ones
 * 2. Caches feedback items to avoid re-fetching
 * 3. Batches Redis operations for efficient pipeline execution
 * 4. Provides incremental centroid updates
 */
export class ClusteringBatch {
  private changedClusterIds: Set<string> = new Set();
  private newClusterIds: Set<string> = new Set();
  private feedbackCache: Map<string, FeedbackItem> = new Map();
  private redisOperations: Map<string, RedisOperation> = new Map();
  private clusters: ClusterData[] = [];
  private clusterMap: Map<string, number> = new Map(); // clusterId -> index

  /**
   * Initialize with existing clusters
   */
  initializeClusters(clusters: ClusterData[]): void {
    this.clusters = clusters.map((c) => ({
      ...c,
      feedbackIds: [...c.feedbackIds],
      centroid: [...c.centroid],
    }));
    this.clusterMap.clear();
    for (let i = 0; i < this.clusters.length; i++) {
      this.clusterMap.set(this.clusters[i].id, i);
    }
  }

  // --------------------------------------------------------------------------
  // Cluster Change Tracking
  // --------------------------------------------------------------------------

  markClusterChanged(clusterId: string): void {
    this.changedClusterIds.add(clusterId);
  }

  markClusterNew(clusterId: string): void {
    this.newClusterIds.add(clusterId);
    this.changedClusterIds.add(clusterId);
  }

  isNewCluster(clusterId: string): boolean {
    return this.newClusterIds.has(clusterId);
  }

  getChangedClusterIds(): string[] {
    return Array.from(this.changedClusterIds);
  }

  getNewClusterIds(): string[] {
    return Array.from(this.newClusterIds);
  }

  /**
   * Get only the cluster IDs that need summary regeneration
   * This is the key optimization - skip unchanged clusters!
   */
  getClustersNeedingSummaryRegeneration(allClusterIds: string[]): string[] {
    return allClusterIds.filter((id) => this.changedClusterIds.has(id));
  }

  // --------------------------------------------------------------------------
  // Incremental Centroid Updates
  // --------------------------------------------------------------------------

  /**
   * Update centroid incrementally without re-computing from all embeddings
   * Formula: newCentroid = (oldCentroid * oldCount + newEmbedding) / (oldCount + 1)
   */
  updateCentroidIncremental(
    oldCentroid: number[],
    newEmbedding: number[],
    oldCount: number
  ): number[] {
    // First item in cluster - just use the embedding
    if (oldCount === 0 || oldCentroid.length === 0) {
      return [...newEmbedding];
    }

    const newCount = oldCount + 1;
    return oldCentroid.map((val, i) => (val * oldCount + newEmbedding[i]) / newCount);
  }

  // --------------------------------------------------------------------------
  // Feedback Caching
  // --------------------------------------------------------------------------

  cacheFeedbackItem(item: FeedbackItem): void {
    this.feedbackCache.set(item.id, item);
  }

  cacheFeedbackItems(items: FeedbackItem[]): void {
    for (const item of items) {
      this.feedbackCache.set(item.id, item);
    }
  }

  getCachedFeedbackItem(id: string): FeedbackItem | undefined {
    return this.feedbackCache.get(id);
  }

  getCachedFeedbackItems(ids: string[]): { found: FeedbackItem[]; missing: string[] } {
    const found: FeedbackItem[] = [];
    const missing: string[] = [];

    for (const id of ids) {
      const item = this.feedbackCache.get(id);
      if (item) {
        found.push(item);
      } else {
        missing.push(id);
      }
    }

    return { found, missing };
  }

  // --------------------------------------------------------------------------
  // Redis Operation Batching
  // --------------------------------------------------------------------------

  /**
   * Queue a Redis operation for batch execution
   * Automatically merges compatible operations on the same key
   */
  queueRedisOperation(operation: RedisOperation): void {
    const key = `${operation.type}:${operation.key}`;

    if (operation.type === 'sadd' || operation.type === 'srem') {
      const existing = this.redisOperations.get(key);
      if (existing && existing.values && operation.values) {
        // Merge values
        existing.values = [...new Set([...existing.values, ...operation.values])];
      } else {
        this.redisOperations.set(key, { ...operation, values: [...(operation.values || [])] });
      }
    } else if (operation.type === 'hset') {
      const existing = this.redisOperations.get(key);
      if (existing && existing.fields && operation.fields) {
        // Merge fields
        existing.fields = { ...existing.fields, ...operation.fields };
      } else {
        this.redisOperations.set(key, { ...operation, fields: { ...operation.fields } });
      }
    } else {
      // For other types (del), just overwrite
      this.redisOperations.set(key, operation);
    }
  }

  /**
   * Get all queued operations and clear the queue
   */
  getQueuedOperations(): RedisOperation[] {
    const operations = Array.from(this.redisOperations.values());
    this.redisOperations.clear();
    return operations;
  }

  // --------------------------------------------------------------------------
  // Batch Cluster Assignment
  // --------------------------------------------------------------------------

  /**
   * Assign multiple embeddings to clusters efficiently
   * Updates internal cluster state as assignments are made
   */
  assignToClusters(
    embeddings: { id: string; embedding: number[] }[],
    initialClusters: ClusterData[],
    similarityThreshold: number
  ): ClusteringResult[] {
    // Initialize if not already done
    if (this.clusters.length === 0 && initialClusters.length > 0) {
      this.initializeClusters(initialClusters);
    }

    const results: ClusteringResult[] = [];

    for (const { id: feedbackId, embedding } of embeddings) {
      const match = findBestCluster(embedding, this.clusters, similarityThreshold);

      if (match) {
        // Add to existing cluster
        const cluster = this.clusters[match.clusterIndex];
        const oldCount = cluster.feedbackIds.length;
        cluster.feedbackIds.push(feedbackId);

        // Update centroid incrementally
        cluster.centroid = this.updateCentroidIncremental(cluster.centroid, embedding, oldCount);

        this.markClusterChanged(cluster.id);

        results.push({
          clusterId: cluster.id,
          feedbackId,
          isNewCluster: false,
          similarity: match.similarity,
        });
      } else {
        // Create new cluster
        const clusterId = randomUUID();
        const newCluster: ClusterData = {
          id: clusterId,
          feedbackIds: [feedbackId],
          centroid: embedding,
        };

        this.clusters.push(newCluster);
        this.clusterMap.set(clusterId, this.clusters.length - 1);
        this.markClusterNew(clusterId);

        results.push({
          clusterId,
          feedbackId,
          isNewCluster: true,
        });
      }
    }

    return results;
  }

  /**
   * Get the current state of all clusters
   */
  getUpdatedClusters(): ClusterData[] {
    return this.clusters;
  }

  /**
   * Get a specific cluster by ID
   */
  getCluster(clusterId: string): ClusterData | undefined {
    const index = this.clusterMap.get(clusterId);
    if (index === undefined) return undefined;
    return this.clusters[index];
  }
}

// ============================================================================
// LEGACY API - Maintained for backward compatibility
// ============================================================================

/**
 * Generate embedding for a piece of text
 */
async function generateEmbedding(text: string): Promise<number[]> {
  try {
    const response = await ai.models.embedContent({
      model: 'gemini-embedding-001',
      contents: [{ parts: [{ text }] }],
    });

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
 * Prepare text for embedding (combine title and body)
 */
function prepareTextForEmbedding(feedback: FeedbackItem): string {
  const title = feedback.title || '';
  const body = feedback.body || '';
  return `Title: ${title}\nBody: ${body}`.trim();
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
 * @deprecated Use ClusteringBatch.assignToClusters for better performance
 */
export async function clusterFeedback(
  feedback: FeedbackItem,
  existingClusters: ClusterData[],
  similarityThreshold: number = 0.75
): Promise<ClusteringResult> {
  const text = prepareTextForEmbedding(feedback);
  const embedding = await generateEmbedding(text);

  if (existingClusters.length === 0) {
    const clusterId = randomUUID();
    return {
      clusterId,
      feedbackId: feedback.id,
      isNewCluster: true,
    };
  }

  const match = findBestCluster(embedding, existingClusters, similarityThreshold);

  if (match) {
    return {
      clusterId: match.clusterId,
      feedbackId: feedback.id,
      isNewCluster: false,
      similarity: match.similarity,
    };
  }

  const clusterId = randomUUID();
  return {
    clusterId,
    feedbackId: feedback.id,
    isNewCluster: true,
  };
}

/**
 * Batch cluster multiple feedback items
 * @deprecated Use ClusteringBatch for better performance with change tracking
 */
export async function clusterFeedbackBatch(
  feedbackItems: FeedbackItem[],
  existingClusters: ClusterData[],
  similarityThreshold: number = 0.75
): Promise<{
  results: ClusteringResult[];
  updatedClusters: ClusterData[];
}> {
  const batch = new ClusteringBatch();
  batch.initializeClusters(existingClusters);
  batch.cacheFeedbackItems(feedbackItems);

  // Generate embeddings for all feedback (parallelized)
  const embeddingResults = await Promise.all(
    feedbackItems.map(async (item) => {
      const text = prepareTextForEmbedding(item);
      try {
        return {
          id: item.id,
          embedding: await generateEmbedding(text),
        };
      } catch (e) {
        console.error(`Failed to generate embedding for ${item.id}`, e);
        return null;
      }
    })
  );

  const validEmbeddings = embeddingResults.filter(
    (e): e is { id: string; embedding: number[] } => e !== null
  );

  // Use the optimized batch assignment
  const results = batch.assignToClusters(validEmbeddings, existingClusters, similarityThreshold);

  return {
    results,
    updatedClusters: batch.getUpdatedClusters(),
  };
}

/**
 * Optimized batch clustering that returns the batch for further operations
 * This allows the caller to check which clusters changed and need summary regeneration
 */
export async function clusterFeedbackBatchOptimized(
  feedbackItems: FeedbackItem[],
  existingClusters: ClusterData[],
  similarityThreshold: number = 0.75
): Promise<{
  results: ClusteringResult[];
  batch: ClusteringBatch;
}> {
  const batch = new ClusteringBatch();
  batch.initializeClusters(existingClusters);
  batch.cacheFeedbackItems(feedbackItems);

  // Generate embeddings for all feedback (parallelized)
  const embeddingResults = await Promise.all(
    feedbackItems.map(async (item) => {
      const text = prepareTextForEmbedding(item);
      try {
        return {
          id: item.id,
          embedding: await generateEmbedding(text),
        };
      } catch (e) {
        console.error(`Failed to generate embedding for ${item.id}`, e);
        return null;
      }
    })
  );

  const validEmbeddings = embeddingResults.filter(
    (e): e is { id: string; embedding: number[] } => e !== null
  );

  // Use the optimized batch assignment
  const results = batch.assignToClusters(validEmbeddings, existingClusters, similarityThreshold);

  return {
    results,
    batch,
  };
}

/**
 * Generate a summary for a cluster using the feedback items
 */
export async function generateClusterSummary(
  feedbackItems: FeedbackItem[]
): Promise<ClusterSummaryResult> {
  if (feedbackItems.length === 0) {
    return {
      title: 'Empty cluster',
      summary: 'No feedback items',
      issueTitle: 'Empty cluster',
      issueDescription: 'No feedback items were provided to summarize.',
    };
  }

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
