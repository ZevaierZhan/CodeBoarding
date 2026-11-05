"""Check frontend source evidence without running the IPC contract."""

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    content = args.source.read_bytes()
    assert hashlib.sha256(content).hexdigest() == args.sha256
    assert b'invoke<string>("read_file", { path })' in content
    print(
        json.dumps(
            {
                "source_sha256": args.sha256,
                "checks": ["exact frontend file bytes", "literal IPC command and path payload"],
                "rust_or_ipc_runtime_executed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
