import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Fetch a cluster by ID by proxying to the backend.
 *
 * @param params - Promise resolving to route parameters; must include `id` for the cluster
 * @returns The JSON response sent to the client: the cluster data on success, or an error response with appropriate HTTP status.
 */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;

    // Validate ID format (UUID or numeric)
    if (!id || !/^[a-zA-Z0-9-]+$/.test(id)) {
      return NextResponse.json({ error: 'Invalid cluster ID' }, { status: 400 });
    }

    const response = await fetch(`${BACKEND_URL}/clusters/${id}`, {
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json({ error: 'Cluster not found' }, { status: 404 });
      }
      throw new Error(`Backend responded with ${response.status}`);
    }

    const cluster = await response.json();
    return NextResponse.json(cluster);
  } catch (error) {
    console.error('Error fetching cluster from backend:', error);
    return NextResponse.json({ error: 'Failed to fetch cluster' }, { status: 500 });
  }
}
