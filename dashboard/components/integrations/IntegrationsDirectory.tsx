'use client';

import { useEffect, useState } from 'react';
import IntegrationCard, { IntegrationConfig } from '@/components/settings/IntegrationCard';
import SearchInput from '@/components/ui/SearchInput';
import RequestIntegrationDialog from '@/components/integrations/RequestIntegrationDialog';
import { BACKEND_URL, DEFAULT_PAGE_SIZE, DEFAULT_PROJECT_ID, DEFAULT_REQUEST_HREF } from '@/lib/integrations';

export type IntegrationId = 'splunk' | 'datadog' | 'posthog' | 'sentry';

type IntegrationItem = {
  id: IntegrationId;
  config: IntegrationConfig;
  onSave: (data: Record<string, any>) => Promise<void>;
  onToggle: (enabled: boolean) => Promise<void>;
};

export interface IntegrationsDirectoryProps {
  integrationIds?: IntegrationId[];
  projectId?: string;
  pageSize?: number;
  requestHref?: string;
  showRequestButton?: boolean;
  showSearch?: boolean;
  showMeta?: boolean;
  showPagination?: boolean;
  className?: string;
}

function normalizeQuery(value: string) {
  return value.trim().toLowerCase();
}

function normalizeMultiSelectInput(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((entry) => String(entry).trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return [];
    return trimmed
      .split(',')
      .map((entry) => entry.trim())
      .filter(Boolean);
  }
  return [];
}

export default function IntegrationsDirectory({
  integrationIds,
  projectId,
  pageSize = DEFAULT_PAGE_SIZE,
  requestHref = DEFAULT_REQUEST_HREF,
  showRequestButton = true,
  showSearch = true,
  showMeta = true,
  showPagination = true,
  className = '',
}: IntegrationsDirectoryProps) {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const resolvedProjectId = projectId ?? DEFAULT_PROJECT_ID;

  // State for integration configs (loaded from backend)
  const [integrationConfigs, setIntegrationConfigs] = useState<Record<IntegrationId, IntegrationConfig>>({
    splunk: {
      name: 'Splunk',
      icon: '🔍',
      description: 'Monitor logs and trigger alerts via webhook',
      enabled: false,
      comingSoon: true,
      fields: [
        {
          id: 'webhook_token',
          label: 'Webhook Token',
          type: 'password',
          placeholder: 'Enter your webhook token',
          helpText: 'This token will be used to authenticate webhook requests',
          required: true,
        },
        {
          id: 'webhook_url',
          label: 'Webhook URL',
          type: 'text',
          placeholder: `${BACKEND_URL}/webhook/splunk`,
          helpText: 'Copy this URL to your Splunk webhook configuration',
          copyButton: true,
          readOnly: true,
        },
        {
          id: 'allowed_searches',
          label: 'Allowed Searches',
          type: 'textarea',
          placeholder: 'Enter allowed search names (one per line)',
          helpText: 'Only alerts from these saved searches will be processed',
        },
      ],
    },
    datadog: {
      name: 'Datadog',
      icon: '🐕',
      description: 'Receive monitor alerts and metrics',
      enabled: false,
      comingSoon: true,
      fields: [
        {
          id: 'webhook_secret',
          label: 'Webhook Secret (Optional)',
          type: 'password',
          placeholder: 'Enter webhook secret for validation',
          helpText: 'Leave empty to accept all webhook requests',
        },
        {
          id: 'allowed_monitors',
          label: 'Allowed Monitor IDs',
          type: 'multiselect',
          placeholder: 'Comma-separated monitor IDs, or "*" for all',
          defaultValue: '*',
          helpText: 'Use "*" to allow all monitors, or specify IDs like "123456,789012"',
        },
      ],
    },
    posthog: {
      name: 'PostHog',
      icon: '📊',
      description: 'Track product analytics events',
      enabled: false,
      comingSoon: true,
      fields: [
        {
          id: 'event_types',
          label: 'Event Types to Track',
          type: 'checkbox',
          options: ['$exception', '$error', 'custom_error'],
          defaultValue: ['$exception', '$error'],
          helpText: 'Select which event types should trigger feedback creation',
        },
      ],
    },
    sentry: {
      name: 'Sentry',
      icon: '⚠️',
      description: 'Capture errors and performance issues',
      enabled: false,
      comingSoon: true,
      fields: [
        {
          id: 'webhook_secret',
          label: 'Webhook Secret',
          type: 'password',
          placeholder: 'Enter your Sentry webhook secret',
          helpText: 'Found in Sentry project settings → Integrations → Webhooks',
          required: true,
        },
        {
          id: 'environments',
          label: 'Environments',
          type: 'checkbox',
          options: ['production', 'staging', 'development'],
          defaultValue: ['production'],
          helpText: 'Only issues from selected environments will be processed',
        },
        {
          id: 'levels',
          label: 'Severity Levels',
          type: 'checkbox',
          options: ['fatal', 'error', 'warning'],
          defaultValue: ['fatal', 'error'],
          helpText: 'Minimum severity level to capture',
        },
      ],
    },
  });

  // Load initial enabled states from backend
  useEffect(() => {
    const loadIntegrationStates = async () => {
      setIsLoading(true);
      try {
        const integrations: IntegrationId[] = ['splunk', 'datadog', 'posthog', 'sentry'];
        const results = await Promise.allSettled(
          integrations.map(async (integration) => {
            const res = await fetch(
              `${BACKEND_URL}/config/${integration}/enabled?project_id=${resolvedProjectId}`
            );
            if (res.ok) {
              const data = await res.json();
              return { integration, enabled: data.enabled };
            }
            return { integration, enabled: false };
          })
        );

        setIntegrationConfigs((prev) => {
          const updated = { ...prev };
          results.forEach((result) => {
            if (result.status === 'fulfilled') {
              const { integration, enabled } = result.value;
              if (updated[integration]) {
                updated[integration] = {
                  ...updated[integration],
                  enabled,
                };
              }
            }
          });
          return updated;
        });
      } catch (error) {
        console.error('Failed to load integration states:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadIntegrationStates();
  }, [resolvedProjectId]);

  // Toggle handlers for each integration
  const handleToggle =
    (integration: IntegrationId) =>
    async (enabled: boolean) => {
      const res = await fetch(
        `${BACKEND_URL}/config/${integration}/enabled?project_id=${resolvedProjectId}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled }),
        }
      );
      if (!res.ok) throw new Error(`Failed to update ${integration} status`);

      setIntegrationConfigs((prev) => ({
        ...prev,
        [integration]: { ...prev[integration], enabled },
      }));
    };

  // Save handlers for each integration
  const handleSplunkSave = async (data: Record<string, any>) => {
    const payload: { webhook_token?: string; allowed_searches?: string[] } = {};
    if (data.webhook_token !== undefined) {
      payload.webhook_token = data.webhook_token;
    }
    if (data.allowed_searches !== undefined) {
      payload.allowed_searches = data.allowed_searches
        .split('\n')
        .map((s: string) => s.trim())
        .filter(Boolean);
    }
    const res = await fetch(`${BACKEND_URL}/config/splunk?project_id=${resolvedProjectId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to save Splunk configuration');
  };

  const handleDatadogSave = async (data: Record<string, any>) => {
    // Save webhook secret
    if (data.webhook_secret) {
      const secretRes = await fetch(`${BACKEND_URL}/config/datadog/secret`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: resolvedProjectId,
          secret: data.webhook_secret,
        }),
      });
      if (!secretRes.ok) throw new Error('Failed to save webhook secret');
    }

    // Save allowed monitors
    if (data.allowed_monitors) {
      const monitors = normalizeMultiSelectInput(data.allowed_monitors);
      const monitorsRes = await fetch(`${BACKEND_URL}/config/datadog/monitors`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: resolvedProjectId,
          monitors,
        }),
      });
      if (!monitorsRes.ok) throw new Error('Failed to save allowed monitors');
    }
  };

  const handlePostHogSave = async (data: Record<string, any>) => {
    const eventsRes = await fetch(`${BACKEND_URL}/config/posthog/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: resolvedProjectId,
        event_types: data.event_types || [],
      }),
    });
    if (!eventsRes.ok) throw new Error('Failed to save event types');
  };

  const handleSentrySave = async (data: Record<string, any>) => {
    const payload: { webhook_secret?: string; environments?: string[]; levels?: string[] } = {};
    if (data.webhook_secret !== undefined) {
      payload.webhook_secret = data.webhook_secret;
    }
    if (data.environments !== undefined) {
      payload.environments = data.environments;
    }
    if (data.levels !== undefined) {
      payload.levels = data.levels;
    }
    const res = await fetch(`${BACKEND_URL}/config/sentry?project_id=${resolvedProjectId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to save Sentry configuration');
  };

  const integrations: IntegrationItem[] = [
    {
      id: 'splunk',
      config: integrationConfigs.splunk,
      onSave: handleSplunkSave,
      onToggle: handleToggle('splunk'),
    },
    {
      id: 'datadog',
      config: integrationConfigs.datadog,
      onSave: handleDatadogSave,
      onToggle: handleToggle('datadog'),
    },
    {
      id: 'posthog',
      config: integrationConfigs.posthog,
      onSave: handlePostHogSave,
      onToggle: handleToggle('posthog'),
    },
    {
      id: 'sentry',
      config: integrationConfigs.sentry,
      onSave: handleSentrySave,
      onToggle: handleToggle('sentry'),
    },
  ];

  const scopedIntegrations = integrationIds?.length
    ? integrations.filter((integration) => integrationIds.includes(integration.id))
    : integrations;

  const normalizedQuery = normalizeQuery(query);
  const filteredIntegrations =
    showSearch && normalizedQuery
      ? scopedIntegrations.filter(({ config }) => {
          const haystack = `${config.name} ${config.description}`.toLowerCase();
          return haystack.includes(normalizedQuery);
        })
      : scopedIntegrations;

  const totalCount = filteredIntegrations.length;
  const totalPages = showPagination ? Math.max(1, Math.ceil(totalCount / pageSize)) : 1;
  const currentPage = showPagination ? Math.min(page, totalPages - 1) : 0;
  const startIndex = currentPage * pageSize;
  const pageItems = showPagination
    ? filteredIntegrations.slice(startIndex, startIndex + pageSize)
    : filteredIntegrations;

  const requestIsExternal = requestHref.startsWith('http://') || requestHref.startsWith('https://');
  const showTopControls = showSearch || showRequestButton;
  const integrationsLabel = totalCount === 1 ? 'integration' : 'integrations';

  return (
    <div className={className}>
      {showTopControls && (
        <div
          className={`flex flex-col gap-3 sm:flex-row sm:items-center ${
            showSearch ? 'sm:justify-between' : 'sm:justify-end'
          }`}
        >
          {showSearch && (
            <SearchInput
              value={query}
              onChange={(nextQuery) => {
                setQuery(nextQuery);
                setPage(0);
              }}
              placeholder="Search integrations…"
              className="flex-1"
            />
          )}

          {showRequestButton && (
            <>
              {requestIsExternal ? (
                <a
                  href={requestHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/10 hover:text-white transition-colors"
                >
                  Other / Request integration
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 5v14" />
                    <path d="M5 12h14" />
                  </svg>
                </a>
              ) : (
                <RequestIntegrationDialog
                  requestHref={requestHref}
                  triggerTitle="Request a new integration"
                  triggerClassName="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/10 hover:text-white transition-colors"
                >
                  Other / Request integration
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 5v14" />
                    <path d="M5 12h14" />
                  </svg>
                </RequestIntegrationDialog>
              )}
            </>
          )}
        </div>
      )}

      {showMeta && (
        <div className={`${showTopControls ? 'mt-3' : ''} flex items-center justify-between text-xs text-slate-500`}>
          <span>
            {totalCount === scopedIntegrations.length
              ? `${totalCount} ${integrationsLabel}`
              : `${totalCount} matching ${integrationsLabel}`}
          </span>
          {showPagination && totalCount > pageSize && (
            <span>
              Page {currentPage + 1} of {totalPages}
            </span>
          )}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-8">
        {isLoading ? (
          <div className="col-span-full rounded-2xl border border-white/10 bg-white/5 p-8 text-center">
            <div className="flex items-center justify-center gap-3">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-400 border-t-transparent" />
              <p className="text-sm text-slate-300">Loading integrations...</p>
            </div>
          </div>
        ) : totalCount === 0 ? (
          <div className="col-span-full rounded-2xl border border-white/10 bg-white/5 p-8 text-center">
            <p className="text-sm text-slate-300">
              {showSearch && query.trim() ? `No integrations match "${query}".` : 'No integrations available.'}
            </p>
          </div>
        ) : (
          pageItems.map((integration) => (
            <IntegrationCard
              key={integration.id}
              config={integration.config}
              onSave={integration.onSave}
              onToggle={integration.onToggle}
            />
          ))
        )}
      </div>

      {showPagination && totalCount > pageSize && (
        <div className="mt-10 flex items-center justify-center gap-2">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={currentPage === 0}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
              currentPage === 0
                ? 'bg-white/5 text-slate-500 cursor-not-allowed'
                : 'bg-white/5 text-slate-200 hover:bg-white/10 hover:text-white'
            }`}
          >
            Previous
          </button>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={currentPage >= totalPages - 1}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
              currentPage >= totalPages - 1
                ? 'bg-white/5 text-slate-500 cursor-not-allowed'
                : 'bg-white/5 text-slate-200 hover:bg-white/10 hover:text-white'
            }`}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
