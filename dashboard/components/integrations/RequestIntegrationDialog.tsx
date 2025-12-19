'use client';

import type { ReactNode } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

const DEFAULT_SUPPORT_EMAIL = 'support@soulcaster.dev';
const DEFAULT_SUBJECT = 'Integration / Source Request';

function buildMailtoHref({
  supportEmail,
  subject,
  body,
}: {
  supportEmail: string;
  subject: string;
  body: string;
}) {
  const params = new URLSearchParams();
  params.set('subject', subject);
  params.set('body', body);
  return `mailto:${supportEmail}?${params.toString()}`;
}

function parseMailtoHref(href: string): { supportEmail: string; subject?: string } | null {
  if (!href.startsWith('mailto:')) return null;

  const withoutScheme = href.slice('mailto:'.length);
  const [emailPart, queryPart] = withoutScheme.split('?');
  const params = new URLSearchParams(queryPart ?? '');

  return {
    supportEmail: emailPart || DEFAULT_SUPPORT_EMAIL,
    subject: params.get('subject') || undefined,
  };
}

export interface RequestIntegrationDialogProps {
  children: ReactNode;
  triggerClassName?: string;
  triggerTitle?: string;
  requestHref?: string;
  subject?: string;
  supportEmail?: string;
  defaultName?: string;
}

export default function RequestIntegrationDialog({
  children,
  triggerClassName = '',
  triggerTitle,
  requestHref,
  subject,
  supportEmail,
  defaultName = '',
}: RequestIntegrationDialogProps) {
  const parsedMailto = requestHref ? parseMailtoHref(requestHref) : null;
  const resolvedSupportEmail = supportEmail ?? parsedMailto?.supportEmail ?? DEFAULT_SUPPORT_EMAIL;
  const resolvedSubject = subject ?? parsedMailto?.subject ?? DEFAULT_SUBJECT;

  const [open, setOpen] = useState(false);
  const [name, setName] = useState(defaultName);
  const [details, setDetails] = useState('');
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [portalRoot] = useState<HTMLElement | null>(() =>
    typeof document !== 'undefined' ? document.body : null
  );
  const nameInputRef = useRef<HTMLInputElement | null>(null);

  const requestBody = useMemo(() => {
    const lines = [
      'Hi Soulcaster team,',
      '',
      "I'd like to request a new integration/source.",
      '',
      `Name: ${name.trim() || '[fill in]'}`,
      '',
      'Details:',
      details.trim() || '[add details]',
      '',
      typeof window !== 'undefined' ? `Sent from: ${window.location.href}` : undefined,
    ].filter(Boolean);

    return lines.join('\n');
  }, [details, name]);

  const mailtoHref = useMemo(
    () =>
      buildMailtoHref({
        supportEmail: resolvedSupportEmail,
        subject: resolvedSubject,
        body: requestBody,
      }),
    [requestBody, resolvedSubject, resolvedSupportEmail]
  );

  useEffect(() => {
    if (!open) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('keydown', handleKeyDown);
    queueMicrotask(() => nameInputRef.current?.focus());

    return () => {
      document.body.style.overflow = originalOverflow;
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(requestBody);
      setCopyState('copied');
    } catch (err) {
      console.error('Failed to copy request:', err);
      setCopyState('failed');
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setName(defaultName);
          setDetails('');
          setCopyState('idle');
          setOpen(true);
        }}
        className={triggerClassName}
        title={triggerTitle}
      >
        {children}
      </button>

      {open && portalRoot && createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            aria-label="Close request dialog"
            onClick={() => setOpen(false)}
          />

          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="request-dialog-title"
            className="relative w-full max-w-lg rounded-2xl border border-white/10 bg-gradient-to-br from-black/80 via-black/70 to-black/80 p-6 shadow-[0_0_40px_rgba(0,0,0,0.6)] backdrop-blur-md"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent rounded-2xl pointer-events-none" />

            <div className="relative z-10 flex items-start justify-between gap-4">
              <div>
                <h3 id="request-dialog-title" className="text-base font-semibold text-white">Request a new integration/source</h3>
                <p className="mt-1 text-sm text-slate-400">
                  We’ll use this to prioritize what to build next. You can copy the request or email it to{' '}
                  <span className="text-slate-200">{resolvedSupportEmail}</span>.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-sm text-slate-300 hover:bg-white/10 hover:text-white transition-colors"
                aria-label="Close dialog"
              >
                ✕
              </button>
            </div>

            <div className="relative z-10 mt-5 space-y-4">
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-200" htmlFor="request-integration-name">
                  Integration/source name
                </label>
                <input
                  ref={nameInputRef}
                  id="request-integration-name"
                  type="text"
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                    setCopyState('idle');
                  }}
                  placeholder="e.g. Linear, Zendesk, PagerDuty…"
                  className="w-full px-4 py-2.5 bg-black/40 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all"
                />
              </div>

              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-200" htmlFor="request-integration-details">
                  What should this integration/source do?
                </label>
                <textarea
                  id="request-integration-details"
                  value={details}
                  onChange={(event) => {
                    setDetails(event.target.value);
                    setCopyState('idle');
                  }}
                  placeholder="What data should we ingest? Any auth/webhook details? What problem does it solve?"
                  rows={5}
                  className="w-full px-4 py-2.5 bg-black/40 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all resize-none"
                />
              </div>

              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-xs text-slate-400">Preview</p>
                <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap text-xs text-slate-200">
                  {requestBody}
                </pre>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                <button
                  type="button"
                  onClick={copyToClipboard}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-200 hover:bg-emerald-500/15 hover:text-emerald-100 transition-colors"
                >
                  {copyState === 'copied' ? 'Copied' : 'Copy request'}
                </button>
                <a
                  href={mailtoHref}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/10 hover:text-white transition-colors"
                >
                  Email support
                </a>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-transparent px-4 py-2.5 text-sm font-medium text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-colors"
                >
                  Cancel
                </button>
              </div>

              {copyState === 'failed' && (
                <p className="text-xs text-rose-300">
                  Copy failed (browser restrictions). Select the preview text and copy manually, or click “Email
                  support”.
                </p>
              )}
            </div>
          </div>
        </div>,
        portalRoot
      )}
    </>
  );
}
