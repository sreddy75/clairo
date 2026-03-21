import { test as base, expect } from '@playwright/test';

/**
 * Extended test fixture with helpers for authenticated Clairo sessions.
 * All tests using this fixture inherit the Clerk auth state from global setup.
 */
export const test = base.extend<{
  /** Navigate to a page and wait for it to be ready (no loading spinners) */
  navigateTo: (path: string) => Promise<void>;
}>({
  navigateTo: async ({ page }, use) => {
    await use(async (path: string) => {
      await page.goto(path);
      // Wait for main content to be interactive (Clerk + Next.js hydration)
      await page.waitForLoadState('networkidle');
    });
  },
});

export { expect };
