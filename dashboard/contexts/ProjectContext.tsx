'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useSession } from 'next-auth/react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';

export interface Project {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  userId: string;
}

interface ProjectContextValue {
  currentProject: Project | null;
  currentProjectId: string | null;
  projects: Project[];
  isLoading: boolean;
  error: string | null;
  switchProject: (projectId: string) => void;
  createProject: (name: string) => Promise<Project>;
  refreshProjects: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

const STORAGE_KEY = 'soulcaster_current_project_id';

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Get project ID from URL, localStorage, or session (in that order)
  useEffect(() => {
    if (status === 'loading') return;

    const urlProjectId = searchParams.get('project_id') || searchParams.get('projectId');
    const storedProjectId = typeof window !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
    const sessionProjectId = session?.projectId;

    const resolvedId = urlProjectId || storedProjectId || sessionProjectId || null;
    setCurrentProjectId(resolvedId);

    // Sync to localStorage
    if (resolvedId && typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, resolvedId);
    }
  }, [searchParams, session?.projectId, status]);

  // Fetch user's projects
  const refreshProjects = useCallback(async () => {
    if (!session?.user?.id) {
      setProjects([]);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const res = await fetch('/api/projects');
      if (!res.ok) {
        throw new Error('Failed to fetch projects');
      }
      const data = await res.json();
      setProjects(data.projects || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
      setProjects([]);
    } finally {
      setIsLoading(false);
    }
  }, [session?.user?.id]);

  useEffect(() => {
    if (status === 'authenticated') {
      refreshProjects();
    } else if (status === 'unauthenticated') {
      setProjects([]);
      setIsLoading(false);
    }
  }, [status, refreshProjects]);

  // Get current project object
  const currentProject = projects.find(p => p.id === currentProjectId) || null;

  // Auto-select first project if currentProjectId doesn't match any project
  useEffect(() => {
    if (!isLoading && projects.length > 0 && !currentProject && currentProjectId) {
      // currentProjectId is set but doesn't match any project - fallback to first project
      console.log('[ProjectContext] Auto-selecting first project because currentProjectId is invalid');
      setCurrentProjectId(projects[0].id);
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, projects[0].id);
      }
    } else if (!isLoading && projects.length > 0 && !currentProjectId) {
      // No currentProjectId at all - select first project
      console.log('[ProjectContext] Auto-selecting first project');
      setCurrentProjectId(projects[0].id);
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, projects[0].id);
      }
    }
  }, [isLoading, projects, currentProject, currentProjectId]);

  // Switch to a different project
  const switchProject = useCallback((projectId: string) => {
    setCurrentProjectId(projectId);

    // Save to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, projectId);
    }

    // Update URL with new project_id
    const params = new URLSearchParams(searchParams.toString());
    params.set('project_id', projectId);
    router.push(`${pathname}?${params.toString()}`);
  }, [pathname, router, searchParams]);

  // Create a new project
  const createProject = useCallback(async (name: string): Promise<Project> => {
    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || 'Failed to create project');
    }

    const data = await res.json();
    const newProject = data.project as Project;

    // Refresh projects list
    await refreshProjects();

    // Switch to the new project
    switchProject(newProject.id);

    return newProject;
  }, [refreshProjects, switchProject]);

  return (
    <ProjectContext.Provider
      value={{
        currentProject,
        currentProjectId,
        projects,
        isLoading,
        error,
        switchProject,
        createProject,
        refreshProjects,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
}
