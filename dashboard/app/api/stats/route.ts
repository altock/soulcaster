import { NextResponse } from 'next/server';
import { getStats } from '@/lib/redis';
import { requireProjectId } from '@/lib/project';

export async function GET(request: Request) {
  try {
    const projectId = requireProjectId(request);
    const stats = await getStats(projectId);
    return NextResponse.json(stats);
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('Error fetching stats from Redis:', error);
    return NextResponse.json({ error: 'Failed to fetch stats' }, { status: 500 });
  }
}
