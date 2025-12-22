import { NextResponse } from 'next/server';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Proxy the trigger-poll request to the backend.
 *
 * This allows client components to trigger the Reddit poller without
 * exposing the backend URL or dealing with CORS issues.
 */
export async function POST() {
  try {
    const response = await fetch(`${backendUrl}/admin/trigger-poll`, {
      method: 'POST',
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for trigger-poll POST`);
      const status = response.status >= 500 ? 502 : response.status;
      return NextResponse.json({ error: 'Failed to trigger poll' }, { status });
    }
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    if (error?.name === 'AbortError' || error?.message?.includes('timeout')) {
      return NextResponse.json({ error: 'Request timed out. Please try again.' }, { status: 503 });
    }
    console.error('Error triggering poll:', error);
    return NextResponse.json(
      { error: 'Failed to trigger poll' },
      { status: 500 }
    );
  }
}
