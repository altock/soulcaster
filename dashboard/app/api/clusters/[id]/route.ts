import { NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Retrieve a cluster by its ID and respond with JSON.
 *
 * @param params - Promise resolving to route parameters; must provide `id` of the cluster
 * @returns The HTTP JSON response: the cluster object on success, or an error object (`{ error: string }`) with a corresponding HTTP status on failure
 */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const projectId = await requireProjectId(request);

    // Validate ID format (UUID or numeric)
    if (!id || !/^[a-zA-Z0-9-]+$/.test(id)) {
      return NextResponse.json({ error: 'Invalid cluster ID' }, { status: 400 });
    }

    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/74eaca46-c446-486d-8f34-4bfda796b26c', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: 'debug-session',
        runId: 'run1',
        hypothesisId: 'H1',
        location: 'dashboard/app/api/clusters/[id]/route.ts:GET',
        message: 'cluster fetch start',
        data: { clusterId: id, hasProjectId: Boolean(projectId) },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion

    const response = await fetch(`${backendUrl}/clusters/${id}?project_id=${projectId}`, {
      signal: AbortSignal.timeout(10000),
    });

    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/74eaca46-c446-486d-8f34-4bfda796b26c', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: 'debug-session',
        runId: 'run1',
        hypothesisId: 'H2',
        location: 'dashboard/app/api/clusters/[id]/route.ts:GET',
        message: 'cluster fetch response',
        data: { status: response.status, ok: response.ok },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion

    if (!response.ok) {
      console.error(`Backend returned ${response.status} for cluster ${id}`);
      const status = response.status >= 500 ? 502 : response.status;
      return NextResponse.json({ error: 'Failed to fetch cluster' }, { status });
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
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/74eaca46-c446-486d-8f34-4bfda796b26c', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: 'debug-session',
        runId: 'run1',
        hypothesisId: 'H3',
        location: 'dashboard/app/api/clusters/[id]/route.ts:GET',
        message: 'cluster fetch error',
        data: { name: error?.name, message: error?.message },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
    console.error('Error fetching cluster from backend:', error);
    return NextResponse.json({ error: 'Failed to fetch cluster' }, { status: 500 });
  }
}