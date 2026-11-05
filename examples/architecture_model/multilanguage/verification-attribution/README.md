# Implicit binding evidence ownership receipts

Review baseline: `f18fed3dff13ce9fe7f00056a965317d7893fbb3`.
See [the report](../../../../docs/design/architecture-model-m5-verification-attribution.md)
for protocol, outcomes and limits.

- `red.log.gz` / `red.exit.txt`: actual pre-fix run of
  `uv run --no-sync pytest tests/architecture_model/test_m5_p2.py -k unowned -v -s`.
  The two tests existed before production edits; exit 1. Output includes the real
  committed revision and invented snapshot projection.
- `green.log` / `green.exit.txt`: final full P2 selection, 29 tests, exit 0.
- `specialized.log` / `specialized.exit.txt`: M1–M5 suite and module coverage gate.
- `black.log`, `mypy.log`, `node.log`: repository checks and seven Node tests.
- `browser.json`: local Chrome via Playwright, inspecting the old unowned check.
- `playback.json`: existing canonical revision-11 HTML, player and model byte checks.
- `java-vue.json`: capability replay using committed audited real facts, not a new export.

Environment: Windows, Python 3.12.13, pytest 8.3.5, same repository `.venv` as the
preceding review. The specialized suite ran with:

```powershell
$env:M1_NODE='D:\Progrm Files\nvm4w\nodejs\node.exe'
$env:M1_PYRIGHT='F:\CodeBoarding\temp\p0-tools\node_modules\pyright\langserver.index.js'
$env:M1_TOKEI='F:\CodeBoarding\temp\p0-tools\tokei.exe'
$env:M5_TOOLS='F:\CodeBoarding\temp\m5\tools.json'
$env:COVERAGE_FILE='F:\CodeBoarding\temp\m5-p2\attribution-final.coverage'
uv run --no-sync pytest tests/architecture_model --cov=architecture_model --cov-report=term --cov-fail-under=80 -q
```

To reproduce the browser check, first generate the read-only fixture HTML:

```powershell
uv run --no-sync pytest tests/architecture_model/test_m5_p2.py -k unowned --basetemp=temp/m5-attribution-repro
node examples/architecture_model/multilanguage/verification-attribution/browser_check.cjs temp/m5-tools/node_modules/playwright-core 'C:/Program Files/Google/Chrome/Application/chrome.exe' temp/m5-attribution-repro/test_old_unowned_implicit_veri0/unscoped.html temp/implicit-browser.json
```

Local native tools and Playwright must already be installed at those paths.
These receipts do not claim a passing full-repository gate or private integration.
