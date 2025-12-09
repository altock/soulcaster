export type BillingPlanId = 'free' | 'pro' | 'enterprise';

export interface BillingPlan {
  id: BillingPlanId;
  name: string;
  priceUsdPerMonth: number;
  description: string;
}

export interface CheckoutSession {
  sessionId: string;
  url: string;
  mode: 'dummy';
  planId: BillingPlanId;
}

export const BILLING_PLANS: BillingPlan[] = [
  {
    id: 'free',
    name: 'Free',
    priceUsdPerMonth: 0,
    description: 'Perfect for trying out Soulcaster with basic limits.',
  },
  {
    id: 'pro',
    name: 'Pro',
    priceUsdPerMonth: 29,
    description: 'For growing teams that want automated clustering and agent runs.',
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    priceUsdPerMonth: 99,
    description: 'Custom limits and priority support for serious production workloads.',
  },
];

/**
 * Retrieve the billing plan that matches the provided plan id.
 *
 * @param planId - The billing plan identifier to look up
 * @returns The matching billing plan if found, otherwise `undefined`
 */
export function getBillingPlan(planId: BillingPlanId): BillingPlan | undefined {
  return BILLING_PLANS.find((plan) => plan.id === planId);
}

/**
 * Creates a fake checkout session object for the specified billing plan.
 *
 * The session is synthetic (no external payment provider is contacted) and includes a redirect URL that simulates a successful checkout flow.
 *
 * @returns A `CheckoutSession` containing `sessionId`, `planId`, `mode` set to `'dummy'`, and a `url` pointing to a simulated success page with encoded query parameters.
 * @throws Error if `planId` does not correspond to a known billing plan.
 */
export async function createDummyCheckoutSession(planId: BillingPlanId): Promise<CheckoutSession> {
  const plan = getBillingPlan(planId);
  if (!plan) {
    throw new Error(`Unknown billing plan: ${planId}`);
  }

  const sessionId = `dummy_${planId}_${Date.now()}`;

  return {
    sessionId,
    planId,
    mode: 'dummy',
    url: `/billing/success?session_id=${encodeURIComponent(sessionId)}&plan=${encodeURIComponent(planId)}`,
  };
}
