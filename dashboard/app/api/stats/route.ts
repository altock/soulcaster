import { NextResponse } from 'next/server';
import { getStats } from '@/lib/redis';
import { requireProjectId } from '@/lib/project';

/**
 * Handle GET requests to retrieve statistics for a project from Redis.
 *
 * @param request - Incoming HTTP request used to extract the project ID
 * @returns JSON response containing the project's stats on success; if the project ID is missing returns `{ error: 'project_id is required' }` with HTTP status 400; on other failures returns `{ error: 'Failed to fetch stats' }` with HTTP status 500
 */
export async function GET(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    const stats = await getStats(projectId);
    return NextResponse.json(stats);
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('Error fetching stats from Redis:', error);
    return NextResponse.json({ error: 'Failed to fetch stats' }, { status: 500 });
  }
}