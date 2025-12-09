import type { PrismaClient as PrismaClientType } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';

type PrismaClientConstructor = typeof import('@prisma/client').PrismaClient;

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClientType };

function isMissingPrismaClient(error: unknown): error is NodeJS.ErrnoException {
  return (
    error instanceof Error &&
    'code' in (error as NodeJS.ErrnoException) &&
    (error as NodeJS.ErrnoException).code === 'MODULE_NOT_FOUND'
  );
}

function getPrismaClientConstructor(): PrismaClientConstructor {
  try {
    const { PrismaClient } = require('@prisma/client') as {
      PrismaClient: PrismaClientConstructor;
    };

    return PrismaClient;
  } catch (error) {
    if (isMissingPrismaClient(error)) {
      throw new Error(
        'Prisma client is missing. Run migrations and generate the client: `npm run prisma:migrate` then `npm run prisma:generate`.'
      );
    }

    throw error;
  }
}

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

  const PrismaClient = getPrismaClientConstructor();

  return new PrismaClient({ adapter, log: ['query'] });
}

export const prisma = globalForPrisma.prisma ?? createPrismaClient();

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}