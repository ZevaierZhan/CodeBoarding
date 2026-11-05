"""External Agent authoring transcript for the initial, source-evidenced scenario."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    snapshots = {
        root: json.loads((args.facts / f"{root}.facts.json").read_text(encoding="utf-8"))
        for root in ("frontend", "backend")
    }
    operations = [
        {"action": "create", "collection": "facts", "id": item["id"], "value": item} for item in snapshots.values()
    ]
    evidence = [
        ("open", "frontend", "openDocument"),
        ("preview", "frontend", "previewDocument"),
        ("invoke", "frontend", "readDocument"),
        ("command", "backend", "read_file"),
        ("service", "backend", "read_document"),
        ("registration", "backend", "src/lib.rs"),
    ]
    for identity, root, name in evidence:
        snapshot = snapshots[root]
        locations = snapshot["file_locations"] if identity == "registration" else snapshot["symbols"]
        matches = [loc for key, loc in locations.items() if key == name or loc["symbol"].split(".")[-1] == name]
        assert len(matches) == 1, (identity, matches)
        binding = {
            "id": identity,
            "snapshot_id": snapshot["id"],
            "source_version": snapshot["source"]["digest"],
            "location": matches[0],
            "status": "current",
        }
        operations.append({"action": "create", "collection": "bindings", "id": identity, "value": binding})

    def claim(text: str, bindings: list[str], inferred: bool = False) -> dict:
        return {
            "kind": "inference" if inferred else "code_fact",
            "explanation": text,
            "binding_ids": bindings,
            "assumptions": (
                [
                    "Desktop host enables the desktop feature and installs this registered handler; runtime invocation has not been executed."
                ]
                if inferred
                else []
            ),
        }

    components = [
        (
            "frontend-ui",
            "Document actions",
            "Choose a document path for open or preview",
            "Two UI-facing actions share one client",
            "",
            ["open", "preview"],
        ),
        (
            "ipc-client",
            "Tauri IPC client",
            "Invoke read_file with a path payload",
            "One operation is shared by both actions",
            "frontend-ui",
            ["invoke"],
        ),
        (
            "backend",
            "Rust document backend",
            "Register and handle document requests",
            "Rust boundary includes command registration and file service",
            "",
            ["command", "registration", "service"],
        ),
        (
            "rust-command",
            "Rust read_file command",
            "Delegate a path to the document service",
            "IPC endpoint is separate from filesystem work",
            "backend",
            ["command", "registration"],
        ),
        (
            "document-service",
            "Document file service",
            "Read UTF-8 file bytes and return errors",
            "Filesystem responsibility can be reused outside IPC",
            "backend",
            ["service"],
        ),
    ]
    for identity, name, responsibility, rationale, parent, bindings in components:
        value = {
            "id": identity,
            "name": name,
            "responsibility": responsibility,
            "rationale": rationale,
            "parent_id": parent,
            "binding_ids": bindings,
            "claim": claim(responsibility, bindings),
        }
        operations.append({"action": "create", "collection": "components", "id": identity, "value": value})
    relations = [
        {
            "id": "ui-client",
            "source_id": "frontend-ui",
            "target_id": "ipc-client",
            "meaning": "Both actions call the shared client",
            "claim": claim(
                "Native TypeScript call sites link openDocument/previewDocument to readDocument",
                ["open", "preview", "invoke"],
            ),
        },
        {
            "id": "read-file-ipc",
            "source_id": "ipc-client",
            "target_id": "rust-command",
            "meaning": "Candidate Tauri read_file request across the process boundary",
            "claim": claim(
                "invoke read_file and the Rust command/handler macro provide both sides; the desktop host is outside this fixture",
                ["invoke", "command", "registration"],
                True,
            ),
            "contract": {
                "mechanism": "tauri-ipc",
                "operation": "read_file",
                "caller_binding_ids": ["invoke"],
                "receiver_binding_ids": ["command"],
                "matching_binding_ids": ["registration"],
                "status": "candidate",
                "rationale": "utils.ts passes path to invoke(read_file); lib.rs declares command under desktop and registers generate_handler![read_file]",
                "uncertainties": [
                    "Desktop feature is disabled in the native extraction. No Tauri host runtime or IPC execution was tested."
                ],
            },
        },
        {
            "id": "command-service",
            "source_id": "rust-command",
            "target_id": "document-service",
            "meaning": "Read document through the filesystem service",
            "claim": claim("Native Rust call site links read_file to utils.read_document", ["command", "service"]),
        },
    ]
    operations.extend(
        {"action": "create", "collection": "relations", "id": relation["id"], "value": relation}
        for relation in relations
    )
    steps = [
        ("open-action", "frontend-ui", "open"),
        ("open-ipc", "ipc-client", "invoke"),
        ("open-command", "rust-command", "command"),
        ("open-service", "document-service", "service"),
    ]
    scenario = {
        "id": "open-document",
        "name": "Open document across TypeScript and Rust",
        "entry_step_id": "open-action",
        "relation_ids": [item["id"] for item in relations],
        "steps": [
            {
                "id": identity,
                "component_ids": [component],
                "binding_ids": [binding],
                "claim": claim("Declared open-document step", [binding]),
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
                    "Host routes the declared request" if first[0] == "open-ipc" else "Continue via the source call"
                ),
            }
            for first, second in zip(steps, steps[1:])
        ],
        "claim": claim(
            "Open notes.txt via the shared IPC contract and Rust file service",
            ["open", "invoke", "command", "registration", "service"],
            True,
        ),
    }
    operations.append({"action": "create", "collection": "scenarios", "id": scenario["id"], "value": scenario})
    project = {
        "id": "m5-system",
        "name": "Cross-language document system",
        "boundary": "TypeScript actions, explicit candidate Tauri IPC contract and Rust filesystem service. Desktop host activation and runtime execution are outside this fixture.",
    }
    patch = {
        "author": "M5 external modeling Agent",
        "summary": "Explain one cross-language document request using two independent source roots",
        "operations": operations,
    }
    (output / "project.json").write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")
    (output / "initial.patch.json").write_text(json.dumps(patch, indent=2) + "\n", encoding="utf-8")
    command = [sys.executable, "-m", "architecture_model", "model", "--file", str(output / "model.json")]
    for name, arguments in [
        ("init", ["init", "--project", str(output / "project.json"), "--author", "M5 external modeling Agent"]),
        ("validate", ["validate", "--patch", str(output / "initial.patch.json")]),
        ("apply", ["apply", "--expected-revision", "0", "--patch", str(output / "initial.patch.json")]),
    ]:
        result = subprocess.run(command + arguments, capture_output=True, text=True, check=True)
        (output / f"initial-{name}.response.json").write_text(result.stdout, encoding="utf-8")
    print(output / "model.json")


if __name__ == "__main__":
    main()
