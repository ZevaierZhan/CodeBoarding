"""External Agent's bounded Java/Vue capability trial using actual native facts."""

import json
import sys
import tempfile
from pathlib import Path

from architecture_model.store import ModelStore, load_json
from architecture_model.viewer import export_html


def main() -> None:
    facts_file, source, output = map(Path, sys.argv[1:])
    snapshot = load_json(facts_file)
    assert isinstance(snapshot, dict)
    output.mkdir(parents=True, exist_ok=True)
    operations = [{"action": "create", "collection": "facts", "id": snapshot["id"], "value": snapshot}]
    choices = {
        "vue-page": ("file_locations", "frontend/src/Orders.vue"),
        "api-client": ("symbols", ".api.createOrder"),
        "controller": ("symbols", ".OrderController.createOrder()"),
        "routes": ("file_locations", "backend/src/main/java/example/OrderController.java"),
        "service": ("symbols", ".OrderService.create()"),
    }
    locations = {}
    for identity, (catalog, suffix) in choices.items():
        matches = [
            location
            for key, location in snapshot[catalog].items()
            if key == suffix or location["symbol"].endswith(suffix)
        ]
        assert len(matches) == 1, (identity, matches)
        locations[identity] = matches[0]
        value = {
            "id": identity,
            "snapshot_id": snapshot["id"],
            "source_version": snapshot["source"]["digest"],
            "location": matches[0],
            "status": "current",
        }
        operations.append({"action": "create", "collection": "bindings", "id": identity, "value": value})
    assert any(
        call["source"].endswith("OrderController.createOrder()") and call["target"].endswith("OrderService.create()")
        for call in snapshot["calls"]
    )
    assert not any(location["path"].endswith(".vue") for location in snapshot["symbols"].values())

    def claim(text: str, evidence: list[str], inferred: bool = False) -> dict:
        return {
            "kind": "inference" if inferred else "code_fact",
            "explanation": text,
            "binding_ids": evidence,
            "issues": (
                [
                    "Vue has file evidence only. Host startup, component mounting and HTTP deployment/proxy mapping are unverified."
                ]
                if inferred
                else []
            ),
        }

    components = [
        ("page", "Vue orders page", ["vue-page"]),
        ("client", "TypeScript API client", ["api-client"]),
        ("java-controller", "Spring orders controller", ["controller", "routes"]),
        ("java-service", "Order service", ["service"]),
    ]
    for identity, name, bindings in components:
        value = {
            "id": identity,
            "name": name,
            "responsibility": name,
            "rationale": "Separate UI, transport, HTTP handling and business service",
            "binding_ids": bindings,
            "claim": claim(name + " as declared in source", bindings),
        }
        operations.append({"action": "create", "collection": "components", "id": identity, "value": value})
    relation = {
        "id": "orders-http",
        "source_id": "client",
        "target_id": "java-controller",
        "meaning": "Candidate POST /api/orders mapping",
        "claim": claim(
            "fetch POST /api/orders matches RequestMapping /api plus PostMapping /orders; application registration and deployment are outside the fixture",
            ["api-client", "controller", "routes"],
            True,
        ),
        "contract": {
            "mechanism": "http",
            "operation": "POST /api/orders",
            "caller_binding_ids": ["api-client"],
            "receiver_binding_ids": ["controller"],
            "matching_binding_ids": ["routes"],
            "rationale": "Inspected HTTP method, class route prefix and method route suffix on both sides",
            "status": "candidate",
            "uncertainties": [
                "No Spring application boot/scan or frontend proxy/base URL configuration is included. Static route equality is not runtime proof."
            ],
        },
    }
    operations.append({"action": "create", "collection": "relations", "id": relation["id"], "value": relation})
    steps = [
        ("submit-page", "page", "vue-page"),
        ("request-order", "client", "api-client"),
        ("handle-order", "java-controller", "controller"),
        ("create-order", "java-service", "service"),
    ]
    scenario = {
        "id": "vue-order",
        "name": "Vue -> API Client -> Spring Controller -> Service",
        "entry_step_id": steps[0][0],
        "relation_ids": ["orders-http"],
        "steps": [
            {
                "id": identity,
                "component_ids": [component],
                "binding_ids": [binding],
                "claim": claim("Declared capability step", [binding], binding == "vue-page"),
            }
            for identity, component, binding in steps
        ],
        "order": [item[0] for item in steps],
        "transitions": [
            {
                "source_id": first[0],
                "target_id": second[0],
                "kind": "next",
                "condition": (
                    "Assuming UI mounting and host routing"
                    if first[0] != "handle-order"
                    else "Native service method call"
                ),
            }
            for first, second in zip(steps, steps[1:])
        ],
        "claim": claim(
            "A source-evidenced HTTP candidate path, including explicit Vue file-only and host activation gaps",
            list(choices),
            True,
        ),
    }
    operations.append({"action": "create", "collection": "scenarios", "id": scenario["id"], "value": scenario})
    patch = {
        "author": "M5 external Agent",
        "summary": "Java/Vue capability check, distinct from the primary continuing Tauri model",
        "operations": operations,
    }
    (output / "java-vue.patch.json").write_text(json.dumps(patch, indent=2) + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="m5-java-vue-") as temporary:
        store = ModelStore(Path(temporary) / "model.json")
        store.initialize(
            {
                "id": snapshot["project_id"],
                "name": "Java/Vue capability check",
                "boundary": "Independent assessment fixture; no application host or deployment is included",
            },
            "M5 external Agent",
        )
        store.apply(0, patch)
        result = export_html(store.read(), output / "java-vue.html", source_map={snapshot["source_root_id"]: source})
        (output / "java-vue-check.json").write_text(
            json.dumps(
                result
                | {
                    "method_edge_present": True,
                    "vue_symbol_support": False,
                    "vue_file_evidence": True,
                    "http_contract_status": "candidate",
                    "scenario": scenario["id"],
                    "temporary_check_model": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
