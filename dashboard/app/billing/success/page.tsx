import { redirect } from 'next/navigation';

interface BillingSuccessPageProps {
  searchParams?: Record<string, string | string[] | undefined>;
}

/**
 * Render a billing success UI for a completed dummy Stripe checkout.
 *
 * Redirects to `/billing` if `searchParams.session_id` is missing or not a string.
 *
 * @param searchParams - Optional query parameters; the component reads `session_id` and `plan` when they are strings.
 * @returns A React element showing a success message, the session ID, and the optional plan label when provided.
 */
export default function BillingSuccessPage({ searchParams }: BillingSuccessPageProps) {
  const sessionId = typeof searchParams?.session_id === 'string' ? searchParams.session_id : '';
  const plan = typeof searchParams?.plan === 'string' ? searchParams.plan : '';

  if (!sessionId) {
    redirect('/billing');
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-16 text-center">
      <h1 className="text-3xl font-semibold mb-4">Dummy checkout complete</h1>
      <p className="text-slate-400 mb-6">
        You just completed a <span className="font-semibold text-emerald-300">dummy Stripe</span> checkout flow.
        No real payment was processed.
      </p>
      <div className="rounded-xl border border-white/10 bg-black/40 px-6 py-5 text-left text-sm text-slate-300 space-y-2">
        <div>
          <span className="font-medium text-slate-200">Session ID:</span>{' '}
          <span className="font-mono text-xs text-slate-400 break-all">{sessionId}</span>
        </div>
        {plan && (
          <div>
            <span className="font-medium text-slate-200">Plan:</span>{' '}
            <span className="uppercase tracking-wide text-emerald-300 text-xs">{plan}</span>
          </div>
        )}
      </div>

      <p className="mt-8 text-xs text-slate-500">
        When you are ready to go live, swap the dummy checkout in <code>lib/billing.ts</code> for a real Stripe
        integration and update the API route to call it.
      </p>
    </div>
  );
}
