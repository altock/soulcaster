import { NextResponse } from 'next/server';
import { createDummyCheckoutSession, type BillingPlanId } from '@/lib/billing';

interface CheckoutRequestBody {
  planId?: BillingPlanId;
}

/**
 * Creates a dummy billing checkout session for the requested plan and returns session details.
 *
 * @param request - HTTP request whose JSON body may include `planId` (BillingPlanId). If omitted, `planId` defaults to `'pro'`.
 * @returns A JSON response: on success (`ok: true`) includes `mode`, `sessionId`, `planId`, and `url` with HTTP 200; on failure (`ok: false`) includes `error` with HTTP 400.
 */
export async function POST(request: Request) {
  try {
    const body = (await request.json()) as CheckoutRequestBody;

    const planId = body.planId ?? 'pro';

    const session = await createDummyCheckoutSession(planId);

    return NextResponse.json(
      {
        ok: true,
        mode: session.mode,
        sessionId: session.sessionId,
        planId: session.planId,
        url: session.url,
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
