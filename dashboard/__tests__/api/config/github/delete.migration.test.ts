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

    del(key: string) {
      this.commands.push(() => {
        this.store.hashes.delete(key);
        this.store.sets.delete(key);
        return 1;
      });
      return this;
    }

    srem(key: string, member: string) {
      this.commands.push(() => {
        const set = this.store.sets.get(key);
        if (set) set.delete(member);
        return 1;
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

    hgetall(key: string) {
      return cloneHashes(this.hashes.get(key));
    }

    del(key: string) {
      this.hashes.delete(key);
      this.sets.delete(key);
    }

    sadd(key: string, member: string) {
      const set = this.sets.get(key) ?? new Set<string>();
      set.add(member);
      this.sets.set(key, set);
    }

    srem(key: string, member: string) {
      const set = this.sets.get(key);
      if (set) set.delete(member);
    }
  }

  return { Redis: MockRedis, __store: shared };
});

describe('API /api/config/github/repos/[name] delete migration', () => {
  const projectId = 'proj-1';
  const repoName = 'naga-k/bad-ux-mart';
  const projectRepoKey = `github:repo:${projectId}:${repoName}`;
  const legacyRepoKey = `github:repo:${repoName}`;
  const projectSet = `github:repos:${projectId}`;
  const legacySet = 'github:repos';

  beforeEach(() => {
    jest.resetModules();
    // Re-require mocked modules AFTER resetModules so we configure the fresh instances
    const { requireProjectId } = require('@/lib/project');
    requireProjectId.mockResolvedValue(projectId);

    const { __store } = require('@upstash/redis');
    __store.hashes.clear();
    __store.sets.clear();

    // Seed both project and legacy entries
    __store.hashes.set(projectRepoKey, { owner: 'naga-k', repo: 'bad-ux-mart', enabled: 'true' });
    __store.hashes.set(legacyRepoKey, { owner: 'naga-k', repo: 'bad-ux-mart', enabled: 'true' });
    __store.sets.set(projectSet, new Set([repoName]));
    __store.sets.set(legacySet, new Set([repoName]));
  });

  it('removes project-scoped and legacy repo records', async () => {
    const { DELETE } = require('@/app/api/config/github/repos/[name]/route');
    const response = await DELETE({ headers: new Headers() } as any, { params: Promise.resolve({ name: encodeURIComponent(repoName) }) });
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.message).toContain(repoName);

    const { __store } = require('@upstash/redis');
    expect(__store.hashes.has(projectRepoKey)).toBe(false);
    expect(__store.hashes.has(legacyRepoKey)).toBe(false);
    expect(__store.sets.get(projectSet)?.has(repoName)).toBe(false);
    expect(__store.sets.get(legacySet)?.has(repoName)).toBe(false);
  });
});
