import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { getUnclusteredFeedbackIds, getFeedbackItem, getClusterIds } from '@/lib/redis';
import { clusterFeedbackBatch, generateClusterSummary, type ClusterData } from '@/lib/clustering';
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
    const feedbackItems = await Promise.all(
      unclusteredIds.map((id) => getFeedbackItem(id))
    );
    const validFeedback = feedbackItems.filter((item): item is FeedbackItem => item !== null);

    // Get existing clusters
    const existingClusterIds = await getClusterIds();
    const existingClusters: ClusterData[] = [];

    for (const clusterId of existingClusterIds) {
      const clusterData = await redis.hgetall(`cluster:${clusterId}`);
      if (!clusterData) continue;

      // Get feedback IDs in this cluster
      const feedbackIds = (await redis.smembers(`cluster:items:${clusterId}`)) as string[];

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
        id: clusterId,
        feedbackIds,
        centroid,
      });
    }

    console.log(`[Clustering] Processing against ${existingClusters.length} existing clusters`);

    // Run clustering
    const { results, updatedClusters } = await clusterFeedbackBatch(
      validFeedback,
      existingClusters,
      0.80 // similarity threshold
    );

    // Track new clusters created
    const newClusterIds = new Set(
      results.filter((r) => r.isNewCluster).map((r) => r.clusterId)
    );

    console.log(`[Clustering] Created ${newClusterIds.size} new clusters`);

    // Update Redis with clustering results
    for (const cluster of updatedClusters) {
      // Get feedback items for this cluster
      const clusterFeedback = await Promise.all(
        cluster.feedbackIds.map((id) => getFeedbackItem(id))
      );
      const validClusterFeedback = clusterFeedback.filter(
        (item): item is FeedbackItem => item !== null
      );

      // Generate summary
      const { title, summary } = await generateClusterSummary(validClusterFeedback);

      const timestamp = new Date().toISOString();

      // Check if cluster is new or existing
      const isNew = newClusterIds.has(cluster.id);

      if (isNew) {
        // Create new cluster
        await redis.hset(`cluster:${cluster.id}`, {
          id: cluster.id,
          title,
          summary,
          status: 'new',
          created_at: timestamp,
          updated_at: timestamp,
          centroid: JSON.stringify(cluster.centroid),
        });
      } else {
        // Update existing cluster
        await redis.hset(`cluster:${cluster.id}`, {
          summary, // Update summary with new items
          updated_at: timestamp,
          centroid: JSON.stringify(cluster.centroid),
        });
      }

      // Update cluster items set
      await redis.del(`cluster:items:${cluster.id}`);
      if (cluster.feedbackIds.length > 0) {
        await redis.sadd(`cluster:items:${cluster.id}`, ...cluster.feedbackIds);
      }

      // Mark feedback as clustered
      for (const feedbackId of cluster.feedbackIds) {
        await redis.hset(`feedback:${feedbackId}`, { clustered: 'true' });
      }
    }

    // Remove items from unclustered set
    if (unclusteredIds.length > 0) {
      await redis.srem('feedback:unclustered', ...unclusteredIds);
    }

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
