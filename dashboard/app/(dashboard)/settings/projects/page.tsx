'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useProject, Project } from '@/contexts/ProjectContext';
import CreateProjectModal from '@/components/CreateProjectModal';
import { Skeleton, SkeletonText } from '@/components/ui/Skeleton';

export default function ProjectsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    projects,
    currentProjectId,
    isLoading,
    error,
    switchProject,
    createProject,
    refreshProjects,
  } = useProject();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const handleSwitchProject = (project: Project) => {
    switchProject(project.id);
    // Navigate to dashboard with the new project
    router.push(`/dashboard?project_id=${project.id}`);
  };

  const handleCreateProject = async (name: string) => {
    await createProject(name);
  };

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <div className="relative overflow-hidden border-b border-white/5 bg-gradient-to-b from-black via-black/95 to-transparent">
        <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-96 w-[800px] rounded-full bg-emerald-500/10 blur-[120px] opacity-60 animate-pulse" />

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 mb-6">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="text-xs font-medium text-emerald-300">Settings</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">
            <span className="bg-gradient-to-r from-white via-emerald-200 to-emerald-400 bg-clip-text text-transparent">
              Projects
            </span>
          </h1>

          <p className="text-lg text-slate-400 max-w-2xl leading-relaxed font-light">
            Manage your projects. Each project has its own feedback, clusters, and integrations.
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Actions Bar */}
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-xl font-semibold text-white">Your Projects</h2>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="px-5 py-2.5 bg-emerald-500 text-black rounded-full hover:bg-emerald-400 transition-all text-sm font-bold shadow-[0_0_20px_rgba(16,185,129,0.2)] hover:shadow-[0_0_30px_rgba(16,185,129,0.4)] active:scale-95"
          >
            + New Project
          </button>
        </div>

        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
            <p className="text-sm">{error}</p>
            <button
              onClick={refreshProjects}
              className="mt-2 text-xs underline hover:no-underline"
            >
              Try again
            </button>
          </div>
        )}

        {/* Loading State */}
        {isLoading ? (
          <div className="grid gap-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="p-6 rounded-2xl border border-white/10 bg-matrix-card"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <Skeleton className="h-6 w-48 mb-2" />
                    <Skeleton className="h-4 w-32" />
                  </div>
                  <Skeleton className="h-9 w-24 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        ) : projects.length === 0 ? (
          /* Empty State */
          <div className="text-center py-16 rounded-2xl border border-white/10 bg-matrix-card">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-500/10 flex items-center justify-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="32"
                height="32"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-emerald-400"
              >
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                <line x1="12" y1="11" x2="12" y2="17"></line>
                <line x1="9" y1="14" x2="15" y2="14"></line>
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">No projects yet</h3>
            <p className="text-slate-400 mb-6">Create your first project to get started.</p>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="px-5 py-2.5 bg-emerald-500 text-black rounded-full hover:bg-emerald-400 transition-all text-sm font-bold"
            >
              Create Project
            </button>
          </div>
        ) : (
          /* Projects List */
          <div className="grid gap-4">
            {projects.map((project) => {
              const isActive = project.id === currentProjectId;
              return (
                <div
                  key={project.id}
                  className={`p-6 rounded-2xl border transition-all ${
                    isActive
                      ? 'border-emerald-500/40 bg-emerald-500/5'
                      : 'border-white/10 bg-matrix-card hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <h3 className="text-lg font-semibold text-white truncate">
                          {project.name}
                        </h3>
                        {isActive && (
                          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                            Active
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-500 mt-1">
                        Created {new Date(project.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 ml-4">
                      {isActive ? (
                        <span className="px-4 py-2 text-sm text-slate-500">Current</span>
                      ) : (
                        <button
                          onClick={() => handleSwitchProject(project)}
                          className="px-4 py-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 transition-all text-sm font-medium"
                        >
                          Switch
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      <CreateProjectModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreateProject={handleCreateProject}
      />
    </div>
  );
}
