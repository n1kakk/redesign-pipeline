// Take redesign screenshots for a site - uses file:// protocol
// Usage: node screenshot_redesign.js <site_name>
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const siteName = process.argv[2] || 'akrecapital';
const baseDir = path.join(__dirname, '..', 'outputs', siteName);
const htmlPath = path.join(baseDir, 'final.html');
const outDir = path.join(baseDir, 'screenshots', 'redesign');

fs.mkdirSync(outDir, { recursive: true });

(async () => {
  console.log(`[${siteName}] HTML: ${htmlPath}`);
  if (!fs.existsSync(htmlPath)) {
    console.error(`[${siteName}] HTML not found at ${htmlPath}`);
    process.exit(1);
  }

  const html = fs.readFileSync(htmlPath, 'utf-8');
  const fileUrl = 'file://' + htmlPath.replace(/\\/g, '/');

  const browser = await chromium.launch({ headless: true });

  // Desktop fullpage + viewport
  const desktopContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await desktopContext.newPage();

  console.log(`[${siteName}] Rendering desktop from ${fileUrl}...`);
  await page.goto(fileUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForTimeout(5000);

  await page.screenshot({ path: path.join(outDir, 'fullpage.png'), fullPage: true });
  const fpSize = fs.statSync(path.join(outDir, 'fullpage.png')).size;
  console.log(`[${siteName}] Fullpage saved (${(fpSize/1024).toFixed(0)} KB)`);

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(outDir, 'viewport.png') });
  console.log(`[${siteName}] Viewport saved`);

  await desktopContext.close();

  // Mobile
  const mobileContext = await browser.newContext({
    viewport: { width: 375, height: 812 },
    deviceScaleFactor: 2,
  });
  const mobilePage = await mobileContext.newPage();

  console.log(`[${siteName}] Rendering mobile...`);
  await mobilePage.goto(fileUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await mobilePage.waitForTimeout(2000);
  await mobilePage.evaluate(() => window.scrollTo(0, 0));
  await mobilePage.waitForTimeout(500);

  await mobilePage.screenshot({
    path: path.join(outDir, 'mobile.png'),
    fullPage: true,
  });
  console.log(`[${siteName}] Mobile saved`);

  await mobileContext.close();
  await browser.close();

  console.log(`[${siteName}] All screenshots done!`);
})().catch(err => {
  console.error(`[${siteName}] Error: ${err.message}`);
  process.exit(1);
});
