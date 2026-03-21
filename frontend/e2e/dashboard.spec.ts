import { expect, test } from './fixtures/auth';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ navigateTo }) => {
    await navigateTo('/dashboard');
  });

  test('loads dashboard with key sections', async ({ page }) => {
    // Page header
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();

    // Stat cards should be present
    const statCards = page.locator('[class*="grid"] > div').first();
    await expect(statCards).toBeVisible();
  });

  test('sidebar navigation is functional', async ({ page }) => {
    // Sidebar should show navigation items
    await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /clients/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /lodgements/i })).toBeVisible();
  });

  test('command palette opens with keyboard shortcut', async ({ page }) => {
    // Press Cmd+K to open command palette
    await page.keyboard.press('Meta+k');

    // Command palette dialog should appear
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Search input should be focused
    const searchInput = dialog.getByPlaceholder(/search/i);
    await expect(searchInput).toBeVisible();

    // Close with Escape
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
  });
});
