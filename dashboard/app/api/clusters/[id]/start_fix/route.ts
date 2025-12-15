import { NextResponse } from 'next/server';

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

    // Validate ID format (UUID or numeric)
    if (!id || !/^[a-zA-Z0-9-]+$/.test(id)) {
      return NextResponse.json({ error: 'Invalid cluster ID' }, { status: 400 });
    }

    // Direct proxy to backend
    // Backend expects optional project_id query param
    const backendUrl = `${BACKEND_URL}/clusters/${encodeURIComponent(id)}/start_fix`;

    // If we had a project_id in the request url search params, pass it along
    // const { searchParams } = new URL(request.url);
    // const projectId = searchParams.get('project_id');
    // const url = projectId ? `${backendUrl}?project_id=${projectId}` : backendUrl;

    // For now, assuming default project / implicit context
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
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
  } catch (error) {
    console.error('Error starting fix:', error);
    return NextResponse.json({ error: 'Failed to start fix' }, { status: 500 });
  }
}
