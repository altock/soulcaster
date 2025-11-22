import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Proxy a GET request to the backend to retrieve a cluster by ID and return it as a JSON response.
 *
 * @param params - Promise resolving to route parameters; must include `id` for the cluster
 * @returns The JSON response sent to the client: the cluster data on success, or `{ error: 'Failed to fetch cluster' }` with HTTP status 500 on failure.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const response = await fetch(`${BACKEND_URL}/clusters/${id}`, {
      headers: {
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching cluster:', error);
    return NextResponse.json(
      { error: 'Failed to fetch cluster' },
      { status: 500 }
    );
  }
}