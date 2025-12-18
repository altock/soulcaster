import { NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';
import { getGitHubToken } from '@/lib/auth';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Initiates a fix operation for the cluster specified by the route `id` by proxying a POST to the backend.
 *
 * @param params - Promise resolving to route parameters; must include `id`, the cluster identifier.
 * @returns The backend's JSON response when the fix is started; on failure returns an error object `{ error: 'Failed to start fix' }` with HTTP status 500.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const projectId = await requireProjectId(request);
    const githubToken = await getGitHubToken();

    // Validate ID format (UUID or numeric)
    if (!id || !/^[a-zA-Z0-9-]+$/.test(id)) {
      return NextResponse.json({ error: 'Invalid cluster ID' }, { status: 400 });
    }

    // Check if user has GitHub token
    if (!githubToken) {
      return NextResponse.json(
        { error: 'GitHub authentication required. Please sign in with GitHub to create PRs.' },
        { status: 401 }
      );
    }

    // Direct proxy to backend
    // Backend expects optional project_id query param
    const backendUrl = `${BACKEND_URL}/clusters/${encodeURIComponent(id)}/start_fix?project_id=${encodeURIComponent(projectId)}`;

    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-GitHub-Token': githubToken, // Pass user's token to backend
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      try {
        const json = JSON.parse(errorText);
        return NextResponse.json(json, { status: response.status });
      } catch {
        return NextResponse.json({ error: errorText }, { status: response.status });
      }
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('Error starting fix:', error);
    return NextResponse.json({ error: 'Failed to start fix' }, { status: 500 });
  }
}
