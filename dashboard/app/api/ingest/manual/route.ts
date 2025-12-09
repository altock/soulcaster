import { NextRequest, NextResponse } from 'next/server';
import { createFeedback } from '@/lib/redis';
import { requireProjectId } from '@/lib/project';

/**
 * Handle POST requests that create a manual feedback entry, store it in Redis, and return the created feedback id.
 *
 * @returns On success, a JSON object with `success: true`, `feedback_id` (the created feedback identifier), and a user-facing `message`. On validation failure, a JSON error with `{ error: 'Text field is required' }` and HTTP 400. If the request is missing a project id, a JSON error `{ error: 'project_id is required' }` with HTTP 400. On unexpected failures, a JSON error `{ error: 'Failed to submit feedback' }` with HTTP 500.
 */
export async function POST(request: NextRequest) {
  try {
    const projectId = await requireProjectId(request);
    const body = await request.json();

    if (!body.text || typeof body.text !== 'string') {
      return NextResponse.json({ error: 'Text field is required' }, { status: 400 });
    }

    // Extract title (first line or first 80 chars)
    const lines = body.text.trim().split('\n');
    const title = lines[0].substring(0, 80) || 'Manual feedback';
    const bodyText = body.text;
    const githubRepoUrl = body.github_repo_url;

    // Write directly to Redis
    const feedbackId = await createFeedback({
      project_id: projectId,
      title,
      body: bodyText,
      github_repo_url: githubRepoUrl,
      source: 'manual',
      metadata: {
        submitted_at: new Date().toISOString(),
      },
    });

    return NextResponse.json({
      success: true,
      feedback_id: feedbackId,
      message: 'Feedback saved. Click "Run Clustering" to group it with similar issues.',
    });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    console.error('Error submitting feedback:', error);
    return NextResponse.json({ error: 'Failed to submit feedback' }, { status: 500 });
  }
}