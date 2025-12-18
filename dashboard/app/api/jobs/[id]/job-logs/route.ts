import { NextRequest, NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

function backendError(status: number) {
  return status >= 500 ? 502 : status;
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const projectId = await requireProjectId(request);
    const { searchParams } = new URL(request.url);
    const cursor = searchParams.get('cursor') || '0';
    const limit = searchParams.get('limit') || '200';

    const backendParams = new URLSearchParams();
    backendParams.set('project_id', projectId);
    backendParams.set('cursor', cursor);
    backendParams.set('limit', limit);

    const backendRequestUrl = `${backendUrl}/jobs/${encodeURIComponent(id)}/logs?${backendParams.toString()}`;
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

