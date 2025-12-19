'use client';

import type { FeedbackItem } from '@/types';

interface GitHubIssuesListProps {
  items: FeedbackItem[];
}

export default function GitHubIssuesList({ items }: GitHubIssuesListProps) {
  const githubItems = items.filter((item) => item.source === 'github');

  if (githubItems.length === 0) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-purple-900/50 bg-gradient-to-br from-purple-900/20 to-purple-900/5 p-5 backdrop-blur-md">
      <div className="flex items-center gap-2 mb-4">
        <svg
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-5 h-5 text-purple-400"
        >
          <path
            fillRule="evenodd"
            d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
            clipRule="evenodd"
          />
        </svg>
        <h3 className="text-sm font-medium text-purple-300 uppercase tracking-wider">
          GitHub Issues ({githubItems.length})
        </h3>
      </div>
      <div className="space-y-2 max-h-[400px] overflow-y-auto">
        {githubItems.map((item) => (
          <a
            key={item.id}
            href={item.github_issue_url}
            target="_blank"
            rel="noopener noreferrer"
            className="block p-3 rounded-xl bg-purple-900/20 border border-purple-900/30 hover:bg-purple-900/30 hover:border-purple-500/50 transition-all group"
          >
            <div className="flex items-start gap-2">
              <span
                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] ${
                  item.status === 'open'
                    ? 'bg-green-500/20 text-green-400'
                    : 'bg-gray-500/20 text-gray-400'
                }`}
              >
                {item.status === 'open' ? '●' : '✓'}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  {item.repo && (
                    <span className="text-[10px] text-purple-400 font-medium">
                      {item.repo}
                    </span>
                  )}
                  {item.github_issue_number && (
                    <span className="text-[10px] text-purple-300">
                      #{item.github_issue_number}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-200 line-clamp-2 group-hover:text-purple-200">
                  {item.title}
                </p>
              </div>
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                className="w-3 h-3 text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
              >
                <path
                  fillRule="evenodd"
                  d="M4.25 5.5a.75.75 0 00-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-4a.75.75 0 011.5 0v4A2.25 2.25 0 0112.75 17h-8.5A2.25 2.25 0 012 14.75v-8.5A2.25 2.25 0 014.25 4h5a.75.75 0 010 1.5h-5z"
                  clipRule="evenodd"
                />
                <path
                  fillRule="evenodd"
                  d="M6.194 12.753a.75.75 0 001.06.053L16.5 4.44v2.81a.75.75 0 001.5 0v-4.5a.75.75 0 00-.75-.75h-4.5a.75.75 0 000 1.5h2.553l-9.056 8.194a.75.75 0 00-.053 1.06z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
