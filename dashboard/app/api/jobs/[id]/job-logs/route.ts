import { NextRequest, NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

function backendError(status: number) {
  return status >= 500 ? 502 : status;
}

/**
 * Proxy a request for a job's logs to the backend and return the backend response.
 *
 * @param params - A promise that resolves to the route parameters object containing the job `id`.
 * @returns On success, the backend's parsed JSON payload with the backend's HTTP status. On backend errors, a JSON object `{ error: "Failed to fetch job logs", debug: { status, url, response } }` with a mapped status (502 for backend 5xx, otherwise the backend status). Returns `{ error: "project_id is required" }` with status 400 if the project ID is missing, `{ error: "Backend request timed out" }` with status 503 on timeout, and `{ error: "Failed to fetch job logs" }` with status 500 for other failures.
 */
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const projectId = await requireProjectId(request);

    // Backend handles routing between memory and Blob
    const backendRequestUrl = `${backendUrl}/jobs/${encodeURIComponent(id)}/logs?project_id=${projectId}`;
    console.log('[logs] Fetching from backend:', backendRequestUrl);

    const response = await fetch(backendRequestUrl, {
      signal: AbortSignal.timeout(15000),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[logs] Backend returned ${response.status} for job logs GET`);
      console.error(`[logs] Backend URL: ${backendRequestUrl}`);
      console.error(`[logs] Backend response: ${errorText}`);
      return NextResponse.json({
        error: 'Failed to fetch job logs',
        debug: { status: response.status, url: backendRequestUrl, response: errorText }
      }, { status: backendError(response.status) });
    }

    const data = await response.json();
    console.log(`[logs] Fetched from ${data.source || 'unknown'}`);
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    if (error?.name === 'AbortError' || error?.message?.includes('timeout')) {
      return NextResponse.json({ error: 'Backend request timed out' }, { status: 503 });
    }
    console.error('Error fetching job logs:', error);
    return NextResponse.json({ error: 'Failed to fetch job logs' }, { status: 500 });
  }
}
