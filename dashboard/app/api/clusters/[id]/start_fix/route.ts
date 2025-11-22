import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Initiates a fix operation for the cluster specified by the route `id` by proxying a POST to the backend.
 *
 * @param params - Promise resolving to route parameters; must include `id`, the cluster identifier.
 * @returns The backend's JSON response when the fix is started; on failure returns an error object `{ error: 'Failed to start fix' }` with HTTP status 500.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const response = await fetch(`${BACKEND_URL}/clusters/${id}/start_fix`, {
      method: 'POST',
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
    console.error('Error starting fix:', error);
    return NextResponse.json(
      { error: 'Failed to start fix' },
      { status: 500 }
    );
  }
}