import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { parseRepoString, validateRepo } from '@/lib/github';
import type { GitHubRepo } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

/**
 * GET /api/config/github/repos
 * List all configured GitHub repositories
 */
export async function GET() {
  try {
    console.log('[GitHub] Fetching configured repos');

    // Get all repo names from the set
    const repoNames = (await redis.smembers('github:repos')) as string[];
    console.log(`[GitHub] Found ${repoNames.length} configured repos`);

    // Get all GitHub feedback IDs
    const allGithubFeedbackIds = (await redis.zrange('feedback:source:github', 0, -1)) as string[];

    // Count issues per repo by fetching and checking the repo field
    const repoIssueCounts: Record<string, number> = {};

    // Fetch all GitHub feedback items to count by repo
    if (allGithubFeedbackIds.length > 0) {
      const pipeline = redis.pipeline();
      allGithubFeedbackIds.forEach(id => {
        pipeline.hget(`feedback:${id}`, 'repo');
      });
      const repoFields = await pipeline.exec() as (string | null)[];

      // Count issues per repo
      repoFields.forEach((repo) => {
        if (repo) {
          repoIssueCounts[repo] = (repoIssueCounts[repo] || 0) + 1;
        }
      });
    }

    // Fetch full config for each repo
    const repos: GitHubRepo[] = [];
    for (const repoName of repoNames) {
      const repoData = await redis.hgetall(`github:repo:${repoName}`);
      if (repoData) {
        repos.push({
          owner: repoData.owner as string,
          repo: repoData.repo as string,
          full_name: repoName,
          last_synced: repoData.last_synced as string | undefined,
          issue_count: repoIssueCounts[repoName] || 0, // Use actual count from Redis
          enabled: repoData.enabled === 'true',
        });
      }
    }

    return NextResponse.json({ repos });
  } catch (error) {
    console.error('[GitHub] Error fetching repos:', error);
    return NextResponse.json(
      {
        error: 'Failed to fetch GitHub repos',
        detail: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

/**
 * POST /api/config/github/repos
 * Add or update a GitHub repository
 * Body: { repo: "owner/repo" or "https://github.com/owner/repo", enabled?: boolean }
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { repo: repoString, enabled = true } = body;

    if (!repoString) {
      return NextResponse.json(
        { error: 'Missing required field: repo' },
        { status: 400 }
      );
    }

    console.log(`[GitHub] Adding/updating repo: ${repoString}`);

    // Parse repo string
    let owner: string, repo: string;
    try {
      const parsed = parseRepoString(repoString);
      owner = parsed.owner;
      repo = parsed.repo;
    } catch (error) {
      return NextResponse.json(
        {
          error: 'Invalid repo format',
          detail: error instanceof Error ? error.message : 'Use format "owner/repo"',
        },
        { status: 400 }
      );
    }

    const fullName = `${owner}/${repo}`;

    // Validate that the repo exists and is accessible
    try {
      await validateRepo(owner, repo);
    } catch (error) {
      return NextResponse.json(
        {
          error: 'Repository validation failed',
          detail: error instanceof Error ? error.message : 'Unknown error',
        },
        { status: 400 }
      );
    }

    // Check if repo already exists
    const existingRepo = await redis.hgetall(`github:repo:${fullName}`);
    const isUpdate = existingRepo && Object.keys(existingRepo).length > 0;

    // Store repo configuration
    await redis.hset(`github:repo:${fullName}`, {
      owner,
      repo,
      full_name: fullName,
      enabled: enabled.toString(),
      ...(isUpdate ? {} : { issue_count: '0' }), // Don't overwrite count on update
    });

    // Add to repos set
    await redis.sadd('github:repos', fullName);

    console.log(`[GitHub] ${isUpdate ? 'Updated' : 'Added'} repo: ${fullName}`);

    const repoConfig: GitHubRepo = {
      owner,
      repo,
      full_name: fullName,
      last_synced: existingRepo?.last_synced as string | undefined,
      issue_count: existingRepo?.issue_count
        ? parseInt(existingRepo.issue_count as string)
        : 0,
      enabled,
    };

    return NextResponse.json(
      {
        message: `Repository ${isUpdate ? 'updated' : 'added'} successfully`,
        repo: repoConfig,
      },
      { status: isUpdate ? 200 : 201 }
    );
  } catch (error) {
    console.error('[GitHub] Error adding/updating repo:', error);
    return NextResponse.json(
      {
        error: 'Failed to add/update repository',
        detail: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
