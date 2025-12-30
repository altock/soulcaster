import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { createDummyCheckoutSession, type BillingPlanId } from '@/lib/billing';

interface CheckoutRequestBody {
  planId?: BillingPlanId;
  projectId?: string; // Optional: for project-specific billing in the future
}

/**
 * Creates a dummy billing checkout session for the requested plan and returns session details.
 *
 * Requires authentication.
 *
 * @param request - HTTP request whose JSON body may include `planId` (BillingPlanId). If omitted, `planId` defaults to `'pro'`.
 * @returns A JSON response: on success (`ok: true`) includes `mode`, `sessionId`, `planId`, and `url` with HTTP 200; on failure (`ok: false`) includes `error` with HTTP 400.
 */
export async function POST(request: Request) {
  try {
    // Check authentication
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json(
        { ok: false, error: 'Unauthorized' },
        { status: 401 }
      );
    }

    const body = (await request.json()) as CheckoutRequestBody;

    const planId = body.planId ?? 'pro';

    // Note: Currently billing is per-account, not per-project
    // The projectId can be stored in the checkout session metadata for future use
    const checkoutSession = await createDummyCheckoutSession(planId);

    return NextResponse.json(
      {
        ok: true,
        mode: checkoutSession.mode,
        sessionId: checkoutSession.sessionId,
        planId: checkoutSession.planId,
        url: checkoutSession.url,
      },
      { status: 200 }
    );
  } catch (error) {
    console.error('[Billing] Failed to create dummy checkout session', error);

    return NextResponse.json(
      {
        ok: false,
        error: 'Failed to create checkout session',
      },
      { status: 400 }
    );
  }
}
