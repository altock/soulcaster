import { NextResponse } from 'next/server';
import { getUnclusteredCount } from '@/lib/redis';
import { requireProjectId } from '@/lib/project';

/**
 * Get the unclustered feedback count for the project associated with the request.
 *
 * @param request - Incoming HTTP request used to derive the project ID.
 * @returns A NextResponse containing JSON `{ count }` on success; responds with `400` and `{ error: 'project_id is required' }` if the project ID is missing, or `500` and `{ error: 'Failed to fetch unclustered count' }` on other failures.
 */
export async function GET(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    const count = await getUnclusteredCount(projectId);
    return NextResponse.json({ count });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('Error fetching unclustered count:', error);
    return NextResponse.json({ error: 'Failed to fetch unclustered count' }, { status: 500 });
  }
}