const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');

const source = path.resolve(process.argv[2]);
const root = fs.mkdtempSync(path.resolve('temp/p2-render-negatives-'));
const html = fs.readFileSync(path.join(source, 'html/overview.html'), 'utf8');
const baseline = spawnSync('git', ['show', 'a57e2e773a7e79971e202ca2fafe903e5347c399:docs/design/external-agent-p0/check-render.cjs'], { encoding: 'utf8' });
assert.equal(baseline.status, 0, baseline.stderr);
const oldChecker = path.join(root, 'old-check-render.cjs');
fs.writeFileSync(oldChecker, baseline.stdout);
const cases = {
  missing_library: html.replace(/<script src="https:\/\/unpkg.com\/cytoscape@[^\"]+"><\/script>/, ''),
  initialization_exception: html.replace('const cy = cytoscape({', "throw new Error('P0 injected initialization failure');\nconst cy = cytoscape({"),
};
const results = [];
for (const [name, content] of Object.entries(cases)) {
  assert.notEqual(content, html, `Injection missed ${name}`);
  assert.equal((content.match(/class="component"/g) || []).length, 4);
  const output = path.join(root, name);
  fs.mkdirSync(path.join(output, 'html'), { recursive: true });
  fs.writeFileSync(path.join(output, 'html/overview.html'), content);
  const old = spawnSync(process.execPath, [oldChecker, output], { encoding: 'utf8', timeout: 90000 });
  fs.writeFileSync(path.join(output, 'old.log'), old.stdout + old.stderr);
  assert.equal(old.status, 0, `Old checker failed for another reason: ${old.stderr}`);
  const current = spawnSync(process.execPath, [path.join(__dirname, 'check-render.cjs'), output], { encoding: 'utf8', timeout: 90000 });
  fs.writeFileSync(path.join(output, 'current.log'), current.stdout + current.stderr);
  assert.equal(current.status, 1, `Current checker did not reject ${name}: ${current.stderr}`);
  const report = JSON.parse(fs.readFileSync(path.join(output, 'browser-results.json'), 'utf8'));
  assert.equal(report.component_details, 4);
  assert.equal(report.status, 'FAIL');
  results.push({ name, test_status: 'PASS', old_checker_exit: old.status, checker_exit: current.status, report });
}
const normal = spawnSync(process.execPath, [path.join(__dirname, 'check-render.cjs'), source], { encoding: 'utf8', timeout: 90000 });
assert.equal(normal.status, 0, normal.stderr);
const summary = { status: 'PASS', cases: results, normal_checker_exit: normal.status };
fs.writeFileSync(path.join(source, 'browser-negative-results.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary));
