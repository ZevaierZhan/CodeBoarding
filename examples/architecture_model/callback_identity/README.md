# Anonymous callback identity regression

Repeated inline callbacks are separate lexical declarations even when tsserver
gives them the same display name, such as `value.then() callback`. Strict facts
export rejected such valid TypeScript before this fix. Without strict mode,
registration could overwrite one declaration with another.

Anonymous qualified-name segments now include their one-based definition position
(`@line:column`). Display names remain native. The same identity segment is used
in primary names, aliases and descendants, independent of registration order and
absolute checkout location. Alias equivalence requires the same definition
location, so similarly named declarations cannot merge through the alias index.
Named collisions still fail the existing strict check.

The fixture includes multi-line and same-line sibling callbacks, plus identically
named functions nested under different callbacks. The real-tool regression checks
six distinct callbacks, two distinct nested declarations, and the actual call
edges through both callback branches. Calls inside anonymous scopes retain the
existing attribution to the enclosing named declaration.

```powershell
$env:M5_TOOLS='C:/path/to/tools.json'
uv run --no-sync pytest tests/static_analyzer/test_anonymous_identity.py tests/architecture_model/test_callback_facts.py
```

Definition positions distinguish scopes within one snapshot; they are not stable
business IDs. Moving a callback can change its source symbol identity. Existing
fact snapshots and bindings remain immutable and retain their old names; new
exports record a different implementation fingerprint. Use ordinary explicit
source maintenance and rebinding rather than rewriting historical evidence.

Receipts under `evidence/` preserve actual pre-fix unit and native-export failures,
post-fix checks and baseline comparisons. The native pre-fix CLI was the installed
merged-main build, run outside the engine checkout. No private application source
or facts are included here.

Validation on Windows / Python 3.12.13:

| Check | Result |
|---|---|
| Pre-fix unit regression | 5 failed / 1 passed, exit 1 |
| Pre-fix native fixture export | Failed, no facts published |
| New unit + real tsserver regressions | 7 passed |
| M1–M5 + symbol registration regressions, real Python/TS/Rust/mixed tools | 266 passed in 631.93 s |
| Architecture model + SymbolTable coverage | 95.40%, unchanged 80% threshold |
| SymbolTable coverage | 207 / 212 statements, 97.64% |
| Black / mypy | Passed, 379 Python files |
| Node player tests | 7 passed |
| Wheel build and installed CLI export | Passed |

Broader selections retain 13 failures also reproduced with the exact merged-main
SymbolTable (`7d38098c3ae975ced36ad67887355efd4fd34a05`) in the same environment:
six attribution tests and one converter test rely on slash-based paths on Windows;
six workspace-plugin tests report `StopIteration` while driving tsserver. The
latter became runnable after the SDK was installed and were previously skipped.
All other production files are unchanged, so the baseline comparison swaps only
the SymbolTable implementation. Logs preserve the exact selections and failures;
group counts overlap and must not be summed. These failures remain unresolved.
The original full-repository coverage gate remains unpassed, and private
integration was not run. No full-repository rerun is claimed here.
