import { NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Fetches stored Reddit subreddits for the project identified in the incoming request.
 *
 * @returns A JSON response containing `{ subreddits }` on success; if the request lacks a project ID returns `{ error: 'project_id is required' }` with status 400, otherwise returns `{ error: 'Failed to fetch subreddits' }` with status 500.
 */
export async function GET(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    const response = await fetch(`${backendUrl}/config/reddit/subreddits?project_id=${projectId}`, {
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for reddit subreddits GET`);
      const status = response.status >= 500 ? 502 : response.status;
      return NextResponse.json({ error: 'Failed to fetch subreddits' }, { status });
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
    console.error('Error fetching Reddit subreddits from backend:', error);
    return NextResponse.json({ error: 'Failed to fetch subreddits' }, { status: 500 });
  }
}

/**
 * Persist Reddit subreddit list for the current project and return the saved list.
 *
 * Accepts an HTTP request whose body is JSON containing a `subreddits` array and whose project context is resolvable by `requireProjectId`.
 *
 * @param request - The incoming HTTP request (JSON body must include `subreddits` array; project identification must be available to `requireProjectId`)
 * @returns A JSON response with `{ subreddits }` on success, or `{ error }` with an appropriate HTTP status on failure
 */
export async function POST(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    const payload = await request.json();
    const { subreddits } = payload;

    if (!Array.isArray(subreddits)) {
      return NextResponse.json({ error: 'subreddits must be an array' }, { status: 400 });
    }

    const response = await fetch(`${backendUrl}/config/reddit/subreddits?project_id=${projectId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subreddits }),
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for reddit subreddits POST`);
      const status = response.status >= 500 ? 502 : response.status;
      return NextResponse.json({ error: 'Failed to save subreddits' }, { status });
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
    console.error('Error saving Reddit subreddits to backend:', error);
    return NextResponse.json({ error: 'Failed to save subreddits' }, { status: 500 });
  }
}