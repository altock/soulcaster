import { PrismaClient } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

/**
 * Create a PrismaClient configured for the PostgreSQL connection specified by DATABASE_URL.
 *
 * The client is instantiated with a PrismaPg adapter using the environment's `DATABASE_URL`
 * and is configured to emit `query` logs.
 *
 * @returns A configured `PrismaClient` instance
 * @throws If `DATABASE_URL` is not set in the environment
 */
function createPrismaClient() {
  if (!process.env.DATABASE_URL) {
    throw new Error('DATABASE_URL is required to initialize Prisma');
  }

  const adapter = new PrismaPg({
    connectionString: process.env.DATABASE_URL,
  });

  return new PrismaClient({ adapter, log: ['query'] });
}

export const prisma = globalForPrisma.prisma ?? createPrismaClient();

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}