const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.P0_PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const output = path.resolve(process.argv[2]);
  const browser = await chromium.launch({ headless: true, channel: process.env.P0_BROWSER_CHANNEL || undefined });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.join(output, 'html', 'overview.html')).href, { waitUntil: 'networkidle', timeout: 45000 });
    const components = page.locator('.component');
    if (await components.count() !== 4) throw new Error('Expected four component details');
    const details = await components.allInnerTexts();
    if (!details.every(item => item.includes('P0 grouping rationale'))) throw new Error('Rationale not visible');
    if (!details.some(item => item.includes('calculate_total'))) throw new Error('Source anchor not visible');
    if (details.some(item => item.includes('P0_INDEPENDENT_RATIONALE'))) throw new Error('Unexpected independent rationale');
    const result = {
      component_details: details.length,
      source_reference_texts: await page.locator('.references li').count(),
      clickable_source_links: await page.locator('.references a').count(),
      graph_canvases: await page.locator('#cy canvas').count(),
      page_errors: errors,
      playwright: require(path.join(process.env.P0_PLAYWRIGHT_MODULE || 'playwright', 'package.json')).version,
      chromium: browser.version(),
    };
    await page.screenshot({ path: path.join(output, 'renderer.png'), fullPage: true });
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
