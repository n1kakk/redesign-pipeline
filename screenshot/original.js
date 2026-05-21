// Take screenshot of the original site for vision comparison
// Usage: node screenshot_originals.js <site_url>
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const siteUrl = process.argv[2] || 'https://www.rpsplanadvisors.com';
const refDir = path.join(__dirname, '..', 'outputs', 'original_ref');
fs.mkdirSync(refDir, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  console.log(`[screenshot] Navigating to ${siteUrl}...`);
  try {
    await page.goto(siteUrl, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    const fullpagePath = path.join(refDir, 'fullpage.png');
    await page.screenshot({ path: fullpagePath, fullPage: true });
    console.log(`[screenshot] Fullpage saved (${(fs.statSync(fullpagePath).size/1024).toFixed(0)} KB)`);

    const viewportPath = path.join(refDir, 'viewport.png');
    await page.screenshot({ path: viewportPath });
    console.log(`[screenshot] Viewport saved (${(fs.statSync(viewportPath).size/1024).toFixed(0)} KB)`);
  } catch (err) {
    console.error(`[screenshot] Error: ${err.message}`);
  }

  await browser.close();
  console.log('[screenshot] Done!');
})().catch(err => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
