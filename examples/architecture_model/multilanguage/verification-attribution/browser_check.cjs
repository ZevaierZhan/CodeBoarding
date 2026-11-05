"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {pathToFileURL} = require("node:url");

async function main() {
  const [modulePath, executablePath, htmlPath, output] = process.argv.slice(2);
  const {chromium} = require(path.resolve(modulePath));
  const browser = await chromium.launch({executablePath, headless:true});
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(String(error)));
  try {
    await page.goto(pathToFileURL(path.resolve(htmlPath)).href);
    await page.locator("#metadata").click();
    await page.getByRole("button", {name:"Inspect binding frontend", exact:true}).click();
    await page.locator('[data-binding-id="frontend"] > summary').click();
    const record = page.locator('[data-record-id="check"]');
    await record.locator("summary").first().click();
    const text = await record.innerText();
    assert.match(text, /legacy_unscoped/);
    assert.match(text, /"evidence": \[\]/);
    assert.match(text, /"uncovered_binding_ids": \[\s*"frontend"/);
    assert.match(text, /not runtime proof/);
    assert.match(await record.locator("summary").first().innerText(), /planned/);
    assert.deepEqual(errors, []);
    fs.writeFileSync(output, JSON.stringify({
      passed:true, browser:"Chrome via Playwright", errors, visibleRecord:text,
      checks:["unknown implicit evidence", "uncovered frontend", "planned retained", "no runtime promotion"]
    }, null, 2));
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
