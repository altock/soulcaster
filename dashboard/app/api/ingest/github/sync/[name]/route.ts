import { NextRequest, NextResponse } from 'next/server';
import { getProjectId } from '@/lib/project';

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

/**
 * Proxy GitHub sync to the backend ingestion API.
 *
 * The backend owns all writes; this route simply forwards the request.
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  const projectId = await getProjectId(request);
  if (!projectId) {
    return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
  }

  const { name } = await params;
  const repoName = decodeURIComponent(name);

  const url = `${backendUrl}/ingest/github/sync/${encodeURIComponent(repoName)}?project_id=${projectId}`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    return NextResponse.json(
      {
        success: false,
        error: 'Sync failed',
        detail: error?.message || 'Unknown error',
      },
      { status: 500 }
    );
  }
}