/* Pure presentation and playback state; never mutates model objects. */
"use strict";
const ArchitectureView = (() => {
  function visibleAncestor(id, components, expanded) {
    const byId = new Map(components.map(c => [c.id, c]));
    let visible = id;
    let current = byId.get(id);
    while (current && current.parent_id) {
      if (!expanded.has(current.parent_id)) visible = current.parent_id;
      current = byId.get(current.parent_id);
    }
    return visible;
  }
  function hierarchy(components) {
    const children = new Map();
    for (const component of components) {
      if (!children.has(component.parent_id)) children.set(component.parent_id, []);
      children.get(component.parent_id).push(component);
    }
    const rows = [];
    function visit(parent, depth) {
      for (const component of children.get(parent) || []) {
        rows.push({component, depth, index: rows.length});
        visit(component.id, depth + 1);
      }
    }
    visit("", 0);
    return rows;
  }
  function projectedEdges(model, scenario, expanded) {
    const project = id => visibleAncestor(id, model.components, expanded);
    const edges = model.relations.map(r => ({
      source: project(r.source_id), target: project(r.target_id),
      relation_id: r.id, component_ids: [r.source_id, r.target_id], kind: "relation"
    }));
    if (!scenario) return edges;
    const steps = new Map(scenario.steps.map(s => [s.id, s]));
    scenario.transitions.forEach((transition, index) => {
      for (const source of steps.get(transition.source_id).component_ids) {
        for (const target of steps.get(transition.target_id).component_ids) {
          edges.push({source: project(source), target: project(target), kind: transition.kind,
            source_step_id: transition.source_id, target_step_id: transition.target_id,
            transition_index: index, component_ids: [source, target]});
        }
      }
    });
    return edges;
  }
  class Player {
    constructor(scenario) {
      this.scenario = scenario;
      this.reset();
    }
    reset() {
      this.current = this.scenario ? this.scenario.entry_step_id : "";
      this.history = [];
      this.incoming = null;
    }
    choices() {
      return this.scenario ? this.scenario.transitions.map((transition, index) => ({transition, index}))
        .filter(choice => choice.transition.source_id === this.current) : [];
    }
    forward(index) {
      const choice = this.choices().find(c => c.index === index);
      if (!choice) return false;
      this.history.push({step: this.current, incoming: this.incoming});
      this.current = choice.transition.target_id;
      this.incoming = choice.index;
      return true;
    }
    back() {
      const previous = this.history.pop();
      if (!previous) return false;
      this.current = previous.step;
      this.incoming = previous.incoming;
      return true;
    }
    inspectStep(id) {
      if (!this.scenario.steps.some(s => s.id === id)) return false;
      this.current = id;
      this.history = [];
      this.incoming = null;
      return true;
    }
    autoChoice() {
      const choices = this.choices();
      if (choices.length !== 1) return null;
      const choice = choices[0];
      if (choice.transition.kind === "loop" || this.history.some(h => h.step === choice.transition.target_id)
          || choice.transition.target_id === this.current) return null;
      return choice.index;
    }
  }
  return {visibleAncestor, hierarchy, projectedEdges, Player};
})();
if (typeof module !== "undefined") module.exports = ArchitectureView;
