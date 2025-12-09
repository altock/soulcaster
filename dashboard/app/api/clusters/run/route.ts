import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { randomUUID } from 'crypto';
import { getUnclusteredFeedbackIds, getFeedbackItem, getClusterIds } from '@/lib/redis';
import {
  clusterFeedbackBatchOptimized,
  generateClusterSummary,
  ClusteringBatch,
  type ClusterData,
} from '@/lib/clustering';
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

/**
 * Apply all cluster and feedback updates to Redis in a single pipelined batch.
 *
 * Performs writes for only the clusters that changed: creates new cluster records, updates existing cluster hashes and centroids, replaces cluster item sets, marks feedback items as clustered, and removes specified IDs from the project's unclustered set.
 *
 * @param projectId - Project identifier used to scope Redis keys
 * @param batch - ClusteringBatch containing clusters and their current feedback IDs and centroids
 * @param changedClusterIds - Set of cluster IDs whose data or membership changed and should be written
 * @param newClusterIds - Set of cluster IDs that were created in this run (written with `status: 'new'` and creation timestamp)
 * @param summariesByClusterId - Map of cluster ID → generated summary payload (title, summary, and optional issueTitle, issueDescription, repoUrl) to store on cluster records
 * @param idsToRemoveFromUnclustered - Set of feedback IDs to remove from the project's unclustered set; only includes IDs that were successfully clustered or whose feedback documents were missing (IDs that failed embedding generation are intentionally excluded so they remain for retry)
 */
async function executeBatchedRedisOperations(
  projectId: string,
  batch: ClusteringBatch,
  changedClusterIds: Set<string>,
  newClusterIds: Set<string>,
  summariesByClusterId: Map<
    string,
    { title: string; summary: string; issueTitle?: string; issueDescription?: string; repoUrl?: string }
  >,
  idsToRemoveFromUnclustered: Set<string>
): Promise<void> {
  const pipeline = redis.pipeline();

  const timestamp = new Date().toISOString();

  // Iterate only changed clusters - O(changed) instead of O(all)
  for (const clusterId of changedClusterIds) {
    const cluster = batch.getCluster(clusterId);
    if (!cluster) continue;

    const summary = summariesByClusterId.get(cluster.id);
    const isNew = newClusterIds.has(cluster.id);

    if (isNew && summary) {
      // Create new cluster
      const payload: Record<string, string> = {
        id: cluster.id,
        project_id: projectId,
        title: summary.title,
        summary: summary.summary,
        status: 'new',
        created_at: timestamp,
        updated_at: timestamp,
        centroid: JSON.stringify(cluster.centroid),
      };
      if (summary.issueTitle) payload.issue_title = summary.issueTitle;
      if (summary.issueDescription) payload.issue_description = summary.issueDescription;
      if (summary.repoUrl) payload.github_repo_url = summary.repoUrl;

      pipeline.hset(clusterKey(projectId, cluster.id), payload);
      pipeline.sadd(clusterAllKey(projectId), cluster.id);
    } else if (summary) {
      // Update existing cluster
      const updatePayload: Record<string, string> = {
        summary: summary.summary,
        updated_at: timestamp,
        centroid: JSON.stringify(cluster.centroid),
      };
      if (summary.issueTitle) updatePayload.issue_title = summary.issueTitle;
      if (summary.issueDescription) updatePayload.issue_description = summary.issueDescription;
      if (summary.repoUrl) updatePayload.github_repo_url = summary.repoUrl;

      pipeline.hset(clusterKey(projectId, cluster.id), updatePayload);
    }

    // Update cluster items - delete old set and add all items
    pipeline.del(clusterItemsKey(projectId, cluster.id));
    if (cluster.feedbackIds.length > 0) {
      // Use individual sadd calls for type safety with Upstash pipeline
      for (const feedbackId of cluster.feedbackIds) {
        pipeline.sadd(clusterItemsKey(projectId, cluster.id), feedbackId);
      }
    }

    // Mark feedback as clustered
    for (const feedbackId of cluster.feedbackIds) {
      pipeline.hset(feedbackKey(projectId, feedbackId), { clustered: 'true' });
    }
  }

  // Remove only successfully processed items from unclustered set
  // IDs that failed embedding generation remain for retry
  if (idsToRemoveFromUnclustered.size > 0) {
    for (const id of idsToRemoveFromUnclustered) {
      pipeline.srem(feedbackUnclusteredKey(projectId), id);
    }
  }

  // Execute all operations in a single round-trip
  await pipeline.exec();
}

/**
 * Create singleton clusters for each provided feedback item and mark them as clustered.
 *
 * Generates a cluster and cluster-item membership for each item, writes cluster metadata to Redis
 * (including a generated summary and timestamped fields), marks the feedback item as clustered,
 * and removes it from the project's unclustered set while adding its id to `removeFromUnclustered`.
 *
 * @param projectId - Project identifier used to scope Redis keys
 * @param feedbackItems - Array of feedback items to convert into singleton clusters
 * @param removeFromUnclustered - Set that will be populated with IDs removed from the unclustered set
 * @returns An object with `created` equal to the number of singleton clusters created
 */
async function createSingletonClusters(
  projectId: string,
  feedbackItems: FeedbackItem[],
  removeFromUnclustered: Set<string>
) {
  if (feedbackItems.length === 0) return { created: 0 };

  const pipeline = redis.pipeline();
  const timestamp = new Date().toISOString();

  const summaries = await Promise.all(
    feedbackItems.map(async (item) => {
      try {
        return await generateClusterSummary([item]);
      } catch (error) {
        console.error('[Clustering] Failed to generate summary for singleton cluster', error);
        return {
          title: item.title || 'Feedback',
          summary: item.body?.substring(0, 120) || 'Single feedback item',
          issueTitle: item.title || 'Feedback',
          issueDescription: item.body || 'Single feedback item',
          repoUrl: item.github_repo_url,
        };
      }
    })
  );

  feedbackItems.forEach((item, idx) => {
    const clusterId = randomUUID();
    const summary = summaries[idx];

    const payload: Record<string, string> = {
      id: clusterId,
      title: summary.title,
      summary: summary.summary,
      status: 'new',
      project_id: projectId,
      created_at: timestamp,
      updated_at: timestamp,
      centroid: '[]', // no embedding, but keep consistent shape
    };

    if (summary.issueTitle) payload.issue_title = summary.issueTitle;
    if (summary.issueDescription) payload.issue_description = summary.issueDescription;
    if (summary.repoUrl) payload.github_repo_url = summary.repoUrl;

    pipeline.hset(clusterKey(projectId, clusterId), payload);
    pipeline.sadd(clusterAllKey(projectId), clusterId);

    // Cluster items (singleton)
    pipeline.del(clusterItemsKey(projectId, clusterId));
    pipeline.sadd(clusterItemsKey(projectId, clusterId), item.id);

    // Mark feedback as clustered and remove from unclustered
    pipeline.hset(feedbackKey(projectId, item.id), { clustered: 'true' });
    pipeline.srem(feedbackUnclusteredKey(projectId), item.id);
    removeFromUnclustered.add(item.id);
  });

  await pipeline.exec();
  return { created: feedbackItems.length };
}

/**
 * Handle POST /api/clusters/run to run optimized clustering for a project's unclustered feedback.
 *
 * Performs optimized clustering using existing clusters and unclustered feedback: regenerates summaries only for changed clusters, batches all Redis writes in a single pipeline, caches fetched feedback, updates centroids incrementally, and falls back to creating singleton clusters for items that could not be clustered.
 *
 * @returns A JSON response: on success includes clustering metrics (`clustered`, `newClusters`, `updatedClusters`, `skippedClusters`, `failedEmbeddings`, `missingFeedback`, `durationMs`); if `project_id` is missing returns a 400 with an `error` message; other failures return a 500 with `error` and `details`.
export async function POST(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    console.log('[Clustering] Starting optimized clustering job...');
    const startTime = Date.now();

    // Get unclustered feedback IDs
    const unclusteredIds = await getUnclusteredFeedbackIds(projectId);
    console.log(`[Clustering] Found ${unclusteredIds.length} unclustered items`);

    if (unclusteredIds.length === 0) {
      return NextResponse.json({
        success: true,
        message: 'No unclustered feedback to process',
        clustered: 0,
        newClusters: 0,
      });
    }

    // Fetch unclustered feedback items and track which IDs are missing
    const feedbackItems = await Promise.all(unclusteredIds.map((id) => getFeedbackItem(projectId, id)));
    const validFeedback: FeedbackItem[] = [];
    const missingFeedbackIds: Set<string> = new Set();

    for (let i = 0; i < unclusteredIds.length; i++) {
      const item = feedbackItems[i];
      if (item !== null) {
        validFeedback.push(item);
      } else {
        // Track missing IDs - these should be removed from unclustered set
        missingFeedbackIds.add(unclusteredIds[i]);
      }
    }

    if (missingFeedbackIds.size > 0) {
      console.log(`[Clustering] ${missingFeedbackIds.size} feedback items not found (will be removed from unclustered)`);
    }

    // Get existing clusters
    const existingClusterIds = await getClusterIds(projectId);
    const existingClusters: ClusterData[] = [];

    // Fetch existing cluster data in parallel
    const clusterDataPromises = existingClusterIds.map(async (clusterId) => {
      const [clusterData, feedbackIds] = await Promise.all([
        redis.hgetall(clusterKey(projectId, clusterId)),
        redis.smembers(clusterItemsKey(projectId, clusterId)) as Promise<string[]>,
      ]);

      if (!clusterData) return null;

      let centroid: number[] = [];
      if (clusterData.centroid && typeof clusterData.centroid === 'string') {
        try {
          centroid = JSON.parse(clusterData.centroid);
        } catch {
          centroid = [];
        }
      }

      return {
        id: clusterId,
        feedbackIds,
        centroid,
      };
    });

    const clusterResults = await Promise.all(clusterDataPromises);
    for (const cluster of clusterResults) {
      if (cluster) existingClusters.push(cluster);
    }

    console.log(`[Clustering] Processing against ${existingClusters.length} existing clusters`);

    // Run OPTIMIZED clustering - returns batch with change tracking
    const { results, batch } = await clusterFeedbackBatchOptimized(
      validFeedback,
      existingClusters,
      0.65 // similarity threshold
    );

    const allClusters = batch.getUpdatedClusters();
    const newClusterIds = new Set(batch.getNewClusterIds());
    const changedClusterIds = new Set(batch.getChangedClusterIds());

    console.log(`[Clustering] Created ${newClusterIds.size} new clusters`);
    console.log(`[Clustering] Modified ${changedClusterIds.size} clusters total`);
    console.log(
      `[Clustering] Skipping ${allClusters.length - changedClusterIds.size} unchanged clusters`
    );

    // OPTIMIZATION: Only generate summaries for CHANGED clusters
    // This is the biggest performance win - avoid O(n) LLM calls
    const clustersNeedingSummary = batch.getClustersNeedingSummaryRegeneration(
      allClusters.map((c) => c.id)
    );

    console.log(`[Clustering] Generating summaries for ${clustersNeedingSummary.length} clusters`);

    // Generate summaries in parallel for changed clusters only
    const summariesByClusterId = new Map<
      string,
      { title: string; summary: string; issueTitle?: string; issueDescription?: string; repoUrl?: string }
    >();

    await Promise.all(
      clustersNeedingSummary.map(async (clusterId) => {
        const cluster = batch.getCluster(clusterId);
        if (!cluster) return;

        // Use cached feedback items first, fetch missing ones
        const { found, missing } = batch.getCachedFeedbackItems(cluster.feedbackIds);

        // Fetch any missing feedback items
        let allFeedback = [...found];
        if (missing.length > 0) {
          const fetchedItems = await Promise.all(
            missing.map((id) => getFeedbackItem(projectId, id))
          );
          const validFetched = fetchedItems.filter((item): item is FeedbackItem => item !== null);
          allFeedback = [...allFeedback, ...validFetched];
          // Cache for future use
          batch.cacheFeedbackItems(validFetched);
        }

        const { title, summary, issueTitle, issueDescription, repoUrl } =
          await generateClusterSummary(allFeedback);

        summariesByClusterId.set(clusterId, {
          title,
          summary,
          issueTitle,
          issueDescription,
          repoUrl,
        });
      })
    );

    // Build set of IDs to remove from unclustered:
    // 1. IDs that were successfully clustered (appear in results)
    // 2. IDs whose feedback document was missing
    // IDs that failed embedding generation are NOT removed - they stay for retry
    const idsToRemoveFromUnclustered = new Set<string>(missingFeedbackIds);
    for (const result of results) {
      idsToRemoveFromUnclustered.add(result.feedbackId);
    }

    const failedEmbeddingCount = validFeedback.length - results.length;
    if (failedEmbeddingCount > 0) {
      console.log(`[Clustering] ${failedEmbeddingCount} items failed embedding generation (will retry next run)`);
    }

    // OPTIMIZATION: Execute all Redis operations in a single pipeline
    await executeBatchedRedisOperations(
      projectId,
      batch,
      changedClusterIds,
      newClusterIds,
      summariesByClusterId,
      idsToRemoveFromUnclustered
    );

    // Fallback: if some feedback items weren't clustered (e.g., embedding failures),
    // ensure they still become singleton clusters so the UI never shows "no clusters".
    const processedIds = new Set(results.map((r) => r.feedbackId));
    const unprocessedFeedback = validFeedback.filter((item) => !processedIds.has(item.id));
    let fallbackCreated = 0;

    if (unprocessedFeedback.length > 0) {
      console.log(`[Clustering] Creating ${unprocessedFeedback.length} singleton clusters (fallback)`);
      const { created } = await createSingletonClusters(
        projectId,
        unprocessedFeedback,
        idsToRemoveFromUnclustered
      );
      fallbackCreated = created;
    }

    const duration = Date.now() - startTime;
    console.log(`[Clustering] Clustering complete in ${duration}ms`);

    return NextResponse.json({
      success: true,
      message: 'Clustering completed successfully',
      clustered: results.length + fallbackCreated,
      newClusters: newClusterIds.size + fallbackCreated,
      updatedClusters: changedClusterIds.size - newClusterIds.size,
      skippedClusters: allClusters.length - changedClusterIds.size,
      failedEmbeddings: failedEmbeddingCount,
      missingFeedback: missingFeedbackIds.size,
      durationMs: duration,
    });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('[Clustering] Error running clustering:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to run clustering',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}