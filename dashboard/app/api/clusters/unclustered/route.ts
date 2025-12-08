import { NextResponse } from 'next/server';
import { getUnclusteredCount } from '@/lib/redis';
import { requireProjectId } from '@/lib/project';

/**
 * Get count of unclustered feedback items
 * GET /api/clusters/unclustered
 */
export async function GET(request: Request) {
  try {
    const projectId = requireProjectId(request);
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
