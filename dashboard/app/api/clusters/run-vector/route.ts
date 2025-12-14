import { NextResponse } from 'next/server';

const enabled = process.env.ENABLE_DASHBOARD_CLUSTERING === 'true';

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