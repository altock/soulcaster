'use client';

import { useState, useEffect } from 'react';
import type { FeedbackItem } from '@/types';

interface EditFeedbackModalProps {
    item: FeedbackItem;
    isOpen: boolean;
    onClose: () => void;
    onSave: (updatedItem: Partial<FeedbackItem>) => Promise<void>;
}

export default function EditFeedbackModal({ item, isOpen, onClose, onSave }: EditFeedbackModalProps) {
    const [body, setBody] = useState(item.body);
    const [githubRepoUrl, setGithubRepoUrl] = useState(item.github_repo_url || '');
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Reset state when item changes or modal opens
    useEffect(() => {
        if (isOpen) {
            setBody(item.body);
            setGithubRepoUrl(item.github_repo_url || '');
            setError(null);
        }
    }, [item, isOpen]);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!body.trim()) return;

        setIsSaving(true);
        setError(null);

        try {
            await onSave({
                body: body.trim(),
                github_repo_url: githubRepoUrl.trim() || undefined,
            });
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save changes');
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-all duration-300">
            <div
                className="relative w-full max-w-2xl overflow-hidden rounded-3xl border border-white/10 bg-[#0A0A0A] shadow-2xl transition-all"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Background Effects */}
                <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent pointer-events-none" />
                <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl pointer-events-none" />

                <div className="relative z-10 p-6 sm:p-8">
                    <div className="flex items-center justify-between mb-6">
                        <h3 className="text-xl font-semibold text-white flex items-center gap-2">
                            <span className="text-2xl">✏️</span> Edit Feedback
                        </h3>
                        <button
                            onClick={onClose}
                            className="p-2 rounded-full hover:bg-white/5 text-slate-400 hover:text-white transition-colors"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div className="space-y-2">
                            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Feedback Content</label>
                            <textarea
                                value={body}
                                onChange={(e) => setBody(e.target.value)}
                                placeholder="Feedback content..."
                                rows={6}
                                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 resize-none transition-all"
                                disabled={isSaving}
                            />
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">GitHub Repository URL</label>
                            <input
                                type="url"
                                value={githubRepoUrl}
                                onChange={(e) => setGithubRepoUrl(e.target.value)}
                                placeholder="https://github.com/username/repo"
                                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all"
                                disabled={isSaving}
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
                                onClick={onClose}
                                disabled={isSaving}
                                className="px-5 py-2.5 rounded-full border border-white/10 text-slate-300 hover:bg-white/5 hover:text-white transition-colors text-sm font-medium"
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                disabled={isSaving || !body.trim()}
                                className="px-6 py-2.5 bg-emerald-500 text-black rounded-full hover:bg-emerald-400 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed transition-all text-sm font-bold shadow-[0_0_20px_rgba(16,185,129,0.2)] hover:shadow-[0_0_30px_rgba(16,185,129,0.4)] active:scale-95"
                            >
                                {isSaving ? 'Saving...' : 'Save Changes'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
