import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { cosineSimilarity, calculateCentroid } from '@/lib/clustering';
import { CLEANUP_MERGE_THRESHOLD } from '@/lib/vector';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

interface ClusterInfo {
  id: string;
  title: string;
  status: string;
  feedbackIds: string[];
  centroid: number[];
}

/**
 * Find clusters that should be merged based on centroid similarity
 * Uses Union-Find to group similar clusters transitively
 */
function findDuplicateGroups(clusters: ClusterInfo[], threshold: number): ClusterInfo[][] {
  const n = clusters.length;
  const parent = Array.from({ length: n }, (_, i) => i);

  function find(x: number): number {
    if (parent[x] !== x) parent[x] = find(parent[x]);
    return parent[x];
  }

  function union(x: number, y: number): void {
    const px = find(x);
    const py = find(y);
    if (px !== py) parent[px] = py;
  }

  // Compare all pairs and union similar clusters
  for (let i = 0; i < n; i++) {
    if (clusters[i].centroid.length === 0) continue;
    for (let j = i + 1; j < n; j++) {
      if (clusters[j].centroid.length === 0) continue;
      const similarity = cosineSimilarity(clusters[i].centroid, clusters[j].centroid);
      if (similarity >= threshold) {
        union(i, j);
      }
    }
  }

  // Group by parent
  const groups = new Map<number, ClusterInfo[]>();
  for (let i = 0; i < n; i++) {
    const root = find(i);
    const group = groups.get(root) || [];
    group.push(clusters[i]);
    groups.set(root, group);
  }

  // Return only groups with duplicates
  return Array.from(groups.values()).filter((g) => g.length > 1);
}

/**
 * Cleanup duplicate clusters by merging clusters with similar centroids
 * POST /api/clusters/cleanup
 *
 * Threshold defined in lib/vector.ts (CLEANUP_MERGE_THRESHOLD)
 */
export async function POST() {
  try {
    console.log('[Cleanup] Starting duplicate cluster cleanup...');

    // Get all cluster IDs
    const clusterIds = (await redis.smembers('clusters:all')) as string[];
    console.log(`[Cleanup] Found ${clusterIds.length} total clusters`);

    // Fetch all cluster info including centroids
    const clusters: ClusterInfo[] = [];
    for (const id of clusterIds) {
      const data = await redis.hgetall(`cluster:${id}`);
      if (data && data.title) {
        const feedbackIds = (await redis.smembers(`cluster:items:${id}`)) as string[];

        let centroid: number[] = [];
        if (data.centroid && typeof data.centroid === 'string') {
          try {
            centroid = JSON.parse(data.centroid);
          } catch {
            centroid = [];
          }
        }

        clusters.push({
          id,
          title: data.title as string,
          status: data.status as string,
          feedbackIds,
          centroid,
        });
      }
    }

    console.log(`[Cleanup] Loaded ${clusters.length} clusters with data`);

    // Find duplicate groups using centroid similarity
    // Threshold from lib/vector.ts (single source of truth)
    const duplicateGroups = findDuplicateGroups(clusters, CLEANUP_MERGE_THRESHOLD);

    console.log(`[Cleanup] Found ${duplicateGroups.length} groups of similar clusters`);

    let mergedCount = 0;
    let deletedCount = 0;

    // Merge duplicates
    for (const group of duplicateGroups) {
      const titles = group.map((c) => c.title).join(', ');
      console.log(`[Cleanup] Merging ${group.length} similar clusters: "${titles.substring(0, 100)}..."`);

      // Keep the cluster with most feedback items, or prefer "fixing" status
      const sorted = [...group].sort((a, b) => {
        if (a.status === 'fixing' && b.status !== 'fixing') return -1;
        if (b.status === 'fixing' && a.status !== 'fixing') return 1;
        return b.feedbackIds.length - a.feedbackIds.length;
      });

      const keepCluster = sorted[0];
      const duplicates = sorted.slice(1);

      // Collect all unique feedback IDs from duplicates
      const allFeedbackIds = new Set(keepCluster.feedbackIds);
      const allCentroids = [keepCluster.centroid];

      for (const dup of duplicates) {
        for (const feedbackId of dup.feedbackIds) {
          allFeedbackIds.add(feedbackId);
        }
        if (dup.centroid.length > 0) {
          allCentroids.push(dup.centroid);
        }
      }

      // Add all feedback IDs to the kept cluster
      const newIds = Array.from(allFeedbackIds).filter(
        (id) => !keepCluster.feedbackIds.includes(id)
      );
      if (newIds.length > 0) {
        // Add each ID individually to avoid spread issues with Upstash types
        for (const newId of newIds) {
          await redis.sadd(`cluster:items:${keepCluster.id}`, newId);
        }
        console.log(`[Cleanup] Added ${newIds.length} feedback items to ${keepCluster.id}`);
      }

      // Update centroid to be the average of all merged clusters
      if (allCentroids.length > 1) {
        const newCentroid = calculateCentroid(allCentroids);
        await redis.hset(`cluster:${keepCluster.id}`, {
          centroid: JSON.stringify(newCentroid),
          updated_at: new Date().toISOString(),
        });
      }

      // Delete duplicate clusters
      for (const dup of duplicates) {
        await redis.del(`cluster:${dup.id}`);
        await redis.del(`cluster:items:${dup.id}`);
        await redis.srem('clusters:all', dup.id);
        deletedCount++;
        console.log(`[Cleanup] Deleted duplicate cluster ${dup.id}`);
      }

      mergedCount++;
    }

    console.log('[Cleanup] Cleanup complete');

    return NextResponse.json({
      success: true,
      message: 'Duplicate clusters cleaned up successfully',
      totalClusters: clusterIds.length,
      duplicateGroups: duplicateGroups.length,
      mergedGroups: mergedCount,
      deletedClusters: deletedCount,
      remainingClusters: clusterIds.length - deletedCount,
    });
  } catch (error) {
    console.error('[Cleanup] Error cleaning up clusters:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to cleanup duplicate clusters',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
