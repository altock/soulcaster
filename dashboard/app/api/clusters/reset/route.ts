import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { Index } from '@upstash/vector';
import { requireProjectId } from '@/lib/project';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

const vectorIndex = new Index({
  url: process.env.UPSTASH_VECTOR_REST_URL!,
  token: process.env.UPSTASH_VECTOR_REST_TOKEN!,
});

/**
 * Reset all clustering data for a specific project and mark all feedback as unclustered
 * POST /api/clusters/reset
 *
 * Requires project_id query parameter or in session
 */
export async function POST(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    console.log(`[Reset] Starting cluster reset for project ${projectId}...`);

    // Get all cluster IDs for this project
    const clusterIds = (await redis.smembers(`clusters:all:${projectId}`)) as string[];
    console.log(`[Reset] Found ${clusterIds.length} clusters to delete`);

    // Delete all cluster data for this project
    for (const clusterId of clusterIds) {
      await redis.del(`cluster:${projectId}:${clusterId}`);
      await redis.del(`cluster:items:${projectId}:${clusterId}`);
    }

    // Clear project's clusters:all set
    await redis.del(`clusters:all:${projectId}`);

    // Clear Upstash Vector namespace for this project
    console.log('[Reset] Clearing vector index namespace...');
    try {
      // Use namespace parameter to only clear this project's vectors
      await vectorIndex.reset({ namespace: projectId });
      console.log('[Reset] Vector index namespace cleared');
    } catch (vectorError) {
      console.error('[Reset] Error clearing vector index:', vectorError);
      // Continue anyway - vector index may be empty
    }

    // Get all feedback IDs for this project from the created sorted set
    const feedbackIds = (await redis.zrange(`feedback:created:${projectId}`, 0, -1)) as string[];
    console.log(`[Reset] Found ${feedbackIds.length} feedback items to reset`);

    // Mark all feedback as unclustered and clear stored embeddings
    for (const feedbackId of feedbackIds) {
      await redis.hset(`feedback:${projectId}:${feedbackId}`, { clustered: 'false' });
      await redis.hdel(`feedback:${projectId}:${feedbackId}`, 'embedding');
      await redis.sadd(`feedback:unclustered:${projectId}`, feedbackId);
    }

    console.log('[Reset] Reset complete');

    return NextResponse.json({
      success: true,
      message: 'Clustering data reset successfully',
      projectId,
      deletedClusters: clusterIds.length,
      resetFeedback: feedbackIds.length,
    });
  } catch (error) {
    if (error instanceof Error && error.message === 'project_id is required') {
      return NextResponse.json(
        { success: false, error: 'project_id is required' },
        { status: 400 }
      );
    }
    console.error('[Reset] Error resetting clusters:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to reset clustering data',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
