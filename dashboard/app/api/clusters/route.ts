import { NextResponse } from 'next/server';
import { getClusters } from '@/lib/redis';
import { requireProjectId } from '@/lib/project';

/**
 * Handle GET requests to return cluster data for the project identified in the request.
 *
 * @param request - Incoming HTTP request that must contain a project identifier; if the identifier is missing the handler responds with a 400 status.
 * @returns A JSON response with the cluster data on success; on validation failure returns `{ error: 'project_id is required' }` with HTTP status 400; on other failures returns `{ error: 'Failed to fetch clusters' }` with HTTP status 500.
 */
export async function GET(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    const clusters = await getClusters(projectId);
    return NextResponse.json(clusters);
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('Error fetching clusters from Redis:', error);
    return NextResponse.json({ error: 'Failed to fetch clusters' }, { status: 500 });
  }
}