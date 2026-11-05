"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const crypto = require("node:crypto");
const path = require("node:path");
const {pathToFileURL} = require("node:url");

async function main() {
  const [modulePath, executablePath, modelDir, legacyDir, output] = process.argv.slice(2);
  const {chromium} = require(path.resolve(modulePath));
  const modelFile = path.join(modelDir, "model.json");
  const before = crypto.createHash("sha256").update(fs.readFileSync(modelFile)).digest("hex");
  const browser = await chromium.launch({executablePath, headless:true});
  const page = await browser.newPage({viewport:{width:1600,height:1000}});
  const errors = [];
  page.on("pageerror", error => errors.push(String(error)));
  await page.goto(pathToFileURL(path.resolve(modelDir,"index.html")).href);
  await page.locator("#relations button").filter({hasText:"Candidate Tauri"}).click();
  const partial = page.locator('[data-record-id="p2-frontend-source-check"]');
  await partial.locator("summary").first().click();
  assert.match(await partial.innerText(), /declared_partial/);
  assert.match(await partial.innerText(), /uncovered_binding_ids/);
  assert.match(await partial.innerText(), /registration/);
  assert.match(await partial.innerText(), /not runtime proof/);
  const planned = page.locator('[data-record-id="p2-planned-ipc-check"]');
  assert.match(await planned.locator("summary").first().innerText(), /planned/);
  await planned.locator("summary").first().click();
  assert.match(await planned.innerText(), /backend/);
  assert.match(await planned.innerText(), /frontend/);
  assert.match(await planned.innerText(), /declared_referenced_evidence/);
  await page.screenshot({path:output+".png"});
  const legacy = JSON.parse(fs.readFileSync(path.join(legacyDir,"result.json"),"utf8"));
  const observations = [];
  for (const stage of ["before","after-frontend","after-backend"]) {
    await page.goto(pathToFileURL(path.resolve(legacyDir,stage+".html")).href);
    await page.locator("#metadata").click();
    await page.getByRole("button",{name:"Inspect binding legacy-binding",exact:true}).click();
    const summaries = await page.locator("#detail summary").allTextContents();
    assert.ok(summaries.some(text => text.includes("latest target")));
    assert.ok(summaries.some(text => text.includes("older target")));
    assert.match(await page.locator("#detail").textContent(), new RegExp(legacy.legacy_latest));
    observations.push({stage,legacy_target:legacy.legacy_latest,latest_and_older_present:true});
    for (const root of (stage === "after-backend" ? ["frontend","backend"] : stage === "after-frontend" ? ["frontend"] : [])) {
      await page.locator("#metadata").click();
      await page.getByRole("button",{name:`Inspect binding ${root}-binding`,exact:true}).click();
      const rootSummaries = await page.locator("#detail summary").allTextContents();
      assert.ok(rootSummaries.some(text=>text.includes("latest target")));
      assert.ok(!rootSummaries.some(text=>text.includes("older target")));
      observations.push({stage,root,independent_latest_target:true});
    }
  }
  await page.goto(pathToFileURL(path.resolve(legacyDir,"../legacy-control/fixed-unknown.html")).href);
  await page.locator("#metadata").click();
  await page.getByRole("button",{name:"Inspect binding legacy-binding",exact:true}).click();
  const unknown = await page.locator("#detail summary").allTextContents();
  assert.ok(unknown.some(text=>text.includes("target latestness unknown")));
  assert.ok(!unknown.some(text=>text.includes("older target")));
  assert.deepEqual(errors,[]);
  await browser.close();
  const after = crypto.createHash("sha256").update(fs.readFileSync(modelFile)).digest("hex");
  assert.equal(before,after);
  fs.writeFileSync(output+".json",JSON.stringify({partial_executed_is_not_bilateral:true,bilateral_remains_planned:true,lost_legacy_target_is_unknown_not_older:true,legacy_observations:observations,model_sha256_before:before,model_sha256_after:after,javascript_errors:errors},null,2)+"\n");
}
main().catch(error=>{console.error(error);process.exitCode=1;});
