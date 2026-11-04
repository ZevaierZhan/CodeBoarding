const {test} = require('node:test');
const assert = require('node:assert/strict');
const {Player,visibleAncestor,projectedEdges,hierarchy} = require('../../architecture_model/viewer_assets/engine.js');
const components = [{id:'root',parent_id:''},{id:'shared',parent_id:'root'},{id:'leaf',parent_id:'shared'}];
const scenario = {entry_step_id:'a',order:['b','c','a'],steps:[
  {id:'a',component_ids:['leaf']},{id:'b',component_ids:['shared']},{id:'c',component_ids:['root']}],
  transitions:[{source_id:'a',target_id:'c',kind:'branch',condition:'explicit'},
    {source_id:'a',target_id:'b',kind:'branch',condition:'other'},
    {source_id:'c',target_id:'c',kind:'loop',condition:'repeat'},
    {source_id:'c',target_id:'a',kind:'return',condition:'exit'}]};
test('collapse projects references without changing stable objects or order',()=>{
  const model = {components,relations:[{id:'r',source_id:'leaf',target_id:'shared'}]};
  const before=JSON.stringify([model,scenario]);
  assert.equal(visibleAncestor('leaf',components,new Set()),'root');
  assert.equal(visibleAncestor('leaf',components,new Set(['root'])),'shared');
  const edges=projectedEdges(model,scenario,new Set());
  assert.equal(edges[0].relation_id,'r');
  assert.deepEqual(edges[0].component_ids,['leaf','shared']);
  assert.equal(edges[1].source_step_id,'a');
  assert.equal(edges[1].target_step_id,'c');
  assert.equal(edges[1].source,'root');
  assert.equal(JSON.stringify([model,scenario]),before);
  assert.deepEqual(hierarchy(components).map(r=>r.index),[0,1,2]);
});
test('play follows explicit transitions, branches and actual history, never display order',()=>{
  const player=new Player(scenario);
  assert.equal(player.current,'a');
  assert.equal(player.autoChoice(),null);
  assert.equal(player.forward(1),true);
  assert.equal(player.current,'b');
  assert.equal(player.forward(0),false);
  assert.deepEqual(player.choices(),[]);
  assert.equal(player.back(),true);
  assert.equal(player.current,'a');
  player.forward(0);
  assert.equal(player.current,'c');
  assert.equal(player.autoChoice(),null);
  player.forward(2);
  assert.equal(player.current,'c');
  player.forward(3);
  assert.equal(player.current,'a');
  player.back();assert.equal(player.current,'c');assert.equal(player.incoming,2);
  player.reset();assert.equal(player.current,'a');assert.deepEqual(player.history,[]);
});
test('autoplay stops on a single loop and on cycles even when mislabeled next',()=>{
  const loop=new Player({...scenario,entry_step_id:'c',transitions:[scenario.transitions[2]]});
  assert.equal(loop.autoChoice(),null);
  const cycle=new Player({...scenario,transitions:[{source_id:'a',target_id:'c',kind:'next'},{source_id:'c',target_id:'a',kind:'next'}]});
  cycle.forward(cycle.autoChoice());
  assert.equal(cycle.autoChoice(),null);
});
test('direct inspection is explicit and starts a fresh path; empty models are playable safely',()=>{
  const player=new Player(scenario);player.forward(0);
  assert.equal(player.inspectStep('absent'),false);
  assert.equal(player.inspectStep('b'),true);
  assert.equal(player.back(),false);
  assert.equal(player.incoming,null);
  const empty=new Player(null);assert.equal(empty.current,'');assert.deepEqual(empty.choices(),[]);
});
