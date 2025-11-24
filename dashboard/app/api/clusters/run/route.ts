import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { getUnclusteredFeedbackIds, getFeedbackItem, getClusterIds } from '@/lib/redis';
import { clusterFeedbackBatch, generateClusterSummary, type ClusterData, type ClusterSummaryResult } from '@/lib/clustering';
import { batchUpdateClusters, batchRemoveFromUnclustered, type ClusterUpdate } from '@/lib/clustering-batch';
import type { FeedbackItem } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

/**
 * Run clustering on unclustered feedback items
 * POST /api/clusters/run
 */
export async function POST() {
  try {
    console.log('[Clustering] Starting clustering job...');

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

    // Fetch unclustered feedback items
    const feedbackItems = await Promise.all(unclusteredIds.map((id) => getFeedbackItem(id)));
    const validFeedback = feedbackItems.filter((item): item is FeedbackItem => item !== null);

    // OPTIMIZATION: Batch load existing clusters
    const existingClusterIds = await getClusterIds();
    const existingClusters: ClusterData[] = [];

    // Use pipeline to fetch all cluster data in one round trip
    const pipeline = redis.pipeline();
    for (const clusterId of existingClusterIds) {
      pipeline.hgetall(`cluster:${clusterId}`);
      pipeline.smembers(`cluster:items:${clusterId}`);
    }

    const pipelineResults = await pipeline.exec();

    // Parse results (alternating between hgetall and smembers)
    for (let i = 0; i < existingClusterIds.length; i++) {
      const clusterData = pipelineResults[i * 2] as any;
      const feedbackIds = pipelineResults[i * 2 + 1] as string[];

      if (!clusterData || Object.keys(clusterData).length === 0) continue;

      // Parse centroid if it exists
      let centroid: number[] = [];
      if (clusterData.centroid && typeof clusterData.centroid === 'string') {
        try {
          centroid = JSON.parse(clusterData.centroid);
        } catch {
          centroid = [];
        }
      }

      existingClusters.push({
        id: existingClusterIds[i],
        feedbackIds,
        centroid,
      });
    }

    console.log(`[Clustering] Loaded ${existingClusters.length} existing clusters via pipeline`);

    // Run clustering with lower threshold for more aggressive grouping
    // 0.65 allows items with 65% similarity to cluster together
    const { results, updatedClusters } = await clusterFeedbackBatch(
      validFeedback,
      existingClusters,
      0.65 // similarity threshold (lower = more aggressive clustering)
    );

    // Track new clusters created and old counts for smart summary regeneration
    const newClusterIds = new Set(results.filter((r) => r.isNewCluster).map((r) => r.clusterId));
    const oldClusterCounts = new Map(existingClusters.map((c) => [c.id, c.feedbackIds.length]));

    console.log(`[Clustering] Created ${newClusterIds.size} new clusters`);

    // OPTIMIZATION: Prepare batch cluster updates with smart summary regeneration
    const clusterUpdates: ClusterUpdate[] = [];

    for (const cluster of updatedClusters) {
      const isNew = newClusterIds.has(cluster.id);
      const oldCount = oldClusterCounts.get(cluster.id) || 0;
      const newCount = cluster.feedbackIds.length;

      // Get feedback items for this cluster
      const clusterFeedback = await Promise.all(
        cluster.feedbackIds.map((id) => getFeedbackItem(id))
      );
      const validClusterFeedback = clusterFeedback.filter(
        (item): item is FeedbackItem => item !== null
      );

      // Get existing summary for smart regeneration
      let existingSummary: ClusterSummaryResult | undefined;
      if (!isNew) {
        const existingData = await redis.hgetall(`cluster:${cluster.id}`);
        if (existingData) {
          existingSummary = {
            title: existingData.title as string,
            summary: existingData.summary as string,
            issueTitle: existingData.issue_title as string | undefined,
            issueDescription: existingData.issue_description as string | undefined,
            repoUrl: existingData.github_repo_url as string | undefined,
          };
        }
      }

      // OPTIMIZATION: Smart summary regeneration
      const { title, summary, issueTitle, issueDescription, repoUrl } = await generateClusterSummary(
        validClusterFeedback,
        {
          existingSummary,
          oldCount,
          newCount,
          forceRegenerate: isNew,
        }
      );

      clusterUpdates.push({
        clusterId: cluster.id,
        feedbackIds: cluster.feedbackIds,
        centroid: cluster.centroid,
        isNew,
        title,
        summary,
        issueTitle,
        issueDescription,
        repoUrl,
      });
    }

    // OPTIMIZATION: Batch update all clusters in one pipeline
    await batchUpdateClusters(clusterUpdates);

    // OPTIMIZATION: Batch remove from unclustered set
    await batchRemoveFromUnclustered(unclusteredIds);

    console.log('[Clustering] Clustering complete');

    return NextResponse.json({
      success: true,
      message: 'Clustering completed successfully',
      clustered: validFeedback.length,
      newClusters: newClusterIds.size,
      updatedClusters: updatedClusters.length - newClusterIds.size,
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
