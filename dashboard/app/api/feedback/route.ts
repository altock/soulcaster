import { NextRequest, NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Retrieve feedback entries for the project identified in the request.
 *
 * @returns A JSON response containing the feedback payload from Redis on success; a 400 JSON error when `limit` or `offset` are invalid or when the project ID is missing; or a 500 JSON error when fetching fails.
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const projectId = await requireProjectId(request);

    const source = searchParams.get('source');
    const repo = searchParams.get('repo');
    const limitParam = searchParams.get('limit') || '100';
    const offsetParam = searchParams.get('offset') || '0';

    // Parse and validate limit
    const limitNum = parseInt(limitParam, 10);
    if (isNaN(limitNum) || limitNum < 1) {
      return NextResponse.json(
        { error: 'Invalid limit: must be a positive integer' },
        { status: 400 }
      );
    }
    const limit = Math.min(Math.max(limitNum, 1), 100);

    // Parse and validate offset
    const offsetNum = parseInt(offsetParam, 10);
    if (isNaN(offsetNum) || offsetNum < 0) {
      return NextResponse.json(
        { error: 'Invalid offset: must be a non-negative integer' },
        { status: 400 }
      );
    }
    const offset = Math.max(offsetNum, 0);

    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (source) params.set('source', source);
    if (repo) params.set('repo', repo);

    const response = await fetch(`${backendUrl}/feedback?${params.toString()}`, {
      signal: AbortSignal.timeout(30000), // Increased timeout to 30s
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for feedback list`);
      const status = response.status >= 500 ? 502 : response.status;
      return NextResponse.json({ error: 'Failed to fetch feedback' }, { status });
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
    console.error('Error fetching feedback from backend:', error);
    return NextResponse.json({ error: 'Failed to fetch feedback' }, { status: 500 });
  }
}

/**
 * Update an existing feedback entry for the authorized project.
 *
 * Attempts to update feedback identified by `id` with the provided data for the project derived from the request.
 *
 * @returns A `NextResponse` containing `{ success: true }` on successful update. On failure returns a JSON error message with HTTP status 400 when the project ID or feedback `id` is missing, or 500 for other server errors.
 */
export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const projectId = await requireProjectId(request);

    const { id, ...data } = body;

    if (!id) {
      return NextResponse.json({ error: 'Feedback ID is required' }, { status: 400 });
    }

    const response = await fetch(`${backendUrl}/feedback/${id}?project_id=${projectId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      signal: AbortSignal.timeout(30000), // Increased timeout to 30s
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for feedback update ${id}`);
      const status = response.status >= 500 ? 502 : response.status;
      return NextResponse.json({ error: 'Failed to update feedback' }, { status });
    }
    const respJson = await response.json();
    return NextResponse.json(respJson, { status: response.status });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    if (error?.name === 'AbortError' || error?.message?.includes('timeout')) {
      return NextResponse.json({ error: 'Request timed out. Please try again.' }, { status: 503 });
    }
    console.error('Error updating feedback:', error);
    return NextResponse.json({ error: 'Failed to update feedback' }, { status: 500 });
  }
}