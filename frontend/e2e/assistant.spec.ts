import { expect, test } from './fixtures/auth';

test.describe('AI Assistant', () => {
  test('loads assistant page with query mode selection', async ({ page, navigateTo }) => {
    await navigateTo('/assistant');

    // Should show the "What would you like to ask?" heading
    await expect(page.getByText('What would you like to ask?')).toBeVisible();

    // Should show query mode cards
    await expect(page.getByText('General Question')).toBeVisible();
    await expect(page.getByText('Client-Specific')).toBeVisible();
  });

  test('can select a query mode', async ({ page, navigateTo }) => {
    await navigateTo('/assistant');

    // Click the General Question card
    await page.getByText('General Question').click();

    // Should transition to the chat interface (wait for any input or chat UI)
    await page.waitForTimeout(1000);
  });
});
