'use client';

import { useState } from 'react';
import type { BillingPlanId } from '@/lib/billing';
import { BILLING_PLANS } from '@/lib/billing';

/**
 * Render the billing page with plan cards and a dummy Stripe checkout flow.
 *
 * The component displays available billing plans, an optional error banner, and a checkout button for each plan
 * that initiates a POST to /api/billing/checkout and redirects to the returned URL on success.
 *
 * @returns A JSX element containing the billing UI (plan cards, error banner, and checkout buttons).
 */
export default function BillingPage() {
  const [loadingPlan, setLoadingPlan] = useState<BillingPlanId | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleCheckout(planId: BillingPlanId) {
    try {
      setError(null);
      setLoadingPlan(planId);

      const response = await fetch('/api/billing/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ planId }),
      });

      const data = await response.json();

      if (!response.ok || !data?.ok || !data?.url) {
        throw new Error(data?.error || 'Failed to start checkout');
      }

      window.location.href = data.url as string;
    } catch (err) {
      console.error(err);
      setError('Failed to start checkout. This is a dummy Stripe flow, so no real payment was attempted.');
      setLoadingPlan(null);
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-12">
      <h1 className="text-3xl font-semibold mb-2">Billing</h1>
      <p className="text-slate-400 mb-8">
        This uses a <span className="font-semibold text-emerald-300">dummy Stripe checkout</span> so you can test the
        flow without real payments. No cards are charged.
      </p>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {BILLING_PLANS.map((plan) => (
          <div
            key={plan.id}
            className="rounded-2xl border border-white/10 bg-black/40 p-6 flex flex-col justify-between shadow-[0_0_20px_rgba(16,185,129,0.08)]"
          >
            <div>
              <h2 className="text-xl font-semibold mb-2">{plan.name}</h2>
              <p className="text-sm text-slate-400 mb-4">{plan.description}</p>
              <p className="text-3xl font-bold">
                {plan.priceUsdPerMonth === 0 ? (
                  <span className="text-emerald-300">Free</span>
                ) : (
                  <>
                    <span className="text-emerald-300">${plan.priceUsdPerMonth}</span>
                    <span className="text-base text-slate-400 font-normal"> / month</span>
                  </>
                )}
              </p>
            </div>

            <button
              type="button"
              onClick={() => handleCheckout(plan.id)}
              disabled={loadingPlan === plan.id}
              className="mt-6 inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-medium text-black bg-emerald-400 hover:bg-emerald-300 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {loadingPlan === plan.id ? 'Starting dummy checkout…' : 'Start dummy Stripe checkout'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
