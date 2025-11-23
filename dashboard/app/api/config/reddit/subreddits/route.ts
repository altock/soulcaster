import { NextResponse } from 'next/server';
import { getRedditSubreddits, setRedditSubreddits } from '@/lib/redis';

export async function GET() {
  try {
    const subreddits = await getRedditSubreddits();
    return NextResponse.json({ subreddits });
  } catch (error) {
    console.error('Error fetching Reddit subreddits from Redis:', error);
    return NextResponse.json({ error: 'Failed to fetch subreddits' }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const { subreddits } = payload;

    if (!Array.isArray(subreddits)) {
      return NextResponse.json({ error: 'subreddits must be an array' }, { status: 400 });
    }

    await setRedditSubreddits(subreddits);
    return NextResponse.json({ subreddits });
  } catch (error) {
    console.error('Error saving Reddit subreddits to Redis:', error);
    return NextResponse.json({ error: 'Failed to save subreddits' }, { status: 500 });
  }
}
