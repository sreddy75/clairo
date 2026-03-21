import { expect, test } from './fixtures/auth';

test.describe('Navigation', () => {
  test('navigates between main pages via sidebar', async ({ page, navigateTo }) => {
    await navigateTo('/dashboard');

    // Navigate to Clients
    await page.getByRole('link', { name: /clients/i }).click();
    await expect(page).toHaveURL(/\/clients/);
    await expect(page.getByRole('heading', { name: /clients/i })).toBeVisible();

    // Navigate to Lodgements
    await page.getByRole('link', { name: /lodgements/i }).click();
    await expect(page).toHaveURL(/\/lodgements/);

    // Navigate back to Dashboard
    await page.getByRole('link', { name: /dashboard/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('command palette navigates to pages', async ({ page, navigateTo }) => {
    await navigateTo('/dashboard');

    // Open command palette
    await page.keyboard.press('Meta+k');
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Search for "clients" and select
    await dialog.getByPlaceholder(/search/i).fill('Clients');
    await dialog.getByRole('option', { name: /^Clients$/i }).click();

    // Should navigate to clients page
    await expect(page).toHaveURL(/\/clients/);
  });

  test('theme toggle works via command palette', async ({ page, navigateTo }) => {
    await navigateTo('/dashboard');

    // Get initial theme
    const htmlElement = page.locator('html');
    const initialTheme = await htmlElement.getAttribute('class');

    // Open command palette and toggle theme
    await page.keyboard.press('Meta+k');
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder(/search/i).fill('theme');
    await dialog.getByRole('option', { name: /toggle theme/i }).click();

    // Theme class should have changed
    const newTheme = await htmlElement.getAttribute('class');
    expect(newTheme).not.toBe(initialTheme);
  });
});
