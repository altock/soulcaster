import 'dotenv/config'
import { Template, defaultBuildLogger } from 'e2b'
import { template } from './template'

async function main() {
  await Template.build(template, {
    alias: 'kilo-sandbox-v-0-1',
    skipCache: process.env.E2B_SKIP_CACHE === '1' || process.env.E2B_SKIP_CACHE === 'true',
    onBuildLogs: defaultBuildLogger(),
  });
}

main().catch(console.error);
