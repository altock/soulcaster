import { BILLING_PLANS, createDummyCheckoutSession, getBillingPlan } from '@/lib/billing';

describe('Billing helpers (dummy Stripe)', () => {
  it('should expose the default billing plans', () => {
    const ids = BILLING_PLANS.map((p) => p.id);
    expect(ids).toContain('free');
    expect(ids).toContain('pro');
    expect(ids).toContain('enterprise');
  });

  it('should resolve a billing plan by id', () => {
    const plan = getBillingPlan('pro');
    expect(plan).toBeDefined();
    expect(plan?.id).toBe('pro');
  });

  it('should throw for unknown plan ids', async () => {
    // @ts-expect-error Testing runtime validation
    await expect(createDummyCheckoutSession('unknown-plan')).rejects.toThrow('Unknown billing plan');
  });

  it('should create a dummy checkout session with a success URL', async () => {
    const session = await createDummyCheckoutSession('pro');
    expect(session.mode).toBe('dummy');
    expect(session.planId).toBe('pro');
    expect(session.url).toContain('/billing/success');
    expect(session.url).toContain('session_id=');
  });
});
