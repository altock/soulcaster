import { NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

function backendError(status: number) {
  return status >= 500 ? 502 : status;
}

export async function GET(request: Request) {
  try {
    const projectId = await requireProjectId(request);
    const response = await fetch(`${backendUrl}/jobs?project_id=${projectId}`, {
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for jobs GET`);
      return NextResponse.json({ error: 'Failed to fetch jobs' }, { status: backendError(response.status) });
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
    console.error('Error fetching jobs:', error);
    return NextResponse.json({ error: 'Failed to fetch jobs' }, { status: 500 });
  }
}

