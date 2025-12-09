import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

/**
 * Resolve the project_id from an incoming request.
 * Priority: query string > header > authenticated session
 * Throws if no project_id can be determined.
 */
export async function requireProjectId(request: { url: string; headers?: Headers }): Promise<string> {
  const url = new URL(request.url);
  const searchParams = url.searchParams;

  // Check query string first
  const fromQuery =
    searchParams.get('project_id') || searchParams.get('projectId');
  if (fromQuery) return fromQuery;

  // Check header
  const fromHeader =
    request.headers?.get('x-project-id') || request.headers?.get('x-projectid');
  if (fromHeader) return fromHeader;

  // Fall back to authenticated session's project
  const session = await getServerSession(authOptions);
  if (session?.projectId) {
    return session.projectId;
  }

  throw new Error('project_id is required');
}

/**
 * Resolve the project_id from an incoming request.
 * Priority: query string > header > authenticated session
 * Returns undefined if no project_id can be determined (user not authenticated).
 */
export async function getProjectId(request: { url: string; headers?: Headers }): Promise<string | undefined> {
  const url = new URL(request.url);
  const searchParams = url.searchParams;

  // Check query string first
  const fromQuery =
    searchParams.get('project_id') || searchParams.get('projectId');
  if (fromQuery) return fromQuery;

  // Check header
  const fromHeader =
    request.headers?.get('x-project-id') || request.headers?.get('x-projectid');
  if (fromHeader) return fromHeader;

  // Fall back to authenticated session's project
  const session = await getServerSession(authOptions);
  return session?.projectId;
}
