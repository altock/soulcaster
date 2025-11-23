import { NextResponse } from 'next/server';
import { getClusters } from '@/lib/redis';

/**
 * Fetch cluster data directly from Redis.
 *
 * @returns A JSON Response containing cluster data on success, or `{ error: 'Failed to fetch clusters' }` with HTTP status 500 on failure.
 */
export async function GET() {
  try {
    const clusters = await getClusters();
    return NextResponse.json(clusters);
  } catch (error) {
    console.error('Error fetching clusters from Redis:', error);
    return NextResponse.json({ error: 'Failed to fetch clusters' }, { status: 500 });
  }
}
