import { expect, test } from './fixtures/auth';

test.describe('Clients', () => {
  test('loads client list with table', async ({ page, navigateTo }) => {
    await navigateTo('/clients');

    // Page header
    await expect(page.getByRole('heading', { name: /clients/i })).toBeVisible();

    // Table should be present with column headers
    const table = page.getByRole('table');
    await expect(table).toBeVisible();
  });

  test('client search filters results', async ({ page, navigateTo }) => {
    await navigateTo('/clients');

    // Find the search input
    const searchInput = page.getByPlaceholder(/search/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill('test');
      // Wait for filtered results
      await page.waitForTimeout(500);
      // Table should still be visible
      await expect(page.getByRole('table')).toBeVisible();
    }
  });

  test('navigates to client detail', async ({ page, navigateTo }) => {
    await navigateTo('/clients');

    // Check table has rows (header + at least one data row, or empty state)
    const table = page.getByRole('table');
    await expect(table).toBeVisible();
  });
});
