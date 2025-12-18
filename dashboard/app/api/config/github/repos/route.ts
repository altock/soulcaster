import { NextRequest, NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { parseRepoString, validateRepo } from '@/lib/github';
import type { GitHubRepo } from '@/types';
import { requireProjectId } from '@/lib/project';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

const legacyReposKey = 'github:repos';
const legacyRepoKey = (fullName: string) => `github:repo:${fullName}`;
const projectReposKey = (projectId: string) => `github:repos:${projectId}`;
const projectRepoKey = (projectId: string, fullName: string) => `github:repo:${projectId}:${fullName}`;
const feedbackSourceKey = (projectId: string) => `feedback:source:${projectId}:github`;
const feedbackKey = (projectId: string, id: string) => `feedback:${projectId}:${id}`;

async function migrateLegacyReposToProject(projectId: string, existing: string[] = []): Promise<string[]> {
  const legacyNames = (await redis.smembers(legacyReposKey)) as string[];
  if (!legacyNames || legacyNames.length === 0) return [];

  const existingSet = new Set(existing);
  const migrated: string[] = [];
  for (const name of legacyNames) {
    if (existingSet.has(name)) continue;
    const legacyData = await redis.hgetall(legacyRepoKey(name));
    if (legacyData && Object.keys(legacyData).length > 0) {
      await redis.hset(projectRepoKey(projectId, name), {
        ...legacyData,
        enabled: legacyData.enabled ?? 'true',
      });
      migrated.push(name);
    }
  }

  if (migrated.length > 0) {
    const pipeline = redis.pipeline();
    migrated.forEach((name) => pipeline.sadd(projectReposKey(projectId), name));
    await pipeline.exec();
  }

  return migrated;
}

/**
 * GET /api/config/github/repos
 * List all configured GitHub repositories
 */
export async function GET(request: NextRequest) {
  try {
    const projectId = await requireProjectId(request);
    console.log('[GitHub] Fetching configured repos for project', projectId);

    // Get project-scoped repo names (migrate missing legacy entries if any)
    let repoNames = (await redis.smembers(projectReposKey(projectId))) as string[];
    const migrated = await migrateLegacyReposToProject(projectId, repoNames);
    if (migrated.length > 0) {
      const deduped = new Set<string>([...repoNames, ...migrated]);
      repoNames = Array.from(deduped);
    }
    console.log(`[GitHub] Found ${repoNames.length} configured repos for project ${projectId}`);

    // Get all GitHub feedback IDs
    const allGithubFeedbackIds = (await redis.zrange(feedbackSourceKey(projectId), 0, -1)) as string[];

    // Count issues per repo by fetching and checking the repo field
    const repoIssueCounts: Record<string, number> = {};

    // Fetch all GitHub feedback items to count by repo
    if (allGithubFeedbackIds.length > 0) {
      const pipeline = redis.pipeline();
      allGithubFeedbackIds.forEach(id => {
        pipeline.hget(feedbackKey(projectId, id), 'repo');
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
      let repoData = await redis.hgetall(projectRepoKey(projectId, repoName));
      // Fallback to legacy data if project-scoped data is missing (during migration)
      if (!repoData || Object.keys(repoData).length === 0) {
        const legacyData = await redis.hgetall(legacyRepoKey(repoName));
        if (legacyData && Object.keys(legacyData).length > 0) {
          repoData = legacyData;
          // Write back to project scope so future reads are project-scoped
          await redis.hset(projectRepoKey(projectId, repoName), {
            ...legacyData,
            enabled: legacyData.enabled ?? 'true',
          });
        }
      }

      if (repoData && Object.keys(repoData).length > 0) {
        repos.push({
          owner: repoData.owner as string,
          repo: repoData.repo as string,
          full_name: repoName,
          last_synced: repoData.last_synced as string | undefined,
          issue_count: repoIssueCounts[repoName] || 0, // Use actual count from project-scoped feedback
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
export async function POST(request: NextRequest) {
  try {
    const projectId = await requireProjectId(request);
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

    // Check if repo already exists (project-scoped)
    const existingRepo = await redis.hgetall(projectRepoKey(projectId, fullName));
    const isUpdate = existingRepo && Object.keys(existingRepo).length > 0;

    // Store repo configuration
    await redis.hset(projectRepoKey(projectId, fullName), {
      owner,
      repo,
      full_name: fullName,
      enabled: enabled.toString(),
      ...(isUpdate ? {} : { issue_count: '0' }), // Don't overwrite count on update
    });

    // Add to repos set (project-scoped)
    await redis.sadd(projectReposKey(projectId), fullName);

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
