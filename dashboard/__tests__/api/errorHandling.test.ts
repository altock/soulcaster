/**
 * Tests for backend fetch error handling across dashboard API routes.
 */

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
  requireProjectId: jest.fn(),
  getProjectId: jest.fn(),
}));

jest.mock('@/lib/auth', () => ({
  getGitHubToken: jest.fn(),
}));

import { requireProjectId, getProjectId } from '@/lib/project';
import { getGitHubToken } from '@/lib/auth';

const mockRequireProjectId = requireProjectId as jest.MockedFunction<typeof requireProjectId>;
const mockGetProjectId = getProjectId as jest.MockedFunction<typeof getProjectId>;
const mockGetGitHubToken = getGitHubToken as jest.MockedFunction<typeof getGitHubToken>;

const backendUrl = 'http://backend.test';
const projectId = 'proj-123';
const githubToken = 'gho_test';

type BackendBehavior = (url: any, init?: any) => Promise<any>;

const okResponse = (body: any, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
  text: async () => JSON.stringify(body),
});

const makeFetchMock = (behavior: BackendBehavior) =>
  jest.fn((url, init) => behavior(url, init));

const simulateAbortError = () => {
  const err: any = new Error('The operation was aborted.');
  err.name = 'AbortError';
  return err;
};

const expectJson = async (response: any) => {
  return await response.json();
};

const makeRequest = (url = 'http://test', method = 'GET', body?: any) => {
  return {
    url,
    method,
    headers: new Headers(),
    json: async () => body,
  } as any;
};

describe('API route error handling', () => {
  beforeEach(() => {
    process.env.BACKEND_URL = backendUrl;
    jest.clearAllMocks();
  });

  const routes = [
    {
      name: 'clusters/[id] GET',
      loader: () => require('@/app/api/clusters/[id]/route'),
      body: { cluster: true },
      invoke: async (mod: any, backendBehavior: number | BackendBehavior = 200) => {
        mockRequireProjectId.mockResolvedValue(projectId);
        const request = makeRequest('http://test');
        const behavior =
          typeof backendBehavior === 'function'
            ? backendBehavior
            : async () => okResponse({ cluster: true }, backendBehavior);
        (global.fetch as any) = makeFetchMock(behavior);
        const res = await mod.GET(request, { params: Promise.resolve({ id: 'abc' }) });
        return res;
      },
    },
    {
      name: 'clusters list GET',
      loader: () => require('@/app/api/clusters/route'),
      body: { clusters: [] },
      invoke: async (mod: any, backendBehavior: number | BackendBehavior = 200) => {
        mockRequireProjectId.mockResolvedValue(projectId);
        const request = makeRequest('http://test');
        const behavior =
          typeof backendBehavior === 'function'
            ? backendBehavior
            : async () => okResponse({ clusters: [] }, backendBehavior);
        (global.fetch as any) = makeFetchMock(behavior);
        const res = await mod.GET(request);
        return res;
      },
    },
    {
      name: 'feedback GET',
      loader: () => require('@/app/api/feedback/route'),
      body: { items: [] },
      invoke: async (mod: any, backendBehavior: number | BackendBehavior = 200) => {
        mockRequireProjectId.mockResolvedValue(projectId);
        const request = makeRequest('http://test?limit=10&offset=0');
        const behavior =
          typeof backendBehavior === 'function'
            ? backendBehavior
            : async () => okResponse({ items: [] }, backendBehavior);
        (global.fetch as any) = makeFetchMock(behavior);
        const res = await mod.GET(request);
        return res;
      },
    },
    {
      name: 'feedback PUT',
      loader: () => require('@/app/api/feedback/route'),
      body: { updated: true },
      invoke: async (mod: any, backendBehavior: number | BackendBehavior = 200) => {
        mockRequireProjectId.mockResolvedValue(projectId);
        const request = makeRequest('http://test', 'PUT', { id: 'f1', text: 'hi' });
        const behavior =
          typeof backendBehavior === 'function'
            ? backendBehavior
            : async () => okResponse({ updated: true }, backendBehavior);
        (global.fetch as any) = makeFetchMock(behavior);
        const res = await mod.PUT(request);
        return res;
      },
    },
    {
      name: 'stats GET',
      loader: () => require('@/app/api/stats/route'),
      body: { stats: {} },
      invoke: async (mod: any, backendBehavior: number | BackendBehavior = 200) => {
        mockRequireProjectId.mockResolvedValue(projectId);
        const request = makeRequest('http://test');
        const behavior =
          typeof backendBehavior === 'function'
            ? backendBehavior
            : async () => okResponse({ stats: {} }, backendBehavior);
        (global.fetch as any) = makeFetchMock(behavior);
        const res = await mod.GET(request);
        return res;
      },
    },
    {
      name: 'reddit subreddits GET',
      loader: () => require('@/app/api/config/reddit/subreddits/route'),
      body: { subreddits: [] },
      invoke: async (mod: any, backendBehavior: number | BackendBehavior = 200) => {
        mockRequireProjectId.mockResolvedValue(projectId);
        const request = makeRequest('http://test');
        const behavior =
          typeof backendBehavior === 'function'
            ? backendBehavior
            : async () => okResponse({ subreddits: [] }, backendBehavior);
        (global.fetch as any) = makeFetchMock(behavior);
        const res = await mod.GET(request);
        return res;
      },
    },
    {
      name: 'reddit subreddits POST',
      loader: () => require('@/app/api/config/reddit/subreddits/route'),
      body: { subreddits: ['a'] },
      invoke: async (mod: any, backendBehavior: number | BackendBehavior = 200) => {
        mockRequireProjectId.mockResolvedValue(projectId);
        const request = makeRequest('http://test', 'POST', { subreddits: ['a'] });
        const behavior =
          typeof backendBehavior === 'function'
            ? backendBehavior
            : async () => okResponse({ subreddits: ['a'] }, backendBehavior);
        (global.fetch as any) = makeFetchMock(behavior);
        const res = await mod.POST(request);
        return res;
      },
    },
    {
      name: 'trigger-poll POST',
      loader: () => require('@/app/api/admin/trigger-poll/route'),
      body: { ok: true },
      invoke: async (mod: any, backendBehavior: number | BackendBehavior = 200) => {
        const request = makeRequest('http://test', 'POST');
        const behavior =
          typeof backendBehavior === 'function'
            ? backendBehavior
            : async () => okResponse({ ok: true }, backendBehavior);
        (global.fetch as any) = makeFetchMock(behavior);
        const res = await mod.POST(request);
        return res;
      },
    },
    {
      name: 'ingest manual POST',
      loader: () => require('@/app/api/ingest/manual/route'),
      body: { ok: true },
      invoke: async (mod: any, backendBehavior: number | BackendBehavior = 200) => {
        mockRequireProjectId.mockResolvedValue(projectId);
        const request = makeRequest('http://test', 'POST', { text: 'hello' });
        const behavior =
          typeof backendBehavior === 'function'
            ? backendBehavior
            : async () => okResponse({ ok: true }, backendBehavior);
        (global.fetch as any) = makeFetchMock(behavior);
        const res = await mod.POST(request as any);
        return res;
      },
    },
    {
      name: 'ingest github sync POST',
      loader: () => require('@/app/api/ingest/github/sync/[name]/route'),
      body: { ok: true },
      invoke: async (mod: any, backendBehavior: number | BackendBehavior = 200) => {
        mockGetProjectId.mockImplementation(async () => projectId);
        mockGetGitHubToken.mockImplementation(async () => githubToken);
        const request = { headers: new Headers(), method: 'POST' } as any;
        const behavior =
          typeof backendBehavior === 'function'
            ? backendBehavior
            : async () => okResponse({ ok: true }, backendBehavior);
        (global.fetch as any) = makeFetchMock(behavior);
        const res = await mod.POST(request, { params: Promise.resolve({ name: 'org%2Frepo' }) });
        return res;
      },
    },
  ];

  describe('success paths', () => {
    for (const route of routes) {
      it(`${route.name} returns backend data with same status`, async () => {
        const mod = route.loader();
        const res = await route.invoke(mod, 200);
        const body = await expectJson(res);
        expect(res.status).toBe(200);
        expect(body).toBeDefined();
      });
    }
  });

  describe('backend 5xx maps to 502', () => {
    for (const route of routes) {
      it(`${route.name} maps backend 500 to 502`, async () => {
        const mod = route.loader();
        const res = await route.invoke(mod, 500);
        expect(res.status).toBe(502);
      });
    }
  });

  describe('backend 4xx preserved', () => {
    for (const route of routes) {
      it(`${route.name} preserves 404`, async () => {
        const mod = route.loader();
        const res = await route.invoke(mod, 404);
        expect(res.status).toBe(404);
      });
    }
  });

  describe('timeout -> 503', () => {
    for (const route of routes) {
      it(`${route.name} returns 503 on AbortError`, async () => {
        const mod = route.loader();
        mockRequireProjectId.mockResolvedValue(projectId);
        mockGetProjectId.mockResolvedValue(projectId);
        mockGetGitHubToken.mockResolvedValue(githubToken);
        const res = await route.invoke(mod, async () => {
          throw simulateAbortError();
        });
        expect(res.status).toBe(503);
      });
    }
  });

  describe('generic rejection -> 500', () => {
    for (const route of routes) {
      it(`${route.name} returns 500 on fetch error`, async () => {
        const mod = route.loader();
        mockRequireProjectId.mockResolvedValue(projectId);
        mockGetProjectId.mockResolvedValue(projectId);
        mockGetGitHubToken.mockResolvedValue(githubToken);
        const res = await route.invoke(mod, async () => {
          throw new Error('network fail');
        });
        expect(res.status).toBe(500);
      });
    }
  });
});
