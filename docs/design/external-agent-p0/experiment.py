"""Probe native semantics, persistence and structure refresh without internal model calls."""

import argparse
import importlib.metadata
import json
import logging
import os
import socket
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from jsonschema import validate

from agents.content_hash import compute_source_tree_hash
from agents.llm_renderers.scope import render_scope_context
from agents.scope_analysis_agent import ScopeAnalysisResult
from codeboarding_cli.render import main as render_main
from diagram_analysis.analysis_json import UnifiedAnalysisJson, build_unified_analysis_json, parse_unified_analysis
from diagram_analysis.file_index import build_files_index
from diagram_analysis.io_utils import save_analysis
from diagram_analysis.reference_resolver import StaticReferenceResolver
from diagram_analysis.scope_assembly import ScopeAssembler
from infra.vscode_constants import VSCODE_CONFIG
from static_analyzer import StaticAnalyzer
from static_analyzer.analysis_cache import StaticAnalysisCache
from static_analyzer.clustering.service import ClusteringService
from static_analyzer.config import Language

LOG = logging.getLogger(__name__)
FIXTURE = Path(__file__).parent / "fixture"
RESPONSIBILITIES = {
    "delivery/request.py": "Validate positive quantity and enter the order flow.",
    "orchestration/order.py": "Compute a total, then ask the store to return an order identifier.",
    "persistence/store.py": "Format an order identifier; this fixture does not persist to a database.",
    "policies/pricing.py": "Multiply quantity by ten; no external pricing service is called.",
    "delivery/status.py": "Present an accepted identifier; not called by submit_order.",
    "orchestration/cancel.py": "Format cancellation; not part of the submit flow.",
    "persistence/receipt.py": "Format a receipt; no storage side effect.",
    "policies/discount.py": "Subtract one with a zero floor; not called by place_order.",
}
RATIONALE = "P0 grouping rationale: responsibilities are inferred from the inspected fixture, not author intent."


def snapshot(analysis) -> dict:
    return {
        component.component_id: {
            "name": component.name,
            "description": component.description,
            "members": sorted(
                f"{group.file_path}|{method.qualified_name}"
                for group in component.file_methods
                for method in group.methods
            ),
        }
        for component in analysis.components
    }


def export_facts(results, repo: Path) -> dict:
    graph = results.get_cfg(Language.PYTHON)
    return {
        "source_tree_hash": compute_source_tree_hash(repo),
        "nodes": [
            {
                "name": name,
                "file": Path(node.file_path).relative_to(repo).as_posix(),
                "start": node.line_start,
                "end": node.line_end,
                "kind": node.type.name,
            }
            for name, node in sorted(graph.nodes.items())
        ],
        "edges": [
            {
                "source": edge.get_source(),
                "target": edge.get_destination(),
                "sites": [
                    site | {"file": Path(str(site.get("file", edge.src_node.file_path))).relative_to(repo).as_posix()}
                    for site in edge.call_sites
                ],
            }
            for edge in graph.edges
        ],
        "reference_edges": [
            {"source": edge.src, "target": edge.dst, "kind": edge.kind} for edge in graph.reference_edges
        ],
    }


def run(output: Path, pyright_js: Path, node: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    os.environ["CODEBOARDING_TELEMETRY"] = "false"
    os.environ["DO_NOT_TRACK"] = "1"
    VSCODE_CONFIG["lsp_servers"]["python"]["command"] = [node, str(pyright_js), "--stdio"]
    attempts: list[str] = []

    def guard(frame, event, _arg):
        module = frame.f_globals.get("__name__", "")
        name = frame.f_code.co_name
        forbidden = module == "agents.llm_config" and name in {
            "configure_models",
            "validate_api_key_provided",
            "initialize_agent_llm",
        }
        forbidden |= module == "agents.scope_analysis_agent" and name == "analyze"
        forbidden |= module.startswith("langchain") and name in {
            "invoke",
            "ainvoke",
            "generate",
            "agenerate",
            "stream",
            "astream",
        }
        if event == "call" and forbidden:
            attempts.append(f"{module}.{name}")
            raise AssertionError(f"Internal LLM path entered: {attempts[-1]}")

    def reject_network(*_args, **_kwargs):
        attempts.append("socket.connect")
        raise AssertionError("Network access during guarded experiment")

    previous_profile = sys.getprofile()
    previous_thread_profile = threading.getprofile()
    sys.setprofile(guard)
    threading.setprofile(guard)
    try:
        with patch.object(socket.socket, "connect", reject_network), tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve() / "sample"
            for source in FIXTURE.rglob("*.py.txt"):
                destination = repo / source.relative_to(FIXTURE).with_suffix("")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
            cache = Path(temporary) / "cache"
            with StaticAnalyzer(repo, resident_servers=False) as analyzer:
                static = analyzer.analyze(cache, skip_cache=True)
            StaticAnalysisCache(cache, repo).save(static, source_sha=compute_source_tree_hash(repo))
            facts = export_facts(static, repo)
            expected = {
                ("submit_order", "place_order"),
                ("place_order", "calculate_total"),
                ("place_order", "save_order"),
            }
            actual = {(e["source"].split(".")[-1], e["target"].split(".")[-1]) for e in facts["edges"]}
            assert expected <= actual, (expected, actual)
            service = ClusteringService(repo_dir=repo)
            scope = service.build_full_hierarchy(static, max_depth=1)
            assembler = ScopeAssembler(repo)
            analysis = assembler.build(scope)
            assert len(analysis.components) >= 2, "Fixture needs at least two real deterministic groups"
            baseline = snapshot(analysis)
            ids = set(baseline)
            context = render_scope_context(scope, analysis, repo, ids, set(), set(), False)
            (output / "scope-context.json").write_text(context, encoding="utf-8")
            semantic_data = {
                "description": "Static explanation of the order fixture. This is not an execution trace.",
                "components": [
                    {
                        "group_id": comp.component_id,
                        "name": f"Order responsibility {index}",
                        "description": " ".join(RESPONSIBILITIES[group.file_path] for group in comp.file_methods)
                        + " "
                        + RATIONALE,
                        "key_entities": [
                            {"qualified_name": method.qualified_name, "reference_file": group.file_path}
                            for group in comp.file_methods
                            for method in group.methods
                        ],
                        "rationale": "P0_INDEPENDENT_RATIONALE",
                        "members": ["policies/pricing.py"],
                        "parent_id": "external-parent",
                    }
                    for index, comp in enumerate(analysis.components, 1)
                ],
                "relations": [
                    {
                        "source_group_id": connection.source_group_id,
                        "target_group_id": connection.target_group_id,
                        "relation": "passes order data",
                        "evidence": "Inspected static fixture call; not a runtime observation.",
                    }
                    for connection in scope.connections
                ],
            }
            validate(semantic_data, ScopeAnalysisResult.model_json_schema())
            semantics = ScopeAnalysisResult.model_validate(semantic_data)
            assembler.apply_semantics(analysis, scope, semantics, ids, set(), StaticReferenceResolver(repo, static))
            assert all(snapshot(analysis)[cid]["members"] == baseline[cid]["members"] for cid in ids)
            path = save_analysis(
                analysis,
                output / "native",
                repo,
                compute_source_tree_hash(repo),
                repo_name="p0-order-fixture",
                depth_cap=1,
                tree_spec=service.spec.to_dict(),
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            validate(data, UnifiedAnalysisJson.model_json_schema())
            reloaded, _ = parse_unified_analysis(data)
            assert snapshot(reloaded) == snapshot(analysis)
            assert all(comp.key_entities for comp in reloaded.components)
            assert all(
                ref.reference_start_line and ref.reference_file
                for comp in reloaded.components
                for ref in comp.key_entities
            )
            assert all(relation.relation == "passes order data" for relation in reloaded.components_relations)
            original_text = path.read_text(encoding="utf-8")
            with patch("diagram_analysis.io_utils.os.replace", side_effect=OSError("P0 simulated disk failure")):
                try:
                    save_analysis(
                        analysis,
                        path.parent,
                        repo,
                        compute_source_tree_hash(repo),
                        repo_name="p0-order-fixture",
                        depth_cap=1,
                    )
                except OSError:
                    assert path.read_text(encoding="utf-8") == original_text
                else:
                    raise AssertionError("Expected failed save")
            render_main([str(path), "--format", "html", "--output-dir", str(output / "html")])
            html = (output / "html" / "overview.html").read_text(encoding="utf-8")
            assert RATIONALE in html and "Order responsibility" in html and "calculate_total" in html
            assert "P0_INDEPENDENT_RATIONALE" not in html
            data["scenarios"] = [{"id": "order-A", "steps": [{"component_id": next(iter(ids))}]}]
            data["components"][0]["rationale"] = "P0_INDEPENDENT_RATIONALE"
            unknown_root, _ = parse_unified_analysis(data)
            roundtrip = json.loads(
                build_unified_analysis_json(
                    unknown_root, [], "p0-order-fixture", repo, compute_source_tree_hash(repo), 1
                )
            )
            assert "scenarios" not in roundtrip and "rationale" not in roundtrip["components"][0]
            donor = next(
                c for c in reloaded.components if any(g.file_path == "policies/pricing.py" for g in c.file_methods)
            )
            receiver = next(
                c
                for c in reloaded.components
                if c.component_id != donor.component_id
                and any(g.file_path != "policies/pricing.py" for g in c.file_methods)
            )
            moved = next(g for g in donor.file_methods if g.file_path == "policies/pricing.py")
            donor.file_methods.remove(moved)
            receiver.file_methods.append(moved)
            reloaded.files = build_files_index(reloaded, repo)
            edited_path = save_analysis(
                reloaded,
                output / "edited",
                repo,
                compute_source_tree_hash(repo),
                repo_name="p0-order-fixture",
                depth_cap=1,
                tree_spec=service.spec.to_dict(),
            )
            edited, _ = parse_unified_analysis(json.loads(edited_path.read_text(encoding="utf-8")))
            assert snapshot(edited) == snapshot(reloaded)
            before_refresh = snapshot(edited)
            pricing = repo / "policies/pricing.py"
            pricing.write_text(
                pricing.read_text(encoding="utf-8").replace("quantity * 10", "quantity * 12"), encoding="utf-8"
            )
            with StaticAnalyzer(repo, changed_files={pricing}, resident_servers=False) as analyzer:
                refreshed = analyzer.analyze(cache, source_sha=compute_source_tree_hash(repo))
            assert refreshed.incremental_base_results is not None, "Expected real warm start"
            refreshed_service = ClusteringService(repo_dir=repo)
            refreshed_scope = refreshed_service.build_incremental_hierarchy(
                refreshed,
                1,
                service.spec,
                {scope.scope_id: edited},
                repo,
                cache,
            )
            assembler.populate_file_methods(edited, refreshed_scope)
            refreshed_donor = edited.component_by_id(donor.component_id)
            refreshed_receiver = edited.component_by_id(receiver.component_id)
            assert refreshed_donor is not None and refreshed_receiver is not None
            assert any(g.file_path == "policies/pricing.py" for g in refreshed_donor.file_methods)
            assert not any(g.file_path == "policies/pricing.py" for g in refreshed_receiver.file_methods)
            after_refresh = snapshot(edited)
            assert set(after_refresh) == ids
            assert all(after_refresh[cid]["description"] == before_refresh[cid]["description"] for cid in ids)
            changed_key = next(k for k in data["methods_index"] if "calculate_total" in k)
            refreshed_json = json.loads(
                build_unified_analysis_json(edited, [], "p0-order-fixture", repo, compute_source_tree_hash(repo), 1)
            )
            assert (
                data["methods_index"][changed_key]["content_hash"]
                != refreshed_json["methods_index"][changed_key]["content_hash"]
            )
            refreshed_path = save_analysis(
                edited,
                output / "refreshed",
                repo,
                compute_source_tree_hash(repo),
                repo_name="p0-order-fixture",
                depth_cap=1,
                tree_spec=refreshed_service.spec.to_dict(),
            )
            saved_refresh, _ = parse_unified_analysis(json.loads(refreshed_path.read_text(encoding="utf-8")))
            assert snapshot(saved_refresh) == after_refresh
            for name, content in {
                "facts-before.json": facts,
                "facts-after.json": export_facts(refreshed, repo),
                "semantics.json": semantic_data,
            }.items():
                (output / name).write_text(json.dumps(content, indent=2), encoding="utf-8")
            report = {
                "A": {
                    "static_edges": "PASS",
                    "semantics_schema": "PASS",
                    "unified_schema": "PASS",
                    "save_reload": "PASS",
                    "renderer": "PASS: real CLI main, HTML content checked; browser QA recorded separately",
                    "failed_save_keeps_previous": "PASS",
                },
                "B": {
                    "semantic_membership_request": "LIMIT: ignored",
                    "manual_member_move_save_reload": "PASS (internal API only)",
                    "warm_static_refresh": "PASS",
                    "native_incremental_replay": "LIMIT: restores TreeSpec membership",
                    "ids_and_descriptions": "PASS for body edit",
                    "source_content_hash_changed": "PASS",
                },
                "unknown_fields": "LIMIT: independent rationale and scenarios dropped by native roundtrip",
                "before_member_edit": baseline,
                "edited": before_refresh,
                "after_refresh": after_refresh,
                "guard_attempts": attempts,
                "environment": {
                    name: importlib.metadata.version(name)
                    for name in [
                        "codeboarding",
                        "pydantic",
                        "jsonschema",
                        "tree-sitter",
                        "tree-sitter-python",
                        "networkx",
                    ]
                },
                "python": sys.version.split()[0],
                "fixture_hash": facts["source_tree_hash"],
            }
            (output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            LOG.info("P0 probes passed; native model limitations reproduced. Results: %s", output)
    finally:
        sys.setprofile(previous_profile)
        threading.setprofile(previous_thread_profile)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pyright-js", type=Path, required=True)
    parser.add_argument("--node", default="node")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.output.resolve(), args.pyright_js.resolve(), args.node)


if __name__ == "__main__":
    main()
