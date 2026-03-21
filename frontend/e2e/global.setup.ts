import path from 'path';

import { clerkSetup } from '@clerk/testing/playwright';
import { test as setup } from '@playwright/test';

const authFile = path.join(__dirname, '../playwright/.clerk/user.json');

setup.describe.configure({ mode: 'serial' });

setup('global setup', async ({}) => {
  await clerkSetup();
});

setup('authenticate', async ({ page }) => {
  // Create a sign-in token via Clerk Backend API (bypasses password/verification)
  const response = await fetch('https://api.clerk.com/v1/sign_in_tokens', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${process.env.CLERK_SECRET_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_id: process.env.E2E_CLERK_USER_ID!,
      expires_in_seconds: 300,
    }),
  });

  const { token } = await response.json();

  // Navigate to sign-in with the ticket token — Clerk auto-authenticates
  await page.goto(`/sign-in?__clerk_ticket=${token}`);

  // Wait for redirect to dashboard
  await page.waitForURL('**/dashboard**', { timeout: 15_000 });

  // Save auth state for all subsequent tests
  await page.context().storageState({ path: authFile });
});
