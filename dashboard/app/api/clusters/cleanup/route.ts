import { NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Cleanup duplicate clusters by proxying to backend
 * POST /api/clusters/cleanup
 */
export async function POST(request: Request) {
  try {
    const projectId = await requireProjectId(request);

    // Proxy to backend
    const response = await fetch(
      `${BACKEND_URL}/clusters/cleanup?project_id=${projectId}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        {
          success: false,
          error: errorData.detail || 'Backend cleanup failed',
        },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('[Cleanup] Error cleaning up clusters:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to cleanup duplicate clusters',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
