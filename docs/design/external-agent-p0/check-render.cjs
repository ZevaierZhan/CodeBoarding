const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.P0_PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const output = path.resolve(process.argv[2]);
  const result = { status: 'RUNNING', page_errors: [], console_errors: [], failed_dependencies: [] };
  fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2));
  let browser;
  try {
    browser = await chromium.launch({ headless: true, channel: process.env.P0_BROWSER_CHANNEL || undefined });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
    const page = await context.newPage();
    page.on('pageerror', error => result.page_errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') result.console_errors.push(message.text()); });
    page.on('requestfailed', request => {
      if (request.resourceType() === 'script') result.failed_dependencies.push(request.url());
    });
    page.on('response', response => {
      if (response.request().resourceType() === 'script' && !response.ok()) result.failed_dependencies.push(response.url());
    });
    await page.goto(pathToFileURL(path.join(output, 'html', 'overview.html')).href, { waitUntil: 'networkidle', timeout: 45000 });
    const components = page.locator('.component');
    assert.equal(await components.count(), 4, 'Expected four component details');
    const details = await components.allInnerTexts();
    assert(details.every(item => item.includes('P0 grouping rationale')), 'Rationale not visible');
    assert(details.some(item => item.includes('calculate_total')), 'Source anchor not visible');
    assert(!details.some(item => item.includes('P0_INDEPENDENT_RATIONALE')), 'Unexpected independent rationale');
    result.component_details = details.length;
    result.source_reference_texts = await page.locator('.references li').count();
    result.clickable_source_links = await page.locator('.references a').count();
    assert.equal(result.source_reference_texts, 8);
    await page.waitForFunction(() => {
      // Read-only probe of the actual core registered by Cytoscape on its container.
      const cy = document.getElementById('cy')?._cyreg?.cy;
      return cy && cy.isReady() && !cy.destroyed() && cy.nodes().length > 0 &&
        cy.nodes().every(node => Number.isFinite(node.renderedPosition('x')) && node.renderedWidth() > 0);
    }, null, { timeout: 15000 });
    await page.locator('#cy').waitFor({ state: 'visible', timeout: 15000 });
    result.graph = await page.evaluate(() => {
      const element = document.getElementById('cy');
      const cy = element._cyreg.cy;
      const rect = element.getBoundingClientRect();
      return {
        width: rect.width, height: rect.height, headless: cy.headless(),
        nodes: cy.nodes().map(node => ({ id: node.id(), visible: node.visible(), box: node.renderedBoundingBox() })),
        edges: cy.edges().map(edge => ({ source: edge.source().id(), target: edge.target().id(), visible: edge.visible(), box: edge.renderedBoundingBox() })),
        painted_surface: [...element.querySelectorAll('canvas')].some(canvas => {
          const box = canvas.getBoundingClientRect();
          return canvas.width > 0 && canvas.height > 0 && box.width > 0 && box.height > 0;
        }),
      };
    });
    const graph = result.graph;
    assert(graph.width > 0 && graph.height > 0 && !graph.headless && graph.painted_surface, 'Graph has no visible drawing surface');
    assert.deepEqual(graph.nodes.map(node => node.id).sort(), [1, 2, 3, 4].map(i => `Order_responsibility_${i}`));
    assert.deepEqual(graph.edges.map(edge => `${edge.source}->${edge.target}`).sort(), [
      'Order_responsibility_1->Order_responsibility_2',
      'Order_responsibility_2->Order_responsibility_3',
      'Order_responsibility_2->Order_responsibility_4',
    ]);
    for (const item of [...graph.nodes, ...graph.edges]) {
      assert(item.visible && item.box.w > 0 && item.box.h > 0, 'Invisible graph element');
      assert([item.box.x1, item.box.y1, item.box.x2, item.box.y2].every(Number.isFinite));
      assert(item.box.x2 > 0 && item.box.y2 > 0 && item.box.x1 < graph.width && item.box.y1 < graph.height, 'Graph element outside viewport');
    }
    await page.screenshot({ path: path.join(output, 'renderer.png'), fullPage: true });
    result.playwright = require(path.join(process.env.P0_PLAYWRIGHT_MODULE || 'playwright', 'package.json')).version;
    result.chromium = browser.version();
    await context.close();
    assert.deepEqual(result.page_errors, [], 'Page script exception');
    assert.deepEqual(result.console_errors, [], 'Page console error');
    assert.deepEqual(result.failed_dependencies, [], 'Missing script dependency');
    result.status = 'PASS';
  } catch (error) {
    result.status = 'FAIL';
    result.error = String(error);
    throw error;
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
