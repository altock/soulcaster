-- AlterTable
ALTER TABLE "User" ADD COLUMN     "consentedAt" TIMESTAMP(3),
ADD COLUMN     "consentedToResearch" BOOLEAN NOT NULL DEFAULT false;
