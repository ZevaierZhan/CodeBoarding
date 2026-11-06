"use strict";
(() => {
  const documentData = JSON.parse(document.getElementById("model-data").textContent);
  const model = documentData.model;
  const report = documentData.maintenance;
  const {componentProjection, hierarchy, projectedEdges, Player} = ArchitectureView;
  const rows = hierarchy(model.components);
  const byId = new Map([...model.components, ...model.relations, ...model.scenarios,
    ...model.scenarios.flatMap(s => s.steps), ...model.bindings, ...model.maintenance].map(o => [o.id, o]));
  const expanded = new Set(model.components.filter(c => !c.parent_id).map(c => c.id));
  const bindingIds = new Set(model.bindings.map(b => b.id));
  const players = new Map(model.scenarios.map(s => [s.id, new Player(s)]));
  let scenario = model.scenarios[0] || null;
  let player = scenario ? players.get(scenario.id) : new Player(null);
  let selection = player.current || model.components[0]?.id || model.project.id;
  let timer = null;
  let message = "";
  const el = id => document.getElementById(id);
  const element = (tag, text = "", className = "") => {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  function button(text, action, className = "") {
    const node = element("button", text, className);
    node.type = "button";
    node.addEventListener("click", action);
    return node;
  }
  function field(container, label, value) {
    const node = element("div", "", "field");
    node.append(element("b", label));
    node.append(element("div", typeof value === "string" ? value : JSON.stringify(value, null, 2)));
    container.append(node);
  }
  function json(container, value) { container.append(element("pre", JSON.stringify(value, null, 2))); }
  function details(container, title, value) {
    const node = element("details");
    node.append(element("summary", title));
    json(node, value);
    container.append(node);
    return node;
  }
  function pause() {
    if (timer !== null) clearInterval(timer);
    timer = null;
    el("play").textContent = "Play";
  }
  function select(id) { selection = id; renderDetail(); }
  function moved() {
    message = "";
    selection = player.current;
    render();
  }
  function advance(index) {
    pause();
    if (player.forward(index)) moved();
  }
  function autoTick() {
    const index = player.autoChoice();
    if (index === null) {
      pause();
      message = player.choices().length ? "Paused: choose a branch or explicitly enter a cycle." : "Paused at modeled endpoint or unexplained gap.";
      renderPlayer();
      return;
    }
    player.forward(index);
    moved();
  }
  function renderTree(projection) {
    el("tree").replaceChildren();
    for (const {component, depth} of rows) {
      if (projection.visibleById.get(component.id) !== component.id) continue;
      const row = element("div", "", "tree-row");
      row.style.paddingInlineStart = `${depth * 12}px`;
      if (projection.parentIds.has(component.id)) {
        const toggle = button(expanded.has(component.id) ? "−" : "+", () => {
          expanded.has(component.id) ? expanded.delete(component.id) : expanded.add(component.id);
          render();
        });
        toggle.setAttribute("aria-label", `Toggle ${component.name}`);
        toggle.setAttribute("aria-expanded", String(expanded.has(component.id)));
        row.append(toggle);
      }
      row.append(button(component.name, () => select(component.id), "object"));
      el("tree").append(row);
    }
    el("steps").replaceChildren();
    if (!scenario) { el("steps").append(element("p", "No modeled businesses. Update the model through the external Agent / CLI.")); return; }
    for (const id of scenario.order) {
      const step = scenario.steps.find(s => s.id === id);
      const node = button(id, () => {
        pause(); player.inspectStep(id); message = "Direct inspection starts a new browsing path.";
        selection = id; render();
      }, `step${id === player.current ? " active" : ""}`);
      node.setAttribute("aria-current", id === player.current ? "step" : "false");
      node.append(element("small", step.claim.explanation));
      el("steps").append(node);
    }
  }
  function svgElement(tag, attributes) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  }
  function renderGraph(projection) {
    const active = new Set(scenario?.steps.find(s => s.id === player.current)?.component_ids || []);
    const involved = new Set(scenario?.steps.flatMap(s => s.component_ids) || []);
    const project = id => projection.visibleById.get(id);
    const activeVisible = new Set([...active].map(project));
    const currentLabel = scenario?.analysis_kind === "comparison" ? "Inspected item" : "Current step";
    const involvedVisible = new Set([...involved].map(project));
    const graph = el("graph");
    const nodes = el("nodes");
    graph.replaceChildren(); nodes.replaceChildren();
    const defs = svgElement("defs", {});
    const marker = svgElement("marker", {id:"arrow",viewBox:"0 0 10 10",refX:9,refY:5,markerWidth:6,markerHeight:6,orient:"auto-start-reverse"});
    marker.append(svgElement("path", {d:"M 0 0 L 10 5 L 0 10 z",fill:"context-stroke"}));
    defs.append(marker); graph.append(defs);
    const width = Math.max(430, ...rows.map(r => r.depth * 230 + 460));
    const height = Math.max(230, rows.length * 105 + 30);
    nodes.style.width = `${width}px`; nodes.style.height = `${height}px`;
    graph.style.width = `${width}px`; graph.style.height = `${height}px`;
    const positions = new Map(rows.map(r => [r.component.id, {x: r.depth * 230 + 20, y: r.index * 105 + 20}]));
    const edges = projectedEdges(model, scenario, expanded, projection);
    const groups = new Map();
    for (const edge of edges) {
      const activeEdge = edge.kind !== "relation" && (edge.source_step_id === player.current || edge.transition_index === player.incoming);
      if (edge.kind !== "relation" && !activeEdge) continue;
      const key = JSON.stringify([edge.source,edge.target]);
      if (!groups.has(key)) groups.set(key,[]);
      groups.get(key).push(edge);
    }
    const labelRows = new Map();
    for (const grouped of groups.values()) {
      const edge = grouped[0];
      const transitions = grouped.filter(e => e.kind !== "relation");
      const highlight = transitions.length > 0;
      const source = positions.get(edge.source), target = positions.get(edge.target);
      const stroke = highlight ? "#007c78" : "#9aadb9";
      let path;
      if (edge.source === edge.target) {
        path = `M${source.x+170},${source.y+20} C${source.x+235},${source.y-16} ${source.x+235},${source.y+95} ${source.x+170},${source.y+66}`;
      } else {
        path = `M${source.x+190},${source.y+42} C${source.x+220},${source.y+42} ${target.x+220},${target.y+42} ${target.x+190},${target.y+42}`;
      }
      const line = svgElement("path", {d:path, fill:"none", stroke, "stroke-width":highlight?3:1.5,
        "stroke-dasharray":highlight?"6 3":"none", "marker-end":"url(#arrow)"});
      const title = svgElement("title", {});
      title.textContent = grouped.map(item => item.kind === "relation" ? item.relation_id : `${item.source_step_id} → ${item.target_step_id} · ${item.kind}`).join("\n");
      line.append(title); graph.append(line);
      const labelRow = labelRows.get(edge.source) || 0;
      labelRows.set(edge.source,labelRow+1);
      const label = svgElement("text", {x:source.x+198,y:source.y+12+labelRow*15});
      const relationCount = grouped.length - transitions.length;
      label.textContent = [relationCount ? `${relationCount} relation${relationCount > 1 ? "s" : ""}` : "", ...new Set(transitions.map(item=>item.kind))].filter(Boolean).join(" · ");
      graph.append(label);
    }
    for (const {component} of rows) {
      if (project(component.id) !== component.id) continue;
      const position = positions.get(component.id);
      const node = button("", () => select(component.id), "node");
      node.dataset.componentId = component.id;
      node.style.left = `${position.x}px`; node.style.top = `${position.y}px`;
      node.classList.toggle("current", activeVisible.has(component.id));
      node.classList.toggle("unrelated", el("focus").checked && !involvedVisible.has(component.id));
      node.append(element("strong", component.name), element("small", component.id));
      if (activeVisible.has(component.id)) {
        node.append(element("span", active.has(component.id) ? currentLabel : `${currentLabel} inside · ${player.current}`, "inside"));
      }
      const hidden = projection.hiddenCounts.get(component.id) || 0;
      if (hidden) node.append(element("small", `${hidden} components inside · expand in structure`));
      nodes.append(node);
    }
    el("relations").replaceChildren();
    for (const relation of model.relations) {
      el("relations").append(button(`${relation.source_id} → ${relation.target_id} · ${relation.meaning}`,
        () => select(relation.id), "relation"));
    }
    if (!rows.length) nodes.append(element("p", "No components modeled yet."));
    if (!model.relations.length) el("relations").append(element("p", "No component relations modeled. Business transitions remain separate."));
  }
  function renderPlayer() {
    const comparison = scenario?.analysis_kind === "comparison";
    el("current").textContent = scenario ? `${comparison ? "Comparison topic" : "Operation"} · ${scenario.name} / ${player.current}` : "No business selected";
    el("choices").replaceChildren();
    const choices = player.choices();
    el("playback-status").textContent = comparison
      ? "Independent explanations in display order. Select a topic item to inspect its evidence; playback is disabled."
      : message || (choices.length === 0
      ? "No outgoing transition saved. Modeled endpoint or unexplained gap; no next step is inferred from display order."
      : choices.length > 1 ? "Choose a saved transition. Conditions have not been evaluated."
      : choices[0].transition.kind === "loop" ? "Loop boundary: paused until explicitly selected. Choose another transition to exit when available." : "Ready to follow the saved transition.");
    for (const {transition, index} of choices) {
      el("choices").append(button(`${transition.kind} → ${transition.target_id} · ${transition.condition}`, () => advance(index)));
    }
    const incoming = scenario?.transitions[player.incoming];
    el("incoming").textContent = comparison ? "No execution order is asserted." : incoming ? `Last traversed: ${incoming.source_id} → ${incoming.target_id} · ${incoming.kind} · ${incoming.condition}` : "No transition traversed in this browsing path.";
    el("back").disabled = player.history.length === 0;
    el("next").disabled = choices.length !== 1;
    el("play").disabled = !scenario || !choices.length;
    el("reset").disabled = !scenario || comparison;
  }
  function renderBindings(container, ids, displayed) {
    container.append(element("h3", "Code evidence"));
    for (const id of ids) {
      const binding = byId.get(id);
      if (!binding) continue;
      const node = element("details");
      node.dataset.bindingId = id;
      node.append(element("summary", `${id} · ${binding.location.path}:${binding.location.start} · ${binding.status}`));
      node.append(button(`Inspect binding ${id}`, () => select(id)));
      field(node, "Binding status is relative to its saved evidence", binding.reason || binding.status);
      for (const [index, snippet] of documentData.snippets[id].entries()) {
        field(node, index === 0 ? "Referenced evidence" : "Historical binding evidence", snippet.location.symbol || snippet.location.path);
        const snapshot = model.facts.find(item => item.id === snippet.snapshot_id);
        json(node, {source_root_id:snippet.source_root_id || "legacy single root", language:snapshot?.file_languages?.[snippet.location.path] || "legacy", project:snapshot?.file_projects?.[snippet.location.path] || "legacy", snapshot_id:snippet.snapshot_id,source_version:snippet.source_version,...snippet.location});
        if (snippet.status === "verified") node.append(element("p", "Exact file SHA-256 matched this evidence version.", "badge"), element("pre", snippet.text));
        else node.append(element("p", snippet.reason, "warning"));
      }
      details(node, "Binding history metadata", binding.history);
      node.append(element("h3", "Binding opinions & verification"));
      node.append(element("p", "Coverage is limited to the recorded object_ids, inputs and source_version. Binding checks do not verify a whole component or business.", "muted"));
      renderRecords(node, new Set([id]), displayed, `binding ${id}`);
      container.append(node);
    }
  }
  function renderMaintenance(container, ids, displayed) {
    container.append(element("h3", "Maintenance & review history"));
    container.append(element("p", "Current means current explanation contents for a saved source comparison. It does not mean latest source verified.", "muted"));
    field(container, "Legacy root latest target", report.latest_target_snapshot_id || "Unknown or no legacy target saved");
    if (report.legacy_target_status) field(container, "Legacy target availability", report.legacy_target_status);
    details(container, "Explicit root latest targets", report.source_root_targets || {});
    const matching = model.maintenance.filter(item => ids.has(item.binding_id) || [...item.component_ids,...item.relation_ids,...item.scenario_ids,...item.step_ids].some(id => ids.has(id)));
    if (!matching.length) container.append(element("p", "No maintenance observations for this selection. This is not evidence of verification."));
    for (const item of matching) {
      const current = report.current_coverage_ids.includes(item.id);
      const pending = report.pending_ids.includes(item.id);
      const currentPending = report.current_pending_ids.includes(item.id);
      const latest = report.latest_observation_ids ? report.latest_observation_ids.includes(item.id) : item.target_snapshot_id === report.latest_target_snapshot_id;
      const targetLabel = report.unknown_target_observation_ids?.includes(item.id) ? "target latestness unknown" : latest ? "latest target" : "older target";
      const node = element("details");
      node.append(element("summary", `${current ? "Current explanation" : "Historical explanation"} · ${item.disposition} · ${currentPending ? "current pending" : pending ? "historical pending" : item.resolution ? "review recorded" : "unchanged comparison"} · ${targetLabel}`));
      field(node, "Observation ID", item.id);
      field(node, "Target snapshot / source version", `${item.target_snapshot_id} / ${item.target_source_version}`);
      field(node, "Reasons", item.reasons);
      details(node, "Actual affected scope and content fingerprints", {component_ids:item.component_ids,relation_ids:item.relation_ids,scenario_ids:item.scenario_ids,step_ids:item.step_ids,coverage_version:item.coverage_version,object_versions:item.object_versions});
      if (item.resolution) details(node, "Confirmation author, reason and actual version coverage", item.resolution).open = true;
      else field(node, "Review", pending ? "Unresolved" : "No review required by this comparison");
      details(node, "Source basis, candidates and static call changes", {basis:item.basis,candidates:item.candidates,call_changes:item.call_changes,compared_revision:item.compared_revision});
      renderRecords(node, new Set([item.id]), displayed, `observation ${item.id}`);
      container.append(node);
    }
    container.append(element("p", "Historical source bodies and old explanation bodies cannot be reconstructed from revisions or fingerprints.", "muted"));
  }
  function renderRecords(container, ids, displayed, context) {
    for (const [name, records] of [["Human opinion", model.opinions], ["Verification", model.verifications]]) {
      for (const record of records.filter(r => r.object_ids.some(id => ids.has(id)))) {
        if (displayed.has(record.id)) {
          const existing = displayed.get(record.id);
          const reference = button(`View ${record.id} · also targets this selection; shown under ${existing.context}`, () => {
            let ancestor = existing.node;
            while (ancestor) {
              if (ancestor.tagName === "DETAILS") ancestor.open = true;
              ancestor = ancestor.parentElement;
            }
            existing.node.scrollIntoView({block:"nearest"});
            existing.node.querySelector("summary").focus();
          });
          reference.dataset.recordReference = record.id;
          container.append(reference);
          continue;
        }
        const node = details(container, `${name} · ${record.status || record.stance} · ${record.id}`, record);
        if (name === "Verification") {
          const scope = documentData.verification_scopes?.[record.id];
          details(node, "Verification evidence scope (not whole-business approval)", scope || {scope_kind:"legacy_unscoped",notice:"Actual binding/root coverage was not declared."}).open = true;
        }
        node.dataset.recordId = record.id;
        displayed.set(record.id, {node, context});
      }
    }
  }
  function renderDetail() {
    const container = el("detail"); container.replaceChildren();
    const object = byId.get(selection);
    if (!object) { json(container, model.project); return; }
    container.append(element("h3", object.name || object.id));
    if (object.contract) details(container, "Cross-boundary contract (static evidence, not runtime proof)", object.contract);
    field(container, "Stable object ID", object.id);
    for (const name of ["responsibility", "rationale", "parent_id", "meaning", "source_id", "target_id", "component_ids"]) {
      if (object[name]) field(container, name.replaceAll("_", " "), object[name]);
    }
    const claim = object.claim;
    if (claim) {
      container.append(element("span", claim.kind, "badge"));
      field(container, "Explanation", claim.explanation);
      field(container, "Assumptions", claim.assumptions.length ? claim.assumptions : "None declared");
      field(container, "Issues", claim.issues.length ? claim.issues : "None declared");
    }
    if (object.steps) {
      field(container, "Analysis kind", object.analysis_kind || "operation");
      field(container, "Analysis questions (display order)", object.facet_order || []);
      container.append(element("p", "Step order organizes reading. Only operation transitions describe a modeled execution path.", "muted"));
    }
    const owner = model.scenarios.find(item => item.steps.some(step => step.id === object.id));
    if (owner?.facet_order?.length) {
      container.append(element("h3", "Analysis questions"));
      container.append(element("p", "Authored interpretations supported by this step's claim and code evidence. These entries have no execution status. Executed checks appear separately under Verification.", "muted"));
      for (const label of owner.facet_order || []) {
        field(container, label, object.facet_checks?.[label] || "Not examined / unknown");
      }
    }
    const ids = new Set([object.id]);
    const bindings = new Set([...(object.binding_ids || []), ...(claim?.binding_ids || [])]);
    if (bindingIds.has(object.id)) bindings.add(object.id);
    if (object.component_ids) {
      for (const id of object.component_ids) {
        ids.add(id);
        container.append(button(`Inspect component ${id}`, () => select(id)));
        for (const bid of [...byId.get(id).binding_ids, ...byId.get(id).claim.binding_ids]) bindings.add(bid);
      }
    }
    const displayed = new Map();
    renderBindings(container, bindings, displayed);
    container.append(element("h3", "Opinions & verification"));
    container.append(element("p", "Planned checks are not executed results. An executed result applies only to its recorded inputs, objects and source version; it does not change claim kind.", "muted"));
    renderRecords(container, ids, displayed, `selection ${object.id}`);
    renderMaintenance(container, new Set([...ids, ...bindings]), displayed);
  }
  function render() {
    const projection = componentProjection(model.components, expanded);
    renderTree(projection); renderGraph(projection); renderPlayer(); renderDetail();
  }
  el("project").textContent = model.project.name;
  el("boundary").textContent = model.project.boundary;
  el("identity").textContent = `Model ${model.id} · revision ${model.revision}`;
  el("exported").textContent = `Exported ${documentData.exported_at}`;
  for (const item of model.scenarios) {
    const option = element("option", `${item.analysis_kind === "comparison" ? "Comparison" : "Operation"} · ${item.name}`); option.value = item.id; el("scenario").append(option);
  }
  el("scenario").disabled = !scenario;
  el("inspect-business").disabled = !scenario;
  el("inspect-business").addEventListener("click", () => { if (scenario) select(scenario.id); });
  el("scenario").addEventListener("change", () => {
    pause(); scenario = model.scenarios.find(s => s.id === el("scenario").value);
    player = players.get(scenario.id); message = ""; selection = player.current; render();
  });
  el("focus").addEventListener("change", () => renderGraph(componentProjection(model.components, expanded)));
  el("reset").addEventListener("click", () => { pause(); player.reset(); moved(); });
  el("back").addEventListener("click", () => { pause(); player.back(); moved(); });
  el("next").addEventListener("click", () => {
    const choices = player.choices(); if (choices.length === 1) advance(choices[0].index);
  });
  el("play").addEventListener("click", () => {
    if (timer !== null) { pause(); return; }
    timer = setInterval(autoTick, 1100); el("play").textContent = "Pause";
  });
  el("expand-all").addEventListener("click", () => { model.components.forEach(c => expanded.add(c.id)); render(); });
  el("collapse-all").addEventListener("click", () => { expanded.clear(); render(); });
  el("metadata").addEventListener("click", () => {
    const container = el("detail"); container.replaceChildren();
    field(container, "Model / revision / export", `${model.id} / ${model.revision} / ${documentData.exported_at}`);
    field(container, "Selected business / step", `${scenario?.id || "none"} / ${player.current || "none"}`);
    json(container, model.project);
    container.append(element("h3", "Source bindings"));
    for (const binding of model.bindings) {
      container.append(button(`Inspect binding ${binding.id}`, () => select(binding.id)));
    }
    field(container, "Legacy root latest target", report.latest_target_snapshot_id || "Unknown or no legacy target saved");
    if (report.legacy_target_status) field(container, "Legacy target availability", report.legacy_target_status);
    details(container, "Independent source root maintenance targets", report.source_root_targets || {});
    for (const facts of model.facts) details(container, `Snapshot ${facts.id}`, {id:facts.id,source_root_id:facts.source_root_id || "legacy single root",file_languages:facts.file_languages,file_projects:facts.file_projects, source:facts.source,tools:facts.tools,limitations:facts.limitations});
    details(container, "Maintenance coverage sets", report);
    details(container, "Revision metadata (not historical explanation bodies)", model.revisions);
  });
  window.addEventListener("pagehide", pause);
  render();
})();
