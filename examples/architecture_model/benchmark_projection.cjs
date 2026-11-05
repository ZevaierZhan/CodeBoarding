const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {execFileSync} = require('node:child_process');
const {performance} = require('node:perf_hooks');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const revision = 'edf00712ffd3c605794c1ce76345aab7094f917c';
function load(source) { return new Function('module', source + ';return module.exports;')({exports:{}}); }
const before = load(execFileSync('git',['show',`${revision}:architecture_model/viewer_assets/engine.js`],{cwd:root,encoding:'utf8'}));
const after = load(fs.readFileSync(path.join(root,'architecture_model/viewer_assets/engine.js'),'utf8'));
const measurements = [];
for (const count of [100,200,400,800]) {
  const components = Array.from({length:count},(_,i)=>({id:`c${i}`,parent_id:i?'c0':''}));
  const rows = before.hierarchy(components), expanded = new Set(components.map(c=>c.id));
  const legacy = () => rows.filter(r=>before.visibleAncestor(r.component.id,components,expanded)===r.component.id)
    .map(({component})=>[component.id,rows.filter(r=>r.component.id!==component.id && before.visibleAncestor(r.component.id,components,expanded)===component.id).length]);
  const started = performance.now();
  const expected = legacy(), beforeMs = performance.now()-started;
  if (!after.componentProjection) { measurements.push({components:count,before_ms:beforeMs}); continue; }
  const optimizedStarted = performance.now();
  const projection = after.componentProjection(components,expanded);
  const actual = rows.filter(r=>projection.visibleById.get(r.component.id)===r.component.id)
    .map(({component})=>[component.id,projection.hiddenCounts.get(component.id)||0]);
  const afterMs = performance.now()-optimizedStarted;
  assert.deepEqual(actual,expected);
  const model = {components,relations:[{id:'r',source_id:'c1',target_id:`c${count-1}`}]};
  assert.deepEqual(after.projectedEdges(model,null,expanded,projection),before.projectedEdges(model,null,expanded));
  measurements.push({components:count,before_ms:beforeMs,after_ms:afterMs,speedup:beforeMs/afterMs,equivalent:true});
}
const result={baseline:revision,node:process.version,platform:`${os.platform()} ${os.release()}`,cpu:os.cpus()[0].model,
  scope:'Isolated visible-node/hidden-count computation, same fully expanded star input; one sample per size, not full browser performance or a timing gate',measurements};
if(process.argv[2]) fs.writeFileSync(process.argv[2],JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));
