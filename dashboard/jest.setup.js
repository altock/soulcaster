import '@testing-library/jest-dom'
import { TextEncoder, TextDecoder } from 'util'

// Polyfill for Next.js API routes
global.TextEncoder = TextEncoder
global.TextDecoder = TextDecoder

// Mock environment variables for tests
process.env.NEXTAUTH_URL = 'http://localhost:3000'
process.env.NEXTAUTH_SECRET = 'test-secret'
process.env.GITHUB_ID = 'test-github-id'
process.env.GITHUB_SECRET = 'test-github-secret'

// Upstash Vector env vars (mock values for testing)
process.env.UPSTASH_VECTOR_REST_URL = 'https://test-vector.upstash.io'
process.env.UPSTASH_VECTOR_REST_TOKEN = 'test-vector-token'

// Provide dummy database URL for Prisma mocks
process.env.DATABASE_URL = 'postgres://user:pass@localhost:5432/testdb'

// Mock Prisma adapter/client to avoid loading real ESM modules in tests
jest.mock('@auth/prisma-adapter', () => ({
  PrismaAdapter: jest.fn(() => ({})),
}))

jest.mock('@prisma/adapter-pg', () => ({
  PrismaPg: jest.fn(() => ({})),
}))

jest.mock('@prisma/client', () => ({
  PrismaClient: jest.fn(() => ({
    $transaction: jest.fn(async (fn) => fn({
      user: {
        upsert: jest.fn().mockResolvedValue({ id: 'user-1', defaultProjectId: null }),
        findUnique: jest.fn().mockResolvedValue({ defaultProjectId: null }),
        update: jest.fn().mockResolvedValue({ defaultProjectId: 'project-1' }),
      },
      project: {
        create: jest.fn().mockResolvedValue({ id: 'project-1' }),
      },
    })),
  })),
  Prisma: {
    TransactionClient: class {},
  },
}))

jest.mock('@/lib/prisma', () => ({
  prisma: {
    $transaction: jest.fn(async (fn) => fn({
      user: {
        upsert: jest.fn().mockResolvedValue({ id: 'user-1', defaultProjectId: null }),
        findUnique: jest.fn().mockResolvedValue({ defaultProjectId: null }),
        update: jest.fn().mockResolvedValue({ defaultProjectId: 'project-1' }),
      },
      project: {
        create: jest.fn().mockResolvedValue({ id: 'project-1' }),
      },
    })),
  },
}))

// Minimal Web API stubs if not provided by the environment
if (typeof global.Request === 'undefined') {
  global.Request = class Request {}
}
if (typeof global.Response === 'undefined') {
  global.Response = class Response {}
}
if (typeof global.Headers === 'undefined') {
  global.Headers = class Headers {}
}
