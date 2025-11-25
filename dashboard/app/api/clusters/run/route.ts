import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { getUnclusteredFeedbackIds, getFeedbackItem, getClusterIds } from '@/lib/redis';
import {
  clusterFeedbackBatchOptimized,
  generateClusterSummary,
  ClusteringBatch,
  type ClusterData,
} from '@/lib/clustering';
import type { FeedbackItem } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

/**
 * Execute batched Redis operations using pipeline
 * This is MUCH more efficient than individual calls
 *
 * @param idsToRemoveFromUnclustered - Only IDs that were successfully clustered
 *   or whose feedback document was missing. IDs that failed embedding generation
 *   are NOT included here so they remain in feedback:unclustered for retry.
 */
async function executeBatchedRedisOperations(
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

      pipeline.hset(`cluster:${cluster.id}`, payload);
      pipeline.sadd('clusters:all', cluster.id);
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

      pipeline.hset(`cluster:${cluster.id}`, updatePayload);
    }

    // Update cluster items - delete old set and add all items
    pipeline.del(`cluster:items:${cluster.id}`);
    if (cluster.feedbackIds.length > 0) {
      // Use individual sadd calls for type safety with Upstash pipeline
      for (const feedbackId of cluster.feedbackIds) {
        pipeline.sadd(`cluster:items:${cluster.id}`, feedbackId);
      }
    }

    // Mark feedback as clustered
    for (const feedbackId of cluster.feedbackIds) {
      pipeline.hset(`feedback:${feedbackId}`, { clustered: 'true' });
    }
  }

  // Remove only successfully processed items from unclustered set
  // IDs that failed embedding generation remain for retry
  if (idsToRemoveFromUnclustered.size > 0) {
    for (const id of idsToRemoveFromUnclustered) {
      pipeline.srem('feedback:unclustered', id);
    }
  }

  // Execute all operations in a single round-trip
  await pipeline.exec();
}

/**
 * Run clustering on unclustered feedback items
 * POST /api/clusters/run
 *
 * OPTIMIZATIONS:
 * 1. Only regenerate summaries for changed clusters (not all)
 * 2. Use Redis pipeline for batch operations
 * 3. Cache feedback items to avoid re-fetching
 * 4. Incremental centroid updates
 */
export async function POST() {
  try {
    console.log('[Clustering] Starting optimized clustering job...');
    const startTime = Date.now();

    // Get unclustered feedback IDs
    const unclusteredIds = await getUnclusteredFeedbackIds();
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
    const feedbackItems = await Promise.all(unclusteredIds.map((id) => getFeedbackItem(id)));
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
    const existingClusterIds = await getClusterIds();
    const existingClusters: ClusterData[] = [];

    // Fetch existing cluster data in parallel
    const clusterDataPromises = existingClusterIds.map(async (clusterId) => {
      const [clusterData, feedbackIds] = await Promise.all([
        redis.hgetall(`cluster:${clusterId}`),
        redis.smembers(`cluster:items:${clusterId}`) as Promise<string[]>,
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
          const fetchedItems = await Promise.all(missing.map((id) => getFeedbackItem(id)));
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
      batch,
      changedClusterIds,
      newClusterIds,
      summariesByClusterId,
      idsToRemoveFromUnclustered
    );

    const duration = Date.now() - startTime;
    console.log(`[Clustering] Clustering complete in ${duration}ms`);

    return NextResponse.json({
      success: true,
      message: 'Clustering completed successfully',
      clustered: results.length,
      newClusters: newClusterIds.size,
      updatedClusters: changedClusterIds.size - newClusterIds.size,
      skippedClusters: allClusters.length - changedClusterIds.size,
      failedEmbeddings: failedEmbeddingCount,
      missingFeedback: missingFeedbackIds.size,
      durationMs: duration,
    });
  } catch (error) {
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
