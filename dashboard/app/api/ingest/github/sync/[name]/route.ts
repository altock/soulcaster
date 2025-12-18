import { NextRequest, NextResponse } from 'next/server';
import { getProjectId } from '@/lib/project';
import { getGitHubToken } from '@/lib/auth';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Proxy GitHub sync to the backend ingestion API.
 *
 * The backend owns all writes; this route simply forwards the request.
 * Passes the user's GitHub OAuth token for API authentication.
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  const projectId = await getProjectId(request);
  if (!projectId) {
    return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
  }

  const githubToken = await getGitHubToken();
  if (!githubToken) {
    return NextResponse.json(
      { error: 'GitHub authentication required. Please sign in with GitHub.' },
      { status: 401 }
    );
  }

  const { name } = await params;
  const repoName = decodeURIComponent(name);

  const url = `${backendUrl}/ingest/github/sync/${encodeURIComponent(repoName)}?project_id=${projectId}`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-GitHub-Token': githubToken,
      },
      signal: AbortSignal.timeout(60000), // Increased timeout to 60s for large repos
    });

    if (!response.ok) {
      console.error(`Backend returned ${response.status} for GitHub sync ${repoName}`);
      const status = response.status >= 500 ? 502 : response.status;
      return NextResponse.json({ error: 'Sync failed' }, { status });
    }

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    if (error?.name === 'AbortError' || error?.message?.includes('timeout')) {
      return NextResponse.json(
        {
          success: false,
          error: 'Sync failed',
          detail: 'Backend request timed out',
        },
        { status: 503 }
      );
    }
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