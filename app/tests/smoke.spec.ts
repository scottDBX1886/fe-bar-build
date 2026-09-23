import { expect, test } from '@playwright/test';

const appUrl = process.env.APP_URL ?? 'http://127.0.0.1:8000';

test('retention advisor shell exposes its governed workflows', async ({ page }) => {
  const token = process.env.DATABRICKS_TOKEN;
  if (token) {
    await page.setExtraHTTPHeaders({ Authorization: `Bearer ${token}` });
  }
  await page.goto(appUrl);

  await expect(page.getByRole('banner')).toBeVisible();
  await expect(page.getByTestId('identity-badge')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Executive Overview' })).toBeVisible();

  await page.getByRole('link', { name: 'Advisor Caseload' }).click();
  await expect(page.getByRole('heading', { name: 'Advisor Caseload' })).toBeVisible();

  await page.getByRole('link', { name: 'Ask Genie' }).click();
  await expect(page.getByRole('heading', { name: 'Ask Genie' })).toBeVisible();
  await expect(page.getByText('Runs with your Databricks permissions', { exact: true })).toBeVisible();
  await expect(page.getByText(/AI-generated.*verify/i)).toBeVisible();
  await expect(page.getByPlaceholder('Ask about student retention')).toBeVisible();
});
