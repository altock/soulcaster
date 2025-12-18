jest.mock('next/server', () => ({
  NextResponse: {
    json: jest.fn((data, init) => ({
      json: async () => data,
      status: init?.status ?? 200,
    })),
  },
  Headers,
}));
jest.mock('@/lib/project', () => ({
  getProjectId: jest.fn(),
}));
jest.mock('@/lib/auth', () => ({
  getGitHubToken: jest.fn(),
}));

import { getProjectId } from '@/lib/project';
import { getGitHubToken } from '@/lib/auth';

const mockGetProjectId = getProjectId as jest.MockedFunction<typeof getProjectId>;
const mockGetGitHubToken = getGitHubToken as jest.MockedFunction<typeof getGitHubToken>;

describe('API /api/ingest/github/sync/[name]', () => {
  const backendUrl = 'http://backend.test';
  const projectId = 'proj-123';
  const token = 'gho_test_token';

  let originalBackendUrl: string | undefined;
  let originalFetch: typeof fetch;

  beforeEach(() => {
    originalBackendUrl = process.env.BACKEND_URL;
    originalFetch = global.fetch;
    process.env.BACKEND_URL = backendUrl;
    jest.clearAllMocks();
    (global.fetch as any) = jest.fn();
  });

  afterEach(() => {
    if (originalBackendUrl !== undefined) {
      process.env.BACKEND_URL = originalBackendUrl;
    } else {
      delete process.env.BACKEND_URL;
    }
    global.fetch = originalFetch;
  });

  it('forwards project, token, and repo to backend', async () => {
    const backendPayload = { success: true, new_issues: 1 };

    mockGetProjectId.mockResolvedValue(projectId);
    mockGetGitHubToken.mockResolvedValue(token);

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => backendPayload,
    });

    const request = { headers: new Headers(), method: 'POST' } as any;

    const { POST } = require('@/app/api/ingest/github/sync/[name]/route');
    const response = await POST(request, { params: Promise.resolve({ name: 'org%2Frepo' }) });
    const data = await response.json();

    expect(data).toEqual(backendPayload);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe(`${backendUrl}/ingest/github/sync/org%2Frepo?project_id=${projectId}`);
    expect(options.method).toBe('POST');
    expect(options.headers['X-GitHub-Token']).toBe(token);
  });

  it('returns 401 when project is missing', async () => {
    mockGetProjectId.mockResolvedValue(undefined);
    mockGetGitHubToken.mockResolvedValue(token);

    const request = { headers: new Headers(), method: 'POST' } as any;

    const { POST } = require('@/app/api/ingest/github/sync/[name]/route');
    const response = await POST(request, { params: Promise.resolve({ name: 'org%2Frepo' }) });
    expect(response.status).toBe(401);
  });
});
