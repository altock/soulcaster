import { NextResponse } from 'next/server';

const enabled = process.env.ENABLE_DASHBOARD_CLUSTERING === 'true';

/**
 * Handle POST requests to the dashboard clustering endpoint and always return a deprecation/disabled error.
 *
 * The JSON error message indicates either that dashboard clustering is deprecated (recommended backend endpoint)
 * or that vector clustering is disabled in the dashboard; the message chosen depends on the `ENABLE_DASHBOARD_CLUSTERING` flag.
 *
 * @returns A NextResponse containing a JSON error message and HTTP status 410 (Gone).
 */
export async function POST() {
  if (!enabled) {
    return NextResponse.json(
      {
        error: 'Dashboard clustering is deprecated. Use backend POST /cluster-jobs.',
      },
      { status: 410 }
    );
  }

  return NextResponse.json(
    {
      error: 'Vector clustering disabled in dashboard. Enable via ENABLE_DASHBOARD_CLUSTERING=true only for local testing.',
    },
    { status: 410 }
  );
}