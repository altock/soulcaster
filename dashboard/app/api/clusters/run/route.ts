import { NextResponse } from 'next/server';

const enabled = process.env.ENABLE_DASHBOARD_CLUSTERING === 'true';

/**
 * Handle POST requests to the dashboard clustering route and return a deprecation or dev-only guidance response.
 *
 * @returns A NextResponse with HTTP status 410 and a JSON body containing an `error` message; the message either indicates that dashboard clustering is deprecated and points to the backend `/cluster-jobs` endpoint, or explains that dashboard clustering is disabled by default and how to enable it for development.
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
      error: 'Dashboard clustering disabled by default. Set ENABLE_DASHBOARD_CLUSTERING=true for dev-only use.',
    },
    { status: 410 }
  );
}