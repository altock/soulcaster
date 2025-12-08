/**
 * Resolve the project_id from an incoming request.
 * Prefers query string `project_id`/`projectId`, then `x-project-id` header.
 * Throws if missing so callers can return a 400.
 */
export function requireProjectId(request: { url: string; headers?: Headers }): string {
  const url = new URL(request.url);
  const searchParams = url.searchParams;

  const fromQuery =
    searchParams.get('project_id') || searchParams.get('projectId');
  const fromHeader =
    request.headers?.get('x-project-id') || request.headers?.get('x-projectid');

  const projectId = fromQuery || fromHeader;
  if (!projectId) {
    throw new Error('project_id is required');
  }
  return projectId;
}
