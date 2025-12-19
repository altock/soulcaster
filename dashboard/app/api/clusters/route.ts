import { NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Handle GET requests to return cluster data for the project identified in the request.
 *
 * @param request - Incoming HTTP request that must contain a project identifier; if the identifier is missing the handler responds with a 400 status.
 * @returns A JSON response with the cluster data on success; on validation failure returns `{ error: 'project_id is required' }` with HTTP status 400; on other failures returns `{ error: 'Failed to fetch clusters' }` with HTTP status 500.
 */
export async function GET(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    const response = await fetch(`${backendUrl}/clusters?project_id=${projectId}`, {
      signal: AbortSignal.timeout(30000),
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for clusters GET`);
      const status = response.status >= 500 ? 502 : response.status;
      return NextResponse.json({ error: 'Failed to fetch clusters' }, { status });
    }
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    if (error?.name === 'AbortError' || error?.message?.includes('timeout')) {
      return NextResponse.json({ error: 'Backend request timed out' }, { status: 503 });
    }
    console.error('Error fetching clusters from backend:', error);
    return NextResponse.json({ error: 'Failed to fetch clusters' }, { status: 500 });
  }
}