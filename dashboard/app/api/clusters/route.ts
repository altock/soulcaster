import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Fetch cluster data by proxying to the backend.
 *
 * @returns A JSON Response containing cluster data on success, or `{ error: 'Failed to fetch clusters' }` with HTTP status 500 on failure.
 */
export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/clusters`, {
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`);
    }

    const clusters = await response.json();
    return NextResponse.json(clusters);
  } catch (error) {
    console.error('Error fetching clusters from backend:', error);
    return NextResponse.json({ error: 'Failed to fetch clusters' }, { status: 500 });
  }
}
