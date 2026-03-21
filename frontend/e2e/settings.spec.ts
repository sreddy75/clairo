import { expect, test } from './fixtures/auth';

test.describe('Settings', () => {
  test('loads settings page', async ({ page, navigateTo }) => {
    await navigateTo('/settings');

    // Settings page should have a heading
    await expect(page.getByRole('heading', { name: /settings/i })).toBeVisible();
  });

  test('settings sub-pages are accessible', async ({ page, navigateTo }) => {
    // Billing
    await navigateTo('/settings/billing');
    await expect(page.getByText(/billing/i).first()).toBeVisible();

    // Integrations
    await navigateTo('/settings/integrations');
    await expect(page.getByText(/integration/i).first()).toBeVisible();
  });
});
