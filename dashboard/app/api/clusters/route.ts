import { NextResponse } from 'next/server';
import { getClusters } from '@/lib/redis';
import { requireProjectId } from '@/lib/project';

/**
 * Fetch cluster data directly from Redis.
 *
 * @returns A JSON Response containing cluster data on success, or `{ error: 'Failed to fetch clusters' }` with HTTP status 500 on failure.
 */
export async function GET(request: Request) {
  try {
    const projectId = requireProjectId(request);
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
