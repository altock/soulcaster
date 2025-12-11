import { NextRequest, NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { requireProjectId } from '@/lib/project';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

const projectReposKey = (projectId: string) => `github:repos:${projectId}`;
const projectRepoKey = (projectId: string, fullName: string) => `github:repo:${projectId}:${fullName}`;
const legacyReposKey = 'github:repos';
const legacyRepoKey = (fullName: string) => `github:repo:${fullName}`;

/**
 * DELETE /api/config/github/repos/[name]
 * Remove a GitHub repository from configuration
 * Name should be URL-encoded "owner/repo" (e.g., "anthropics%2Fclaude-code")
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  try {
    const projectId = await requireProjectId(request);
    const { name } = await params;

    // Decode URL-encoded repo name (e.g., "anthropics%2Fclaude-code" -> "anthropics/claude-code")
    const repoName = decodeURIComponent(name);

    console.log(`[GitHub] Removing repo: ${repoName}`);

    // Check if repo exists in project scope or legacy scope
    const [projectData, legacyData] = await Promise.all([
      redis.hgetall(projectRepoKey(projectId, repoName)),
      redis.hgetall(legacyRepoKey(repoName)),
    ]);

    if ((!projectData || Object.keys(projectData).length === 0) && (!legacyData || Object.keys(legacyData).length === 0)) {
      return NextResponse.json(
        { error: 'Repository not found' },
        { status: 404 }
      );
    }

    // Remove repo configuration (both project-scoped and legacy to avoid re-migration)
    await redis.del(projectRepoKey(projectId, repoName));
    await redis.srem(projectReposKey(projectId), repoName);
    await redis.del(legacyRepoKey(repoName));
    await redis.srem(legacyReposKey, repoName);

    // Optionally: Remove associated feedback items (or keep them for history)
    // For now, we'll keep the feedback items but they won't be updated
    // Future enhancement: Add flag to delete associated feedback

    console.log(`[GitHub] Removed repo: ${repoName}`);

    return NextResponse.json({
      message: `Repository ${repoName} removed successfully`,
    });
  } catch (error) {
    console.error('[GitHub] Error removing repo:', error);
    return NextResponse.json(
      {
        error: 'Failed to remove repository',
        detail: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
