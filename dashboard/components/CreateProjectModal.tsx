'use client';

import { useState } from 'react';

interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreateProject: (name: string) => Promise<void>;
}

export default function CreateProjectModal({
  isOpen,
  onClose,
  onCreateProject,
}: CreateProjectModalProps) {
  const [name, setName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsCreating(true);
    setError(null);

    try {
      await onCreateProject(name.trim());
      setName('');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setIsCreating(false);
    }
  };

  const handleClose = () => {
    if (!isCreating) {
      setName('');
      setError(null);
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-all duration-300"
      onClick={handleClose}
    >
      <div
        className="relative w-full max-w-md overflow-hidden rounded-3xl border border-white/10 bg-[#0A0A0A] shadow-2xl transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Background Effects */}
        <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent pointer-events-none" />
        <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl pointer-events-none" />

        <div className="relative z-10 p-6 sm:p-8">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-white">Create New Project</h3>
            <button
              onClick={handleClose}
              disabled={isCreating}
              className="p-2 rounded-full hover:bg-white/5 text-slate-400 hover:text-white transition-colors disabled:opacity-50"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Project Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My Awesome Project"
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all"
                disabled={isCreating}
                autoFocus
              />
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
                {error}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={handleClose}
                disabled={isCreating}
                className="px-5 py-2.5 rounded-full border border-white/10 text-slate-300 hover:bg-white/5 hover:text-white transition-colors text-sm font-medium disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isCreating || !name.trim()}
                className="px-6 py-2.5 bg-emerald-500 text-black rounded-full hover:bg-emerald-400 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed transition-all text-sm font-bold shadow-[0_0_20px_rgba(16,185,129,0.2)] hover:shadow-[0_0_30px_rgba(16,185,129,0.4)] active:scale-95"
              >
                {isCreating ? (
                  <span className="flex items-center gap-2">
                    <svg
                      className="animate-spin h-4 w-4"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      ></circle>
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      ></path>
                    </svg>
                    Creating...
                  </span>
                ) : (
                  'Create Project'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
