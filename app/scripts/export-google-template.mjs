import { chromium } from '@playwright/test';
import process from 'node:process';

const cdpUrl = process.env.CDP_URL ?? 'http://127.0.0.1:9223';
const presentationId = process.env.PRESENTATION_ID;
const outputPath = process.env.OUTPUT_PATH;

if (!presentationId || !outputPath) {
  throw new Error('PRESENTATION_ID and OUTPUT_PATH are required');
}

const browser = await chromium.connectOverCDP(cdpUrl);
try {
  const pages = browser.contexts().flatMap((context) => context.pages());
  const page = pages.find((candidate) => candidate.url().includes(presentationId));
  if (!page) throw new Error(`No authenticated presentation page found for ${presentationId}`);

  const exportUrl = `https://docs.google.com/presentation/d/${presentationId}/export/pptx`;
  const downloadPromise = page.waitForEvent('download', { timeout: 60_000 });
  await page.goto(exportUrl).catch(() => undefined);
  const download = await downloadPromise;
  await download.saveAs(outputPath);
  process.stdout.write(`${JSON.stringify({ output_path: outputPath, status: 'exported' })}\n`);
} finally {
  await browser.close();
}
