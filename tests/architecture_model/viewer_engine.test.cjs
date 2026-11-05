const {test} = require('node:test');
const assert = require('node:assert/strict');
const {Player,visibleAncestor,componentProjection,projectedEdges,hierarchy} = require('../../architecture_model/viewer_assets/engine.js');
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
test('shared projection matches ancestor semantics and preserves original edge references for every collapse state',()=>{
  const forest=[...components,{id:'other',parent_id:''},{id:'child',parent_id:'other'}];
  const model={components:forest,relations:[{id:'r',source_id:'leaf',target_id:'child'}]};
  const before=JSON.stringify(model);
  for(const ordered of [forest,[...forest].reverse()]) {
    for(const expanded of [new Set(),new Set(['root']),new Set(['shared']),new Set(['root','shared','other'])]) {
      const projection=componentProjection(ordered,expanded);
      for(const c of forest) assert.equal(projection.visibleById.get(c.id),visibleAncestor(c.id,forest,expanded));
      for(const visible of forest.filter(c=>projection.visibleById.get(c.id)===c.id)) {
        assert.equal(projection.hiddenCounts.get(visible.id)||0,forest.filter(c=>c.id!==visible.id&&visibleAncestor(c.id,forest,expanded)===visible.id).length);
      }
      const edges=projectedEdges(model,scenario,expanded,projection);
      assert.deepEqual(edges[0].component_ids,['leaf','child']);
      assert.equal(edges[0].relation_id,'r');assert.equal(edges[0].source,projection.visibleById.get('leaf'));
      assert.equal(edges[1].source_step_id,'a');assert.equal(edges[1].target_step_id,'c');
    }
  }
  assert.equal(JSON.stringify(model),before);
});
test('projection handles deep chains and out-of-order parents without changing identities',()=>{
  const chain=Array.from({length:2000},(_,i)=>({id:`n${i}`,parent_id:i?`n${i-1}`:''})).reverse();
  const folded=componentProjection(chain,new Set());
  assert.equal(folded.visibleById.get('n1999'),'n0');assert.equal(folded.hiddenCounts.get('n0'),1999);
  const open=componentProjection(chain,new Set(chain.map(c=>c.id)));
  assert.equal(open.visibleById.get('n1999'),'n1999');assert.equal(open.hiddenCounts.size,0);
  assert.equal(componentProjection([],new Set()).visibleById.size,0);
});
