import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

type ProjectRequest = { url: string; headers?: Headers };

/**
 * Resolve the project identifier from an incoming request by checking query parameters, request headers, then the authenticated session.
 *
 * @param request - Incoming request object containing a `url` and optional `headers`. The function checks `project_id` or `projectId` query parameters first, then `x-project-id` or `x-projectid` headers, and finally the authenticated session's `projectId`.
 * @returns The project id if found, `undefined` otherwise.
 */
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
 * Resolve the project identifier from an incoming request using query parameters, request headers, then the authenticated session.
 *
 * @param request - Incoming request object containing a `url` and optional `headers` to inspect for the project identifier
 * @returns The project identifier found in the request or session, or `undefined` if none could be determined
 */
export async function getProjectId(request: ProjectRequest): Promise<string | undefined> {
  return resolveProjectId(request);
}

/**
 * Obtain the project identifier for the given request and fail if it cannot be determined.
 *
 * @returns The resolved `project_id` string.
 * @throws Error when a `project_id` cannot be determined from the request or session.
 */
export async function requireProjectId(request: ProjectRequest): Promise<string> {
  const projectId = await resolveProjectId(request);
  if (!projectId) {
    throw new Error('project_id is required');
  }
  return projectId;
}