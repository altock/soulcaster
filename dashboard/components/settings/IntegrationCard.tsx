'use client';

import { useState, useEffect } from 'react';

export interface IntegrationConfig {
  name: string;
  icon: string;
  description: string;
  fields: IntegrationField[];
  enabled?: boolean;
}

export interface IntegrationField {
  id: string;
  label: string;
  type: 'text' | 'password' | 'textarea' | 'checkbox' | 'multiselect';
  placeholder?: string;
  options?: string[];
  defaultValue?: any;
  helpText?: string;
  copyButton?: boolean;
  webhookUrl?: string;
  required?: boolean;
  readOnly?: boolean;
}

export interface IntegrationCardProps {
  config: IntegrationConfig;
  onSave: (data: Record<string, any>) => Promise<void>;
  onToggle?: (enabled: boolean) => Promise<void>;
}

export default function IntegrationCard({ config, onSave, onToggle }: IntegrationCardProps) {
  const [formData, setFormData] = useState<Record<string, any>>(() => {
    const initial: Record<string, any> = {};
    config.fields.forEach((field) => {
      if (field.type === 'checkbox') {
        initial[field.id] = field.defaultValue || [];
      } else if (field.type === 'multiselect') {
        if (Array.isArray(field.defaultValue)) {
          initial[field.id] = field.defaultValue;
        } else if (typeof field.defaultValue === 'string') {
          initial[field.id] = field.defaultValue
            .split(',')
            .map((value) => value.trim())
            .filter(Boolean);
        } else {
          initial[field.id] = [];
        }
      } else {
        initial[field.id] = field.defaultValue || '';
      }
    });
    return initial;
  });

  const [enabled, setEnabled] = useState(config.enabled ?? true);
  const [toggleLoading, setToggleLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState<string | null>(null);
  const [multiSelectInputs, setMultiSelectInputs] = useState<Record<string, string>>({});

  // Sync enabled state when config.enabled changes
  useEffect(() => {
    setEnabled(config.enabled ?? true);
  }, [config.enabled]);

  const handleCheckboxChange = (fieldId: string, value: string, checked: boolean) => {
    setFormData((prev) => {
      const current = prev[fieldId] || [];
      if (checked) {
        return { ...prev, [fieldId]: [...current, value] };
      }
      return { ...prev, [fieldId]: current.filter((v: string) => v !== value) };
    });
  };

  const addMultiSelectValues = (fieldId: string, rawValue: string) => {
    const nextValues = rawValue
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);
    if (!nextValues.length) return;

    setFormData((prev) => {
      const current = Array.isArray(prev[fieldId]) ? prev[fieldId] : [];
      const combined = [...current, ...nextValues];
      const normalized = combined.map((value) => value.trim()).filter(Boolean);
      if (normalized.includes('*')) {
        return { ...prev, [fieldId]: ['*'] };
      }
      const deduped: string[] = [];
      const seen = new Set<string>();
      normalized.forEach((value) => {
        if (!seen.has(value)) {
          seen.add(value);
          deduped.push(value);
        }
      });
      return { ...prev, [fieldId]: deduped };
    });

    setMultiSelectInputs((prev) => ({ ...prev, [fieldId]: '' }));
  };

  const removeMultiSelectValue = (fieldId: string, value: string) => {
    setFormData((prev) => {
      const current = Array.isArray(prev[fieldId]) ? prev[fieldId] : [];
      return { ...prev, [fieldId]: current.filter((entry: string) => entry !== value) };
    });
  };

  const handleToggle = async () => {
    if (!onToggle) return;

    const newEnabledState = !enabled;
    setToggleLoading(true);

    try {
      await onToggle(newEnabledState);
      setEnabled(newEnabledState);
    } catch (error: any) {
      setMessage({ type: 'error', text: error.message || 'Failed to toggle integration' });
    } finally {
      setToggleLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    try {
      await onSave(formData);
      setMessage({ type: 'success', text: `${config.name} settings saved successfully` });
    } catch (error: any) {
      setMessage({ type: 'error', text: error.message || 'Failed to save settings' });
    } finally {
      setLoading(false);
    }
  };

  // Auto-dismiss success messages after 3 seconds
  useEffect(() => {
    if (message?.type === 'success') {
      const timer = setTimeout(() => {
        setMessage(null);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  const copyToClipboard = async (text: string, fieldId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(fieldId);
      setTimeout(() => setCopied(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="group relative bg-gradient-to-br from-black/40 via-black/20 to-black/40 border border-white/10 rounded-2xl p-6 backdrop-blur-sm hover:border-emerald-500/30 transition-all duration-300 hover:shadow-[0_0_30px_rgba(16,185,129,0.1)]">
      {/* Subtle glow effect */}
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl pointer-events-none" />

      {/* Header */}
      <div className="relative z-10 flex items-start justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500/20 to-emerald-500/5 border border-emerald-500/20 flex items-center justify-center text-2xl group-hover:shadow-[0_0_20px_rgba(16,185,129,0.2)] transition-shadow">
            {config.icon}
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white group-hover:text-emerald-300 transition-colors">
              {config.name}
            </h3>
            <p className="text-sm text-slate-400 mt-0.5">{config.description}</p>
          </div>
        </div>

        {/* Enable/Disable Toggle */}
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label={`Enable/disable ${config.name} integration`}
          disabled={toggleLoading}
          className={`relative w-11 h-6 rounded-full transition-all ${
            enabled
              ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]'
              : 'bg-white/10'
          } ${toggleLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
          onClick={handleToggle}
        >
          <div
            className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform flex items-center justify-center ${
              enabled ? 'translate-x-5' : 'translate-x-0'
            }`}
          >
            {toggleLoading && (
              <svg className="animate-spin h-3 w-3 text-slate-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            )}
          </div>
        </button>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="relative z-10 space-y-4">
        {config.fields.map((field) => (
          <div key={field.id} className="space-y-2">
            <label htmlFor={field.id} className="block text-sm font-medium text-slate-200">
              {field.label}
              {field.required && <span className="text-rose-400 ml-1">*</span>}
            </label>

            {field.type === 'text' && (
              <div className="relative">
                <input
                  id={field.id}
                  type="text"
                  value={formData[field.id] ?? ''}
                  onChange={(e) => setFormData({ ...formData, [field.id]: e.target.value })}
                  placeholder={field.placeholder}
                  readOnly={field.readOnly}
                  className={`w-full px-4 py-2.5 bg-black/40 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all ${
                    field.readOnly ? 'cursor-default font-mono text-sm pr-12' : ''
                  }`}
                />
                {field.copyButton && (
                  <button
                    type="button"
                    onClick={() => copyToClipboard(String(formData[field.id] ?? ''), field.id)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-slate-400 hover:text-emerald-300 transition-colors"
                    aria-label="Copy to clipboard"
                    title="Copy to clipboard"
                  >
                    {copied === field.id ? (
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                      </svg>
                    )}
                  </button>
                )}
              </div>
            )}

            {field.type === 'password' && (
              <div className="relative">
                <input
                  id={field.id}
                  type={showPassword[field.id] ? 'text' : 'password'}
                  value={formData[field.id] || ''}
                  onChange={(e) => setFormData({ ...formData, [field.id]: e.target.value })}
                  placeholder={field.placeholder}
                  className="w-full px-4 py-2.5 pr-20 bg-black/40 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all font-mono text-sm"
                />
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setShowPassword({ ...showPassword, [field.id]: !showPassword[field.id] })}
                    className="p-1.5 text-slate-400 hover:text-emerald-300 transition-colors"
                    aria-label={showPassword[field.id] ? 'Hide password' : 'Show password'}
                  >
                    {showPassword[field.id] ? (
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                        <line x1="1" y1="1" x2="23" y2="23"></line>
                      </svg>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                      </svg>
                    )}
                  </button>
                  {field.copyButton && field.webhookUrl && (
                    <button
                      type="button"
                      onClick={() => copyToClipboard(field.webhookUrl!, field.id)}
                      className="p-1.5 text-slate-400 hover:text-emerald-300 transition-colors"
                      aria-label="Copy webhook URL"
                      title="Copy webhook URL"
                    >
                      {copied === field.id ? (
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                      ) : (
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                      )}
                    </button>
                  )}
                </div>
              </div>
            )}

            {field.type === 'textarea' && (
              <textarea
                id={field.id}
                value={formData[field.id] || ''}
                onChange={(e) => setFormData({ ...formData, [field.id]: e.target.value })}
                placeholder={field.placeholder}
                rows={4}
                className="w-full px-4 py-2.5 bg-black/40 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all resize-none font-mono text-sm"
              />
            )}

            {field.type === 'checkbox' && field.options && (
              <div className="space-y-2 bg-black/20 border border-white/5 rounded-lg p-4">
                {field.options.map((option) => (
                  <label key={option} className="flex items-center gap-3 cursor-pointer group/check">
                    <input
                      type="checkbox"
                      checked={(formData[field.id] || []).includes(option)}
                      onChange={(e) => handleCheckboxChange(field.id, option, e.target.checked)}
                      className="w-4 h-4 rounded border-white/20 bg-black/40 text-emerald-500 focus:ring-emerald-500/50 focus:ring-offset-0 transition-colors"
                    />
                    <span className="text-sm text-slate-300 group-hover/check:text-white transition-colors">
                      {option}
                    </span>
                  </label>
                ))}
              </div>
            )}

            {field.type === 'multiselect' && (
              <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                <div className="flex flex-wrap gap-2">
                  {(Array.isArray(formData[field.id]) ? formData[field.id] : []).map((value: string) => (
                    <span
                      key={`${field.id}-${value}`}
                      className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/10 px-2.5 py-1 text-xs text-slate-200"
                    >
                      <span>{value}</span>
                      <button
                        type="button"
                        onClick={() => removeMultiSelectValue(field.id, value)}
                        className="text-slate-400 hover:text-white transition-colors"
                        aria-label={`Remove ${value}`}
                      >
                        x
                      </button>
                    </span>
                  ))}
                  <input
                    id={field.id}
                    type="text"
                    value={multiSelectInputs[field.id] || ''}
                    onChange={(e) =>
                      setMultiSelectInputs((prev) => ({ ...prev, [field.id]: e.target.value }))
                    }
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ',') {
                        event.preventDefault();
                        addMultiSelectValues(field.id, event.currentTarget.value);
                      }
                    }}
                    onBlur={(event) => addMultiSelectValues(field.id, event.currentTarget.value)}
                    placeholder={
                      (Array.isArray(formData[field.id]) && formData[field.id].length)
                        ? ''
                        : field.placeholder
                    }
                    className="min-w-[160px] flex-1 bg-transparent px-2 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none"
                  />
                </div>
              </div>
            )}

            {field.helpText && (
              <p className="text-xs text-slate-500 mt-1">{field.helpText}</p>
            )}
          </div>
        ))}

        {/* Message */}
        {message && (
          <div
            className={`px-4 py-3 rounded-lg border ${
              message.type === 'success'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            }`}
          >
            <p className="text-sm">{message.text}</p>
          </div>
        )}

        {/* Save Button */}
        <button
          type="submit"
          disabled={loading}
          className={`w-full py-3 rounded-lg font-semibold text-sm transition-all ${
            loading
              ? 'bg-white/5 text-slate-500 cursor-not-allowed'
              : 'bg-emerald-500 text-black hover:bg-emerald-400 hover:shadow-[0_0_20px_rgba(16,185,129,0.4)] active:scale-[0.98]'
          }`}
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Saving...
            </span>
          ) : (
            'Save Configuration'
          )}
        </button>
      </form>
    </div>
  );
}
