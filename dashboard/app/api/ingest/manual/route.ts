import { NextRequest, NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

/**
 * Proxy manual ingestion to the backend API.
 *
 * Backend owns writes to storage; this route forwards the payload.
 */
export async function POST(request: NextRequest) {
  try {
    const projectId = await requireProjectId(request);
    const body = await request.json();

    if (!body.text || typeof body.text !== 'string') {
      return NextResponse.json({ error: 'Text field is required' }, { status: 400 });
    }

    const response = await fetch(`${backendUrl}/ingest/manual?project_id=${projectId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: body.text,
        github_repo_url: body.github_repo_url,
      }),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('Error submitting feedback:', error);
    return NextResponse.json({ error: 'Failed to submit feedback' }, { status: 500 });
  }
}