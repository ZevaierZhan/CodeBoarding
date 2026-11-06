"""Compare complete fixed-input plans without publishing their contents."""

import argparse
import json
from pathlib import Path

from architecture_model.store import load_json
from architecture_model.validation import digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    plans = []
    for path in (args.before, args.after):
        value = load_json(path)
        if not isinstance(value, dict) or value.get("protocol") != "cross-root-maintenance-plan-v2":
            raise ValueError("Expected a complete v2 plan")
        body = {key: entry for key, entry in value.items() if key != "plan_id"}
        if digest(body) != value["plan_id"]:
            raise ValueError("Plan does not match its SHA-256 identity")
        body["validity"].pop("engine_digest")
        plans.append(body)
    changed = sorted(key for key in plans[0].keys() | plans[1].keys() if plans[0].get(key) != plans[1].get(key))
    if changed:
        raise ValueError(f"Fixed-input plans differ in top-level fields: {changed}")
    print(
        json.dumps(
            {
                "equal_except_engine_and_plan_identity": True,
                "status": plans[0]["status"],
                "summary": plans[0]["summary"],
            }
        )
    )


if __name__ == "__main__":
    main()
