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
