import { chromium } from '@playwright/test';
import process from 'node:process';

const cdpUrl = process.env.CDP_URL ?? 'http://127.0.0.1:9222';
const appHost = 'dev-student-retention-7474646471228909.aws.databricksapps.com';
const browser = await chromium.connectOverCDP(cdpUrl);

try {
  const pages = browser.contexts().flatMap((context) => context.pages());
  const page = pages.find((candidate) => candidate.url().includes(appHost));
  if (!page) throw new Error(`No authenticated app page found for ${appHost}`);

  await page.bringToFront();
  await page.getByRole('banner').waitFor({ state: 'visible' });
  await page.getByTestId('identity-badge').waitFor({ state: 'visible' });
  await page.getByRole('heading', { name: 'Executive Overview' }).waitFor({ state: 'visible' });

  await page.getByRole('link', { name: 'Advisor Caseload' }).click();
  await page.getByRole('heading', { name: 'Advisor Caseload' }).waitFor({ state: 'visible' });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Advisor Caseload' }).waitFor({ state: 'visible' });

  await page.getByRole('link', { name: 'Ask Genie' }).click();
  await page.getByRole('heading', { name: 'Ask Genie' }).waitFor({ state: 'visible' });
  await page.getByText('Runs with your Databricks permissions', { exact: true }).waitFor({ state: 'visible' });
  await page
    .getByText(/AI-generated.*verify/i)
    .first()
    .waitFor({ state: 'visible' });
  await page.getByPlaceholder('Ask about student retention').waitFor({ state: 'visible' });

  const consoleErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });

  process.stdout.write(
    `${JSON.stringify({
      app_url: page.url(),
      executive_overview: 'passed',
      advisor_caseload_navigation: 'passed',
      advisor_caseload_refresh: 'passed',
      embedded_genie_trust_state: 'passed',
      console_errors_after_checks: consoleErrors,
    })}\n`
  );
} finally {
  await browser.close();
}
