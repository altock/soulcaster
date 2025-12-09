import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

type ProjectRequest = { url: string; headers?: Headers };

async function resolveProjectId(request: ProjectRequest): Promise<string | undefined> {
  const url = new URL(request.url);
  const searchParams = url.searchParams;

  const fromQuery = searchParams.get('project_id') || searchParams.get('projectId');
  if (fromQuery) return fromQuery;

  const fromHeader = request.headers?.get('x-project-id') || request.headers?.get('x-projectid');
  if (fromHeader) return fromHeader;

  const session = await getServerSession(authOptions);
  return session?.projectId;
}

/**
 * Resolve the project_id from an incoming request.
 * Priority: query string > header > authenticated session
 * Returns undefined if no project_id can be determined (user not authenticated).
 */
export async function getProjectId(request: ProjectRequest): Promise<string | undefined> {
  return resolveProjectId(request);
}

/**
 * Resolve the project_id from an incoming request.
 * Priority: query string > header > authenticated session
 * Throws if no project_id can be determined.
 */
export async function requireProjectId(request: ProjectRequest): Promise<string> {
  const projectId = await resolveProjectId(request);
  if (!projectId) {
    throw new Error('project_id is required');
  }
  return projectId;
}
