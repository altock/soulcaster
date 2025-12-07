# Neon DB Integration Plan

## Objective
Integrate Neon DB (PostgreSQL) with NextAuth.js to persist user sessions and data.

## Current State
- Authentication: NextAuth.js with GitHub Provider.  
- Session Strategy: JWT (stateless).  
 
- Persistence: None (in-memory/JWT only).  
  _Partially outdated – Prisma + a Postgres datasource are now present; the dashboard uses a Prisma adapter for NextAuth, but additional application data beyond auth is still minimal._

## Proposed Architecture
1.  **Database:** Neon Serverless Postgres.
2.  **Adapter:** `@auth/pg-adapter` or `@next-auth/prisma-adapter` (Prisma is recommended for type safety and schema management).
3.  **Schema:** Standard NextAuth schema (User, Account, Session, VerificationToken).

## Steps
1.  **Install Dependencies:**
    - `npm install @prisma/client @auth/prisma-adapter prisma`  
    - OR `npm install pg @auth/pg-adapter` (if avoiding Prisma).
    - *Recommendation:* Use Prisma for easier schema management.  
 

2.  **Configure Prisma:**
    - Initialize Prisma: `npx prisma init`  
    - Update `prisma/schema.prisma` with NextAuth models.  
    - Configure `datasource db` to use `POSTGRES_PRISMA_URL` and `POSTGRES_URL_NON_POOLING`.  
      _Partially done – datasource is configured via `DATABASE_URL`; Neon-specific URLs can be added as needed._

3.  **Update NextAuth Config (`dashboard/lib/auth.ts`):**
    - Import `PrismaAdapter`.  
    - Add `adapter: PrismaAdapter(prisma)` to `authOptions`.  
    - Switch `session.strategy` to `database` (optional, but default with adapter) or keep `jwt` but sync user to DB.  
      _Partially done – strategy remains `jwt` for now while still persisting user records via the adapter._

4.  **Environment Variables:**
    - Add `DATABASE_URL` (Neon connection string) to `.env.local`.  
      _Partially done – `DATABASE_URL` is expected/configured for Prisma; for Neon specifically you still need to point it at the Neon connection string in your environment._

5.  **Migration:**
    - Run `npx prisma db push` or `npx prisma migrate dev` to create tables in Neon.  
      _Partially done – migrations have been run for local/Postgres usage; for Neon you should still ensure schema is applied against the Neon instance._

## Schema (Prisma)
```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model Account {
  id                 String  @id @default(cuid())
  userId             String
  type               String
  provider           String
  providerAccountId  String
  refresh_token      String?  @db.Text
  access_token       String?  @db.Text
  expires_at         Int?
  token_type         String?
  scope              String?
  id_token           String?  @db.Text
  session_state      String?

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([provider, providerAccountId])
}

model Session {
  id           String   @id @default(cuid())
  sessionToken String   @unique
  userId       String
  expires      DateTime
  user         User     @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model User {
  id            String    @id @default(cuid())
  name          String?
  email         String?   @unique
  emailVerified DateTime?
  image         String?
  accounts      Account[]
  sessions      Session[]
}

model VerificationToken {
  identifier String
  token      String   @unique
  expires    DateTime

  @@unique([identifier, token])
}
