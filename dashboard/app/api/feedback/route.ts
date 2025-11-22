import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const source = searchParams.get('source');
    const limit = searchParams.get('limit') || '100';
    const offset = searchParams.get('offset') || '0';

    // Build query string
    const queryParams = new URLSearchParams({
      limit,
      offset,
    });
    if (source) {
      queryParams.append('source', source);
    }

    const response = await fetch(`${BACKEND_URL}/feedback?${queryParams}`, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching feedback:', error);
    return NextResponse.json(
      { error: 'Failed to fetch feedback' },
      { status: 500 }
    );
  }
}
