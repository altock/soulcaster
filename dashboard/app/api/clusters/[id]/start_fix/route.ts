import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Initiates a fix operation for the cluster specified by the route `id` by proxying a POST to the backend.
 *
 * @param params - Promise resolving to route parameters; must include `id`, the cluster identifier.
 * @returns The backend's JSON response when the fix is started; on failure returns an error object `{ error: 'Failed to start fix' }` with HTTP status 500.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;

    // Validate ID format (UUID or numeric)
    if (!id || !/^[a-zA-Z0-9-]+$/.test(id)) {
      return NextResponse.json({ error: 'Invalid cluster ID' }, { status: 400 });
    }

    const response = await fetch(`${BACKEND_URL}/clusters/${encodeURIComponent(id)}/start_fix`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`);
    }

    // Fetch cluster details to get context
    const clusterResponse = await fetch(`${BACKEND_URL}/clusters/${encodeURIComponent(id)}`);
    if (!clusterResponse.ok) {
       console.warn('Failed to fetch cluster details for context');
    }
    const clusterData = clusterResponse.ok ? await clusterResponse.json() : null;

    // Determine repo based on cluster data
    let repoOwner = process.env.GITHUB_OWNER;
    let repoName = process.env.GITHUB_REPO;

    if (clusterData && clusterData.feedback_items) {
      const hasManualFeedback = clusterData.feedback_items.some(
        (item: any) => item.source === 'manual'
      );
      if (hasManualFeedback) {
        repoOwner = 'naga-k';
        repoName = 'bad-ux-mart';
      }
    }

    // Trigger the agent
    try {
        const protocol = request.headers.get('x-forwarded-proto') || 'http';
        const host = request.headers.get('host');
        const triggerUrl = `${protocol}://${host}/api/trigger-agent`;

        console.log(`Triggering agent at ${triggerUrl} for ${repoOwner}/${repoName}`);
        
        // We don't await the result of the trigger to return quickly to the UI?
        // Actually, better to await to report errors.
        const triggerResponse = await fetch(triggerUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                issue_url: clusterData?.github_pr_url || undefined,
                context: clusterData?.summary || `Fix for cluster ${id}`,
                issue_title: clusterData?.title,
                owner: repoOwner,
                repo: repoName,
            })
        });

        if (!triggerResponse.ok) {
            const errorText = await triggerResponse.text();
            console.error('Failed to trigger agent:', errorText);
            // We still return success for the "start_fix" operation as the status was updated
        } else {
            const triggerData = await triggerResponse.json();
            console.log('Agent triggered successfully:', triggerData);
        }
    } catch (triggerError) {
        console.error('Error calling trigger-agent:', triggerError);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error starting fix:', error);
    return NextResponse.json({ error: 'Failed to start fix' }, { status: 500 });
  }
}
