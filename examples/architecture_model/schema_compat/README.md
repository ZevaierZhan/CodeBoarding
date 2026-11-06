# Optional analysis-topic compatibility

`model.json` is a complete synthetic schema 1 model with one operation, one
comparison and string-valued analysis questions. Its facts represent only the
synthetic source `def run(): return 1`. No private evidence is included.

Validate with the prepared engine environment:

```sh
uv run --no-sync python -m architecture_model model --file examples/architecture_model/schema_compat/model.json validate
```

Run isolated acceptance against a real model using absolute paths:

```sh
uv run --no-sync python -m examples.architecture_model.schema_compat.accept --model MODEL --source-map SOURCE_MAP --output NEW_PRIVATE_DIRECTORY
node examples/architecture_model/schema_compat/browser_check.cjs PLAYWRIGHT_MODULE CHROME_EXECUTABLE NEW_PRIVATE_DIRECTORY
```

The acceptance script records original hashes, copies the full model, validates,
reads, runs coverage-report, exports HTML, changes one existing facet interpretation,
previews and applies with expected revision, and checks preservation and re-export.
It refuses an existing output directory. Treat every generated output as private;
none should be committed or uploaded. A successful format check and browser run
are separate from source agreement, interpretation review and runtime verification.
