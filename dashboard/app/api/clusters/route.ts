import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Proxy GET requests to fetch cluster data from the configured backend.
 *
 * @returns A JSON Response containing the backend's cluster data on success, or `{ error: 'Failed to fetch clusters' }` with HTTP status 500 on failure.
 */
export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/clusters`, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching clusters:', error);
    return NextResponse.json(
      { error: 'Failed to fetch clusters' },
      { status: 500 }
    );
  }
}