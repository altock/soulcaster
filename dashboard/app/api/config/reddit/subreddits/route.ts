import { NextResponse } from 'next/server';
import { getRedditSubreddits, setRedditSubreddits } from '@/lib/redis';
import { requireProjectId } from '@/lib/project';

export async function GET(request: Request) {
  try {
    const projectId = requireProjectId(request);
    const subreddits = await getRedditSubreddits(projectId);
    return NextResponse.json({ subreddits });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('Error fetching Reddit subreddits from Redis:', error);
    return NextResponse.json({ error: 'Failed to fetch subreddits' }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const projectId = requireProjectId(request);
    const payload = await request.json();
    const { subreddits } = payload;

    if (!Array.isArray(subreddits)) {
      return NextResponse.json({ error: 'subreddits must be an array' }, { status: 400 });
    }

    await setRedditSubreddits(projectId, subreddits);
    return NextResponse.json({ subreddits });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('Error saving Reddit subreddits to Redis:', error);
    return NextResponse.json({ error: 'Failed to save subreddits' }, { status: 500 });
  }
}
