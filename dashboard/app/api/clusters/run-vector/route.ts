import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import {
  VectorStore,
  generateFeedbackEmbedding,
  clusterWithVectorDB,
  type ClusteringResult,
} from '@/lib/vector';
import { generateClusterSummary } from '@/lib/clustering';
import type { FeedbackItem } from '@/types';
import { requireProjectId } from '@/lib/project';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

const clusterKey = (projectId: string, clusterId: string) => `cluster:${projectId}:${clusterId}`;
const clusterItemsKey = (projectId: string, clusterId: string) =>
  `cluster:${projectId}:${clusterId}:items`;
const clusterAllKey = (projectId: string) => `clusters:${projectId}:all`;
const feedbackKey = (projectId: string, feedbackId: string) => `feedback:${projectId}:${feedbackId}`;
const feedbackUnclusteredKey = (projectId: string) => `feedback:unclustered:${projectId}`;

async function getUnclusteredFeedbackIds(projectId: string): Promise<string[]> {
  const ids = await redis.smembers(feedbackUnclusteredKey(projectId));
  return (ids as string[]) || [];
}

async function getFeedbackItemById(projectId: string, id: string): Promise<FeedbackItem | null> {
  const data = await redis.hgetall(feedbackKey(projectId, id));
  if (!data || Object.keys(data).length === 0) return null;

  let metadata: any = data.metadata;
  if (typeof metadata === 'string') {
    try {
      metadata = JSON.parse(metadata);
    } catch {
      metadata = {};
    }
  }

  const github_issue_number =
    typeof data.github_issue_number === 'string' ? parseInt(data.github_issue_number, 10) : undefined;

  return {
    id,
    source: (data.source as FeedbackItem['source']) || 'manual',
    external_id: data.external_id as string | null | undefined,
    title: (data.title as string) || '',
    body: (data.body as string) || '',
    repo: data.repo as string | undefined,
    github_repo_url: data.github_repo_url as string | undefined,
    github_issue_number: isNaN(github_issue_number || NaN) ? undefined : github_issue_number,
    github_issue_url: data.github_issue_url as string | undefined,
    status: data.status as FeedbackItem['status'],
    metadata: metadata || {},
    created_at: (data.created_at as string) || new Date().toISOString(),
  };
}

// Similarity threshold - see /docs/DESIGN_DECISIONS.md for rationale
const SIMILARITY_THRESHOLD = 0.72;

// Batch size for parallel operations to avoid overwhelming connections
const BATCH_SIZE = 50;

/**
 * Process items in batches to avoid connection overload
 */
async function batchProcess<T, R>(
  items: T[],
  processor: (item: T) => Promise<R>,
  batchSize: number = BATCH_SIZE
): Promise<R[]> {
  const results: R[] = [];
  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);
    const batchResults = await Promise.all(batch.map(processor));
    results.push(...batchResults);
    // Log progress for large batches
    if (items.length > 100) {
      console.log(`[Vector Clustering] Processed ${Math.min(i + batchSize, items.length)}/${items.length} items`);
    }
  }
  return results;
}

interface ClusterSummaryData {
  title: string;
  summary: string;
  issueTitle?: string;
  issueDescription?: string;
  repoUrl?: string;
}

/**
 * Perform vector-based clustering of a project's unclustered feedback items and persist cluster state.
 *
 * Fetches unclustered feedback IDs, generates embeddings, assigns feedback to existing or new clusters
 * using vector similarity, stores embeddings in the vector store, generates summaries for changed clusters,
 * and updates Redis (cluster hashes, cluster membership sets, and feedback clustered flags). Removes processed
 * items from the unclustered set.
 *
 * @param request - Incoming HTTP request; must include project context (a `project_id` is required)
 * @returns A JSON payload describing the operation outcome:
 * - `success`: `true` on success, `false` on error
 * - `message`: human-readable status message
 * - `clustered`: number of feedback items processed and clustered
 * - `newClusters`: number of newly created clusters
 * - `updatedClusters`: number of existing clusters updated
 * - `embeddingFailures`: number of items that failed during embedding or processing
 * - `missingFeedback`: number of feedback IDs that were not found and removed from unclustered set
 * - `durationMs`: elapsed processing time in milliseconds
 * - `threshold`: similarity threshold used for clustering
 * On error, the response will include `error` and `details` fields with failure information.
 */
export async function POST(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    console.log('[Vector Clustering] Starting vector-based clustering...');
    const startTime = Date.now();

    const vectorStore = new VectorStore();

    // Get unclustered feedback IDs
    const unclusteredIds = await getUnclusteredFeedbackIds(projectId);
    console.log(`[Vector Clustering] Found ${unclusteredIds.length} unclustered items`);

    if (unclusteredIds.length === 0) {
      return NextResponse.json({
        success: true,
        message: 'No unclustered feedback to process',
        clustered: 0,
        newClusters: 0,
      });
    }

    // Fetch feedback items in batches to avoid connection overload
    console.log(`[Vector Clustering] Fetching ${unclusteredIds.length} feedback items in batches of ${BATCH_SIZE}...`);
    const feedbackItems = await batchProcess(unclusteredIds, (id) => getFeedbackItemById(projectId, id));
    const validFeedback: FeedbackItem[] = [];
    const missingFeedbackIds: Set<string> = new Set();

    for (let i = 0; i < unclusteredIds.length; i++) {
      const item = feedbackItems[i];
      if (item !== null) {
        validFeedback.push(item);
      } else {
        missingFeedbackIds.add(unclusteredIds[i]);
      }
    }

    if (missingFeedbackIds.size > 0) {
      console.log(
        `[Vector Clustering] ${missingFeedbackIds.size} feedback items not found (will be removed from unclustered)`
      );
    }

    // Process each feedback item
    const results: ClusteringResult[] = [];
    const newClusterIds = new Set<string>();
    const changedClusterIds = new Set<string>();
    const clusterFeedbackMap = new Map<string, string[]>(); // clusterId -> feedbackIds

    let embeddingFailures = 0;

    for (const feedback of validFeedback) {
      try {
        // Generate embedding
        const embedding = await generateFeedbackEmbedding(feedback);

        // Cluster using vector similarity
        const result = await clusterWithVectorDB(feedback, embedding, SIMILARITY_THRESHOLD);
        results.push(result);

        // Track cluster changes
        changedClusterIds.add(result.clusterId);
        if (result.isNewCluster) {
          newClusterIds.add(result.clusterId);
        }

        // Track feedback per cluster
        const existing = clusterFeedbackMap.get(result.clusterId) || [];
        existing.push(feedback.id);
        clusterFeedbackMap.set(result.clusterId, existing);

        // Also add any grouped unclustered items
        if (result.groupedFeedbackIds) {
          for (const groupedId of result.groupedFeedbackIds) {
            existing.push(groupedId);
            changedClusterIds.add(result.clusterId);
          }
          clusterFeedbackMap.set(result.clusterId, existing);
        }

        // Store in vector DB
        await vectorStore.upsertFeedback(feedback.id, embedding, {
          title: feedback.title || '',
          source: feedback.source,
          clusterId: result.clusterId,
          createdAt: feedback.created_at,
        });

        // Update grouped items' cluster assignments in vector DB
        if (result.groupedFeedbackIds && result.groupedFeedbackIds.length > 0) {
          await vectorStore.updateClusterAssignmentBatch(
            result.groupedFeedbackIds.map((id) => ({
              feedbackId: id,
              clusterId: result.clusterId,
            }))
          );
        }
      } catch (error) {
        console.error(`[Vector Clustering] Error processing ${feedback.id}:`, error);
        embeddingFailures++;
      }
    }

    console.log(`[Vector Clustering] Processed ${results.length} items`);
    console.log(`[Vector Clustering] Created ${newClusterIds.size} new clusters`);
    console.log(`[Vector Clustering] Modified ${changedClusterIds.size} clusters total`);

    // Generate summaries for changed clusters
    const summariesByClusterId = new Map<string, ClusterSummaryData>();

    for (const clusterId of changedClusterIds) {
      const feedbackIds = clusterFeedbackMap.get(clusterId) || [];
      if (feedbackIds.length === 0) continue;

      // Fetch feedback items for summary
      const items = await Promise.all(feedbackIds.map((id) => getFeedbackItemById(projectId, id)));
      const validItems = items.filter((item): item is FeedbackItem => item !== null);

      if (validItems.length > 0) {
        const summary = await generateClusterSummary(validItems);
        summariesByClusterId.set(clusterId, summary);
      }
    }

    // Update Redis with cluster data
    const pipeline = redis.pipeline();
    const timestamp = new Date().toISOString();

    for (const clusterId of changedClusterIds) {
      const feedbackIds = clusterFeedbackMap.get(clusterId) || [];
      const summary = summariesByClusterId.get(clusterId);
      const isNew = newClusterIds.has(clusterId);

      if (isNew && summary) {
        // Create new cluster
        const payload: Record<string, string> = {
          id: clusterId,
          project_id: projectId,
          title: summary.title,
          summary: summary.summary,
          status: 'new',
          created_at: timestamp,
          updated_at: timestamp,
        };
        if (summary.issueTitle) payload.issue_title = summary.issueTitle;
        if (summary.issueDescription) payload.issue_description = summary.issueDescription;
        if (summary.repoUrl) payload.github_repo_url = summary.repoUrl;

        pipeline.hset(clusterKey(projectId, clusterId), payload);
        pipeline.sadd(clusterAllKey(projectId), clusterId);
      } else if (summary) {
        // Update existing cluster
        const updatePayload: Record<string, string> = {
          summary: summary.summary,
          updated_at: timestamp,
        };
        if (summary.issueTitle) updatePayload.issue_title = summary.issueTitle;
        if (summary.issueDescription) updatePayload.issue_description = summary.issueDescription;
        if (summary.repoUrl) updatePayload.github_repo_url = summary.repoUrl;

        pipeline.hset(clusterKey(projectId, clusterId), updatePayload);
      }

      // Update cluster items
      pipeline.del(clusterItemsKey(projectId, clusterId));
      for (const feedbackId of feedbackIds) {
        pipeline.sadd(clusterItemsKey(projectId, clusterId), feedbackId);
        pipeline.hset(feedbackKey(projectId, feedbackId), { clustered: 'true' });
      }
    }

    // Remove successfully processed items from unclustered set
    const idsToRemove = new Set<string>(missingFeedbackIds);
    for (const result of results) {
      idsToRemove.add(result.feedbackId);
    }
    for (const id of idsToRemove) {
      pipeline.srem(feedbackUnclusteredKey(projectId), id);
    }

    await pipeline.exec();

    const duration = Date.now() - startTime;
    console.log(`[Vector Clustering] Complete in ${duration}ms`);

    return NextResponse.json({
      success: true,
      message: 'Vector-based clustering completed successfully',
      clustered: results.length,
      newClusters: newClusterIds.size,
      updatedClusters: changedClusterIds.size - newClusterIds.size,
      embeddingFailures,
      missingFeedback: missingFeedbackIds.size,
      durationMs: duration,
      threshold: SIMILARITY_THRESHOLD,
    });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('[Vector Clustering] Error:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to run vector-based clustering',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}