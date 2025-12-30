import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Proxy the trigger-poll request to the backend.
 *
 * This allows authenticated users to trigger the Reddit poller for their project
 * without exposing the backend URL or dealing with CORS issues.
 *
 * Requires authentication and project_id.
 */
export async function POST(request: Request) {
  try {
    // Check authentication
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Get project ID
    const projectId = await requireProjectId(request);

    const response = await fetch(`${backendUrl}/admin/trigger-poll?project_id=${projectId}`, {
      method: 'POST',
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for trigger-poll POST`);
      const status = response.status >= 500 ? 502 : response.status;
      return NextResponse.json({ error: 'Failed to trigger poll' }, { status });
    }
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    if (error?.name === 'AbortError' || error?.message?.includes('timeout')) {
      return NextResponse.json({ error: 'Request timed out. Please try again.' }, { status: 503 });
    }
    console.error('Error triggering poll:', error);
    return NextResponse.json(
      { error: 'Failed to trigger poll' },
      { status: 500 }
    );
  }
}
