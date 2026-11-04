# M1 P2 review fixes — 2026-11-04 (Asia/Shanghai)

Latest validation for Draft PR [#2](https://github.com/ZevaierZhan/CodeBoarding/pull/2),
continuing `m1/architecture-model-cli` from reviewed head
`cbb121b49aba9f7b32520ba0e16705980b0cdcde`. The workspace was clean and the remote
head matched at start. The PR still targets fork `main`; no unrelated edits, P0
branch, model schema version, transaction design or M2/M3 scope was changed.

[Machine evidence](architecture-model-m1-p2-validation.json) includes source hashes,
actual explicit-tool process markers and snapshot commands, pre-fix failures,
current results, continuous-model stages and error attribution. Full logs, test
binaries and generated models stay ignored in `temp/` and pytest's temporary root.
The [initial M1 validation](architecture-model-m1-results.md) remains historical.

## Four corrections

1. **Explicit tools:** both installed-tool and PATH resolution preserve complete
   absolute commands already configured by the caller. `build_config/get_config`
   therefore keep the requested Node, Pyright JS, Tokei and exact arguments;
   unresolved defaults retain their discovery behavior. The worker records the
   resolved paths and full argv (JSON-encoded strings in `tools`). No fallback is
   attempted after an explicit tool fails.
2. **Scenario impact:** changed opinions/verifications contribute their before and
   after `object_ids`. Direct scenario targets and referenced steps' owning
   scenarios are included for create, body/result updates, retarget and delete.
   Candidate preview and apply use the same diff; revision `scenario_ids` matches.
   No business-semantic inference was added.
3. **Test isolation:** real worker imports and API calls now run in a separate
   `real_export_probe.py` process, retaining the original positive/negative checks.
   The parent asserts configuration, environment and worker/telemetry module
   identities are unchanged. `.coveragerc` enables subprocess measurement so
   isolation does not hide worker execution from coverage. No omissions or
   thresholds were relaxed.
4. **Platform typing:** Windows creation flags are assigned inside a recognized
   `sys.platform == "win32"` block before Popen. Windows process-group creation and
   timeout tree termination remain covered; real Linux also tests the POSIX branch.

## Regression evidence

- Before fixes: resolver/record regressions **8 failed / 1 passed**; isolated
  installation real-tool regressions **3 failed**; requested original pair alone
  **2 passed**, but with the real-export test first **1 passed / 2 failed**.
  The Linux-target probe reproduced the introduced CREATE_NEW_PROCESS_GROUP error.
- After fixes: the **12 new regressions pass**, including four resolver paths,
  default installed-tool discovery, three real tool outcomes, and four record
  lifecycle cases. Each record case checks five create/update/retarget/delete
  stages through actual preview/apply, byte-preserving preview, persistence and
  revision/diff consistency.
- Real-tool tests use a temporary HOME/USERPROFILE containing another Tokei and
  Pyright installation. A copied explicit Node and instrumented Pyright/Tokei
  entry points prove the actual executable/argv. Success exports two callables and
  one call; exact Python argv ends in only `--stdio`, Tokei gets only `-o json`.
  Explicit Tokei/Pyright stubs write markers and exit 42: export returns
  `FACTS_FAILED`, no facts are published and existing model bytes remain unchanged.
  The installed Pyright marker stays absent. No real user installation is modified.
- Final order comparison with real tool paths: pair alone **2 passed**, then
  real export plus pair **3 passed**, both exit 0, no skips. The two prior failures
  are **confirmed PR regressions now fixed**, not baseline/environment failures.

## Final checks

| Check | Actual result |
|---|---|
| All M1 tests, real `M1_NODE/M1_PYRIGHT/M1_TOKEI`, coverage threshold 80 | **84 passed / 0 failed / 0 skipped**, 165.68s; **97.00%**, 647/667 statements, including worker subprocesses. |
| Continuous CLI example in fresh `temp/m1-p2-demo` | PASS, final revision **10**. Startup/A/B and common component survive; scoped review, structure edits, invalid deletions/parent cycles, legal business loop, synchronized one-winner revision race and missing historical binding all pass. Original P0 export is **8 callables / 3 calls**; changing the target changes the real edge/source version without modifying the explanation model. |
| Provider-free/native guard | PASS, 8 symbols/3 calls; telemetry absent, no forbidden provider/Python socket attempts or unfinished threads. No LLM path or P0 guard is imported into production. |
| `uv run black . --check` | Exit 0, 352 files. Commit hook also remains enabled. |
| Packaging and persisted model | Wheel builds (exit 0); archive bytes match all nine architecture modules and the native resolver. Installed CLI validates the continuous model at revision 10 without writing. Generated JSON Schema still matches runtime. |
| Real Linux mypy | **Exit 0**, 352 files, Debian WSL, CPython 3.12.13, frozen repository dependencies in a separate Linux venv. Baseline `origin/main` archive: **exit 0**, 333 files. This is native Linux execution, not just `--platform linux`. |
| Selected native Linux regressions | **12 passed / 0 failed / 0 skipped**, including resolver defaults/overrides, record impact, POSIX timeout flags and both original registry tests. |
| Windows `uv run mypy .` | Exit 1, one unchanged `static_analyzer/workspace_dependencies.py:78` SIGKILL attr-defined error. It is separate from the now-fixed introduced Linux error. |
| Windows registry test files | **131 passed / 4 failed / 4 skipped**. All four failures reproduce on unmodified fork `main` (4 failed in 1.13s): embedded-npm selection, non-executable Node, mocked embedded-node installation, and gzip chmod. They are baseline failures; full root-cause diagnosis is outside this review. |
| Whole repo `uv run pytest --cov=. --cov-report=term --cov-fail-under=80`, real M1 tools enabled | Collected **2783**; M1 rows completed without failures. At **300s**, stopped near `tests/infra/repo_utils/test_non_ascii_paths.py` (~37%); terminated the owned process tree, test process **exit 1**, elapsed 300.38s (bounded driver exits 0). Other failures observed; **no final coverage report, whole-repo 80% still unconfirmed**. |

Other full-suite failures remain **unattributed**. The Windows SIGKILL and four
registry failures above are baseline-reproduced; the registry order failures and
Linux constant error were introduced by this PR and are now fixed. Private
`CodeBoarding-tests` integration remains unrun. A Python audit probe is not an OS
network sandbox for Node/LSP subprocesses.

## Reproduction

Use the real-tool environment and M1 coverage command in the
[example guide](../../examples/architecture_model/README.md). For the ordering check,
run the following nodes alone, then prefix the first with
`tests/architecture_model/test_facts.py::test_real_python_export_and_failure_paths`:

```text
tests/infra/test_registry_coverage.py::TestRegistryAndVscodeConfigParity::test_every_registry_entry_has_matching_vscode_config_entry
tests/infra/test_tool_registry.py::TestToolRegistry::test_resolve_config_falls_back_to_embedded_nodeenv_node
```

Linux validation used `uv sync --frozen` with a dedicated
`UV_PROJECT_ENVIRONMENT=/home/zhan/.cache/codeboarding-m1-p2-venv`, followed by
`uv run --no-sync mypy .` from `/mnt/f/CodeBoarding`, and the same command from
the pristine main archive for comparison. Separate cache directories prevent
Windows/Linux mypy cache interference. M2 auto-refresh/rebinding and M3 playback
remain deferred.
