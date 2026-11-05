/* Exercise the saved M4 document over localhost; never uses file: navigation. */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const directory = path.resolve(process.argv[2] || __dirname);
  const evidence = path.resolve(process.argv[3] || path.join(directory, 'browser'));
  fs.mkdirSync(evidence, {recursive:true});
  const modelPath = path.join(directory, 'model.json');
  const digest = () => crypto.createHash('sha256').update(fs.readFileSync(modelPath)).digest('hex');
  const before = digest();
  const stored = JSON.parse(fs.readFileSync(modelPath, 'utf8'));
  const server = http.createServer((request, response) => {
    if (request.url !== '/index.html') {response.writeHead(404).end(); return;}
    response.writeHead(200, {'Content-Type':'text/html; charset=utf-8'});
    response.end(fs.readFileSync(path.join(directory, 'index.html')));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  const errors = [], external = [], checks = [];
  try {
    browser = await chromium.launch({channel:'chrome', headless:true});
    const context = await browser.newContext({viewport:{width:1500,height:1050}, reducedMotion:'reduce'});
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(String(error)));
    page.on('request', request => {if (!request.url().startsWith('http://127.0.0.1:')) external.push(request.url());});
    await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);
    await page.locator('.node').first().waitFor();
    assert.equal(await page.locator('#scenario option').count(), 2);
    const payload = await page.locator('#model-data').textContent();
    assert.equal(JSON.parse(payload).model.id, stored.id);
    assert.equal(JSON.parse(payload).model.revision, stored.revision);
    checks.push('HTML model identity/revision equals saved model; two businesses render');
    await page.locator('#collapse-all').click();
    assert.equal(await page.locator('.node').count(), 1);
    await page.locator('#expand-all').click();
    assert.equal(await page.locator('.node').count(), stored.components.length);
    checks.push('Hierarchy collapses and expands without replacing component IDs');
    await page.locator('#scenario').selectOption('read-to-html');
    await page.locator('#reset').click();
    assert.match(await page.locator('#current').textContent(), /html-dispatch/);
    await page.locator('#next').click();
    assert.match(await page.locator('#current').textContent(), /html-read/);
    await page.locator('#scenario').selectOption('agent-submits-patch');
    await page.locator('#reset').click();
    assert.match(await page.locator('#current').textContent(), /patch-submit/);
    await page.locator('#scenario').selectOption('read-to-html');
    assert.match(await page.locator('#current').textContent(), /html-read/);
    await page.locator('#play').click();
    await page.waitForTimeout(6000);
    assert.match(await page.locator('#current').textContent(), /html-response/);
    checks.push('Business switching preserves position; explicit next and automatic success-path playback reach the modeled endpoint');
    await page.locator('#tree button.object').filter({hasText:'Offline document projection'}).click();
    assert.match(await page.locator('#detail').textContent(), /hard links|hard-link/);
    const binding = page.locator('#detail details[data-binding-id="e-export-html"]');
    await binding.locator('summary').first().click();
    assert.match(await binding.textContent(), /Exact file SHA-256 matched/);
    assert.match(await binding.textContent(), /export_html/);
    await page.screenshot({path:path.join(evidence, 'source-evidence.png'), fullPage:true});
    await page.locator('#metadata').click();
    assert.match(await page.locator('#detail').textContent(), /planned-business-runtime/);
    checks.push('Hash-verified source, boundary rationale, maintenance history and planned/executed records are inspectable');
    await page.screenshot({path:path.join(evidence, 'metadata.png'), fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path:path.join(evidence, 'mobile.png'), fullPage:true});
    assert.deepEqual(errors, []);
    assert.deepEqual(external, []);
    assert.equal(digest(), before);
    checks.push('Mobile has no page overflow; no page errors or external requests; model bytes unchanged');
    fs.writeFileSync(path.join(evidence, 'results.json'), JSON.stringify({
      browser:await browser.version(), protocol:'localhost HTTP (no file: navigation)',
      model_id:stored.id, revision:stored.revision, checks, errors, external_requests:external,
      model_sha256:before
    }, null, 2) + '\n');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
