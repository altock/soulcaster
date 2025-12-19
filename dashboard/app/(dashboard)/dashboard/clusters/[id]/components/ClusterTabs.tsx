'use client';

export type TabId = 'review' | 'plan' | 'jobs';

interface ClusterTabsProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  jobCount: number;
  hasRunningJob: boolean;
}

export default function ClusterTabs({
  activeTab,
  onTabChange,
  jobCount,
  hasRunningJob,
}: ClusterTabsProps) {
  const tabs: { id: TabId; label: string }[] = [
    { id: 'review', label: 'Review' },
    { id: 'plan', label: 'Plan & Fix' },
    { id: 'jobs', label: 'Jobs' },
  ];

  return (
    <nav className="flex items-center gap-1 border-b border-white/10 mb-6">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`relative px-5 py-3 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === tab.id
              ? 'border-emerald-400 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-white/20'
          }`}
        >
          <span className="flex items-center gap-2">
            {tab.label}
            {tab.id === 'jobs' && jobCount > 0 && (
              <span className="flex items-center gap-1.5">
                <span
                  className={`inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-bold ${
                    activeTab === 'jobs'
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-white/10 text-slate-400'
                  }`}
                >
                  {jobCount}
                </span>
                {hasRunningJob && (
                  <span className="h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />
                )}
              </span>
            )}
          </span>
        </button>
      ))}
    </nav>
  );
}
