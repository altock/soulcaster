import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

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
    const limit = Math.min(Math.max(limitNum, 1), 100).toString();

    // Parse and validate offset
    const offsetNum = parseInt(offsetParam, 10);
    if (isNaN(offsetNum) || offsetNum < 0) {
      return NextResponse.json(
        { error: 'Invalid offset: must be a non-negative integer' },
        { status: 400 }
      );
    }
    const offset = Math.max(offsetNum, 0).toString();

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
