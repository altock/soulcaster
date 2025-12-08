import { NextResponse } from 'next/server';
import { getClusterDetail } from '@/lib/redis';
import { requireProjectId } from '@/lib/project';

/**
 * Fetch a cluster by ID directly from Redis and return it as a JSON response.
 *
 * @param params - Promise resolving to route parameters; must include `id` for the cluster
 * @returns The JSON response sent to the client: the cluster data on success, or an error response with appropriate HTTP status.
 */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const projectId = requireProjectId(request);

    // Validate ID format (UUID or numeric)
    if (!id || !/^[a-zA-Z0-9-]+$/.test(id)) {
      return NextResponse.json({ error: 'Invalid cluster ID' }, { status: 400 });
    }

    const cluster = await getClusterDetail(projectId, id);

    if (!cluster) {
      return NextResponse.json({ error: 'Cluster not found' }, { status: 404 });
    }

    return NextResponse.json(cluster);
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('Error fetching cluster from Redis:', error);
    return NextResponse.json({ error: 'Failed to fetch cluster' }, { status: 500 });
  }
}
