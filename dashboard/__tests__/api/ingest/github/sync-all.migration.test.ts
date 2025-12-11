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

jest.mock('@upstash/redis', () => {
  type Hashes = Map<string, Record<string, string>>;
  type Sets = Map<string, Set<string>>;

  const shared = {
    hashes: new Map() as Hashes,
    sets: new Map() as Sets,
  };

  const cloneHashes = (value?: Record<string, string>) => (value ? { ...value } : {});

  class MockPipeline {
    private commands: Array<() => any> = [];
    constructor(private store: typeof shared) {}

    hgetall(key: string) {
      this.commands.push(() => cloneHashes(this.store.hashes.get(key)));
      return this;
    }

    sadd(key: string, member: string) {
      this.commands.push(() => {
        const set = this.store.sets.get(key) ?? new Set<string>();
        set.add(member);
        this.store.sets.set(key, set);
        return true;
      });
      return this;
    }

    exec() {
      return Promise.resolve(this.commands.map((fn) => fn()));
    }
  }

  class MockRedis {
    hashes = shared.hashes;
    sets = shared.sets;

    pipeline() {
      return new MockPipeline(shared);
    }

    smembers(key: string) {
      return Array.from(this.sets.get(key) ?? []);
    }

    sadd(key: string, member: string) {
      const set = this.sets.get(key) ?? new Set<string>();
      set.add(member);
      this.sets.set(key, set);
    }

    hgetall(key: string) {
      return cloneHashes(this.hashes.get(key));
    }

    hset(key: string, mapping: Record<string, string>) {
      const existing = this.hashes.get(key) ?? {};
      this.hashes.set(key, { ...existing, ...mapping });
    }
  }

  return { Redis: MockRedis, __store: shared };
});

describe('API /api/ingest/github/sync (sync-all) migration', () => {
  const backendUrl = 'http://backend.test';
  const projectId = 'proj-1';
  const repoName = 'org/repo';
  const legacyRepoKey = `github:repo:${repoName}`;
  const legacyReposSet = 'github:repos';
  const projectReposSet = `github:repos:${projectId}`;
  const projectRepoKey = `github:repo:${projectId}:${repoName}`;
  const token = 'gho_test_token';

  let originalFetch: typeof fetch;
  let originalBackendUrl: string | undefined;

  beforeEach(() => {
    jest.resetModules();
    originalFetch = global.fetch;
    originalBackendUrl = process.env.BACKEND_URL;
    global.fetch = jest.fn();
    process.env.BACKEND_URL = backendUrl;

    // Re-require mocked modules AFTER resetModules so we configure the fresh instances
    const { getProjectId } = require('@/lib/project');
    const { getGitHubToken } = require('@/lib/auth');

    getProjectId.mockResolvedValue(projectId);
    getGitHubToken.mockResolvedValue(token);

    const { __store } = require('@upstash/redis');
    __store.hashes.clear();
    __store.sets.clear();

    // Legacy entries (to exercise migration) plus project-scoped entries
    __store.sets.set(legacyReposSet, new Set([repoName]));
    __store.hashes.set(legacyRepoKey, {
      owner: 'org',
      repo: 'repo',
      enabled: 'true',
    });
    __store.sets.set(projectReposSet, new Set([repoName]));
    __store.hashes.set(projectRepoKey, {
      owner: 'org',
      repo: 'repo',
      enabled: 'true',
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalBackendUrl !== undefined) {
      process.env.BACKEND_URL = originalBackendUrl;
    } else {
      delete process.env.BACKEND_URL;
    }
  });

  it('proxies to backend per repo and aggregates results', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        repo: repoName,
        new_issues: 1,
        updated_issues: 0,
        closed_issues: 0,
        total_issues: 1,
        ignored_prs: 0,
      }),
    });

    const { POST } = require('@/app/api/ingest/github/sync/route');
    const response = await POST({ headers: new Headers(), url: 'http://localhost/api' } as any);
    const data = await response.json();

    expect(data.total_new).toBe(1);
    expect(data.total_updated).toBe(0);
    expect(data.total_closed).toBe(0);
    expect(data.repos).toEqual([
      {
        repo: repoName,
        new: 1,
        updated: 0,
        closed: 0,
        total: 1,
        ignored_prs: 0,
      },
    ]);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe(`${backendUrl}/ingest/github/sync/${encodeURIComponent(repoName)}?project_id=${projectId}`);
    expect(options.method).toBe('POST');
    expect(options.headers['X-GitHub-Token']).toBe(token);
  });
});
