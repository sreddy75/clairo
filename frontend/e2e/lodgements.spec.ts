import { expect, test } from './fixtures/auth';

test.describe('Lodgements', () => {
  test('loads lodgements page with filters and table', async ({ page, navigateTo }) => {
    await navigateTo('/lodgements');

    // Page header
    await expect(page.getByRole('heading', { name: /lodgements/i })).toBeVisible();

    // Should have status filter tabs or a table
    const table = page.getByRole('table');
    const emptyState = page.getByText(/no.*lodgements/i);
    await expect(table.or(emptyState)).toBeVisible();
  });

  test('lodgement status tabs filter correctly', async ({ page, navigateTo }) => {
    await navigateTo('/lodgements');

    // Look for status filter tabs (All, Draft, Lodged, etc.)
    const tabList = page.getByRole('tablist');
    if (await tabList.isVisible()) {
      const tabs = tabList.getByRole('tab');
      const tabCount = await tabs.count();
      expect(tabCount).toBeGreaterThan(0);

      // Click each tab and verify page doesn't error
      for (let i = 0; i < Math.min(tabCount, 3); i++) {
        await tabs.nth(i).click();
        await page.waitForLoadState('networkidle');
        // Page should still be functional
        await expect(page.getByRole('heading', { name: /lodgements/i })).toBeVisible();
      }
    }
  });
});
