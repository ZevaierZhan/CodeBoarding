"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {pathToFileURL} = require("node:url");

async function main() {
  const [modulePath, executablePath, directory] = process.argv.slice(2);
  const {chromium} = require(path.resolve(modulePath));
  const browser = await chromium.launch({executablePath, headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1600,height:1000}});
    const errors = [];
    page.on("pageerror", error => errors.push(String(error)));
    const observations = [];
    for (const stage of ["before", "after"]) {
      await page.goto(pathToFileURL(path.resolve(directory, `${stage}.html`)).href);
      const model = await page.locator("#model-data").evaluate(node => JSON.parse(node.textContent).model);
      const topic = model.scenarios.find(s => s.analysis_kind === "comparison");
      const operation = model.scenarios.find(s => s.analysis_kind !== "comparison" && s.steps.some(st => Object.keys(st.facet_checks || {}).length));
      assert.ok(topic && operation);
      await page.locator("#scenario").selectOption(topic.id);
      assert.match(await page.locator("#playback-status").innerText(), /Independent explanations/);
      assert.doesNotMatch(await page.locator("#nodes").innerText(), /Current step/);
      await page.locator("#inspect-business").click();
      assert.match(await page.locator("#detail").innerText(), /comparison/);
      for (const id of ["play", "next", "back", "reset"]) assert.equal(await page.locator(`#${id}`).isDisabled(), true);
      await page.locator("#steps button").last().click();
      assert.match(await page.locator("#incoming").innerText(), /No execution order/);
      await page.screenshot({path:path.join(directory, `${stage}-topic.png`)});
      await page.locator("#scenario").selectOption(operation.id);
      const step = operation.steps.find(st => Object.keys(st.facet_checks || {}).length);
      await page.locator("#steps button").nth(operation.order.indexOf(step.id)).click();
      assert.match(await page.locator("#detail").innerText(), /Authored interpretations/);
      for (const explanation of Object.values(step.facet_checks)) assert.ok((await page.locator("#detail").innerText()).includes(explanation));
      if (operation.facet_order.some(label => !step.facet_checks[label])) {
        assert.match(await page.locator("#detail").innerText(), /Not examined \/ unknown/);
      }
      const evidence = page.locator("#detail details[data-binding-id]").first();
      assert.ok(await evidence.count());
      await evidence.locator("summary").first().click();
      assert.match(await evidence.innerText(), /Referenced evidence|evidence version|source root|Source root/);
      await page.locator("#expand-all").click();
      await page.locator("#collapse-all").click();
      await page.locator("#reset").click();
      const choices = page.locator("#choices button");
      if (await choices.count()) {
        const entry = await page.locator("#current").innerText();
        await choices.first().click();
        assert.equal(await page.locator("#back").isDisabled(), false);
        await page.locator("#back").click();
        assert.equal(await page.locator("#current").innerText(), entry);
      }
      await page.screenshot({path:path.join(directory, `${stage}-operation.png`)});
      observations.push({stage, revision:model.revision, comparisons:model.scenarios.filter(s => s.analysis_kind === "comparison").length,
        operationFacetsVisible:true, topicPlaybackDisabled:true, evidenceAccessible:true, switchAndBack:true});
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(directory, "browser.json"), JSON.stringify({engine:"Chrome/Playwright",observations,pageErrors:errors},null,2));
    console.log("Chrome topic, operation, facet, evidence and history checks passed");
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
