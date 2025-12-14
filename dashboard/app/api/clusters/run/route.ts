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
      error: 'Dashboard clustering disabled by default. Set ENABLE_DASHBOARD_CLUSTERING=true for dev-only use.',
    },
    { status: 410 }
  );
}