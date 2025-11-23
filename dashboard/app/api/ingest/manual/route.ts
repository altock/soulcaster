import { NextRequest, NextResponse } from 'next/server';
import { createFeedback } from '@/lib/redis';

export async function POST(request: NextRequest) {
  try {
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
  } catch (error) {
    console.error('Error submitting feedback:', error);
    return NextResponse.json({ error: 'Failed to submit feedback' }, { status: 500 });
  }
}
