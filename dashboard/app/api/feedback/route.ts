import { NextRequest, NextResponse } from 'next/server';
import { getFeedback } from '@/lib/redis';
import { getProjectId } from '@/lib/project';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const projectId = await getProjectId(request);
    
    if (!projectId) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
    }

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

    // Fetch from Redis
    const data = await getFeedback(projectId, limit, offset, source || undefined, repo || undefined);
    return NextResponse.json(data);
  } catch (error: any) {
    console.error('Error fetching feedback from Redis:', error);
    return NextResponse.json({ error: 'Failed to fetch feedback' }, { status: 500 });
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const projectId = await getProjectId(request);
    
    if (!projectId) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
    }

    const { id, ...data } = body;

    if (!id) {
      return NextResponse.json({ error: 'Feedback ID is required' }, { status: 400 });
    }

    // Import dynamically to avoid circular dependencies if any, though not expected here
    const { updateFeedback } = await import('@/lib/redis');

    await updateFeedback(projectId, id, data);

    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('Error updating feedback:', error);
    return NextResponse.json({ error: 'Failed to update feedback' }, { status: 500 });
  }
}
