import { NextResponse } from 'next/server';
import { getUnclusteredCount } from '@/lib/redis';

/**
 * Get count of unclustered feedback items
 * GET /api/clusters/unclustered
 */
export async function GET() {
  try {
    const count = await getUnclusteredCount();
    return NextResponse.json({ count });
  } catch (error) {
    console.error('Error fetching unclustered count:', error);
    return NextResponse.json(
      { error: 'Failed to fetch unclustered count' },
      { status: 500 }
    );
  }
}
