import { NextRequest, NextResponse } from 'next/server';
import { getFeedback } from '@/lib/redis';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const source = searchParams.get('source');
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
    const data = await getFeedback(limit, offset, source || undefined);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching feedback from Redis:', error);
    return NextResponse.json({ error: 'Failed to fetch feedback' }, { status: 500 });
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, ...data } = body;

    if (!id) {
      return NextResponse.json({ error: 'Feedback ID is required' }, { status: 400 });
    }

    // Import dynamically to avoid circular dependencies if any, though not expected here
    const { updateFeedback } = await import('@/lib/redis');

    await updateFeedback(id, data);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error updating feedback:', error);
    return NextResponse.json({ error: 'Failed to update feedback' }, { status: 500 });
  }
}
