import path from 'path';

import dotenv from 'dotenv';
import { defineConfig, devices } from '@playwright/test';

// Load test env vars (.env.test.local overrides .env.local)
dotenv.config({ path: path.resolve(__dirname, '.env.local') });
dotenv.config({ path: path.resolve(__dirname, '.env.test.local'), override: true });

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [['json', { outputFile: 'test-results/results.json' }], ['html', { open: 'never' }]]
    : [['html', { open: 'on-failure' }]],

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  /* Start dev server automatically in CI; locally, run `npm run dev` first */
  ...(process.env.CI
    ? {
        webServer: {
          command: 'npm run build && npm start',
          url: 'http://localhost:3000/sign-in',
          timeout: 180_000,
        },
      }
    : {}),

  projects: [
    // Auth setup — runs first, saves session state
    {
      name: 'setup',
      testMatch: /global\.setup\.ts/,
    },
    // Authenticated tests — depend on setup
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'playwright/.clerk/user.json',
      },
      dependencies: ['setup'],
    },
  ],
});
