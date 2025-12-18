import { NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Handle GET requests to retrieve statistics for a project from Redis.
 *
 * @param request - Incoming HTTP request used to extract the project ID
 * @returns JSON response containing the project's stats on success; if the project ID is missing returns `{ error: 'project_id is required' }` with HTTP status 400; on other failures returns `{ error: 'Failed to fetch stats' }` with HTTP status 500
 */
export async function GET(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    const response = await fetch(`${backendUrl}/stats?project_id=${projectId}`, {
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for stats GET`);
      const status = response.status >= 500 ? 502 : response.status;
      return NextResponse.json({ error: 'Failed to fetch stats' }, { status });
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
    console.error('Error fetching stats from backend:', error);
    return NextResponse.json({ error: 'Failed to fetch stats' }, { status: 500 });
  }
}