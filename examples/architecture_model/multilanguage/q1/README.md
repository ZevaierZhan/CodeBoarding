# Q1 非 Kotlin 静态分析质量基线

> 本页为 d87eaaa 的初次验收记录；后续缓存路径身份修复的最新格式、兼容策略和验证结果见 [PR #7 路径往返修复](path-identity-review/README.md)。

本轮从 fork main `cca03766` 创建 `qa/non-kotlin-static-baseline`。该 main 已包含 M5 merge `7d38098c3ae975ced36ad67887355efd4fd34a05` 及后续匿名回调身份修复。没有修改 M5 PR，没有向 upstream 推送，也不自动合并。

## 结果与口径

| 验证 | main 修复前 | Q1 最终 |
|---|---:|---:|
| 全仓通过 / 失败 / 跳过 | 2769 / 126 / 30 | 2882 / 6 / 59 |
| URI 相对路径异常 | 29 | 0 |
| 全仓覆盖率 | 38.93% | 39.11%（80% 门禁未通过） |
| 原生分析器目标组 | — | 1783 passed / 44 skipped / 0 failed |
| M1–M5（含真实工具导出） | — | 220 passed |
| Node 业务播放器 | — | 7 passed |

92 项干净 main 失败转为通过，29 项 Kotlin grammar 阻断精确转为跳过，新增 22 项回归。目标组可执行测试通过率 **100%**（1783/1783）；44 项跳过中有 29 项 Kotlin、15 项原有 workspace 前置条件。

不包含缺 Kotlin 阻断的全仓集合为 2918 项：2882 通过、6 失败、30 项其他前置条件跳过；可执行通过率 99.79%，仍非全仓绿色。

M5 原 122 项在干净 main 有 120 项仍失败、2 项已通过；最终 88 项通过、29 项 Kotlin 跳过、5 项失败。当前 main 另有 6 项失败，本轮全部修复；全仓另新观察到 1 项临时目录清理瞬时失败。

本次全仓运行中的模块覆盖率：static_analyzer **87.07%**、architecture_model 73.99%、infra/repo_utils 70.51%、diagram_analysis 56.46%。独立原生工具测试未合并进全仓 coverage，模块数字不能替代全仓 **39.11%**。完整分母见 [coverage-summary.json](evidence/coverage-summary.json)。Black、mypy（381 source files）和 git diff --check 通过。

完整逐项状态见 [all-test-status.json.gz](evidence/all-test-status.json.gz)，失败前后对照见 [status-changes.json](evidence/status-changes.json)，M5 原有 122 项的本轮状态见 [m5-122-status.json](evidence/m5-122-status.json)。这些文件同时保留失败消息和跳过原因，不能把跳过算作通过。

最初在已有工作区测得 2766 passed / 129 failed / 30 skipped。该工作区包含历史 `temp/` 副本；初版离线 wrapper 还缺少 Windows multiprocessing 的 `__main__` 保护。最终对照改在独立、干净的 main worktree 上执行，使用带入口保护的离线 wrapper。初次结果仅作为环境排查证据，不用于夸大本次修复数量。

## 精确隔离 Kotlin grammar

`tests/conftest.py` 只在测试实际请求 `language_pack.get_language("kotlin")` 时检查已配置缓存的 `downloaded_languages()`。未缓存时添加 `requires_kotlin_grammar` 标记并给出明确 SKIP 原因，不调用可能下载的 native loader。其他语言、Kotlin Adapter 的配置/命名等不需要 grammar 的测试、同文件中的非 Kotlin 用例照常执行；不使用名称过滤或整文件跳过。

缓存已有 grammar 时走原 loader，加载错误正常失败。`tests/test_optional_grammars.py` 用 native loader spy 验证“缺失时从不进入下载入口”“已缓存时继续加载且错误不会转为 SKIP”，并真实解析 Python、Java、Rust、TypeScript。实际 29 项依赖清单见 [kotlin-skips.json](evidence/kotlin-skips.json)，包括其他文件中的 Kotlin 参数化用例。

全仓 collect-only 的守卫同时禁止 `get_language` 和 `download`，2947 项完成收集且两入口均未被调用。测试期间没有安装 Kotlin、下载 grammar 或配置 Kotlin LSP。产品 Kotlin Adapter 和生产 grammar-loader 语义保持原样。

## 路径与 URI 根因

- LSP 初始化直接对根路径调用 `as_uri()`，与文档请求先 `resolve()` 的协议不一致。现在构造客户端时固定项目根及 workspace folders 的绝对身份，初始化、重启和文档请求使用合法 URI。
- Windows 的 `Path("/repo/...")` 是盘符未定的 rooted path，不是可直接编码为 URI 的绝对路径。LSP/edge/hierarchy/cache fixture 现在为符号、URI 和期望值使用同一原生绝对路径，没有删除原有定位断言。
- `normalize_repo_path` / `to_relative_path` 原来用宿主 `Path.is_absolute()` 判断所有序列化路径，导致 POSIX 测试路径在 Windows 上保留仓库根并污染分组 prefix。现在按路径 dialect 处理 POSIX、Windows 盘符与 UNC；已有原生路径仍解析真实身份，仓库内路径统一为相对正斜线，外部路径不强行归入仓库。相同根前缀的兄弟目录不会误匹配。
- POSIX 绝对文件名中的字面反斜线予以保留；只在既有相对缓存路径协议和 Windows dialect 边界解释 Windows 分隔符，没有对任意字符串做全局替换。
- `uri_to_path` 保留 Windows UNC authority，拒绝相对 `file:` URI 以及含未编码 query/fragment 的 URI，避免错误地把它们归为某个本地文件。空格、`#`、`%` 的合法百分号编码可往返。
- 展示引用统一用 repo-relative helper；移除 `startswith(repo_root)` 的目录判断，避免兄弟目录被错误裁剪，且保持跨平台正斜线展示。

独立回归：`uv run pytest tests/static_analyzer/test_path_protocol.py -q`，覆盖相对/绝对路径、盘符、盘符大小写、跨盘、POSIX、空格、编码、UNC、相对根、目录边界及 POSIX 字面反斜线。WSL Debian / Python 3.13.5 另外通过 10 项标准库 helper 对照；因其 Python 版本不满足项目 `<3.13` 约束，未执行 Linux 完整 pytest，不声称已验证 Linux 全套。

## 静态分析语义与环境隔离

- **真实缓存错误**：Windows 对只读 fd 的 `fsync` 返回 `Bad file descriptor`。`_atomic_copy` 保留 `mkstemp` 的可写 fd，完成 copy、同步、关闭后再 rename；保留复制元数据和异常临时文件清理。原有复制、恢复、覆盖和 SHA 复制失败清理测试提供修复前红、修复后绿的回归。处理的复制异常现在记录 traceback。
- **匿名回调归属**：fixture 的 `file_symbols` 索引键写死正斜线，实际 `SymbolInfo.file_path` 在 Windows 上使用原生路径。只改索引键，不改 6 项归属断言，也不改 main 的回调身份或归属逻辑。
- **类型层级**：fixture 的 URI 与符号路径统一后通过；生产层级算法未修改。
- **组件分组**：repo-relative prefix 修复后原有分组断言通过；未调整组件 ID、分组算法或增量策略。
- **结果过滤**：测试用 `Path.parts` 判断 `tests` 路径段，不再假定输入是 POSIX 字符串；未改变生产 ignored-files 策略。
- **可选工具 fixture**：Java/.NET 假工具同时遵守宿主 executable 名称；C# 模拟命令的路径比较按 `Path` 规范化，保留失败分支断言。Homebrew 风格路径解析采用受控 `resolve` fixture，不再依赖 Windows symlink 特权。
- **TypeScript 原生 workspace**：只留 PATH 的子进程环境会让 Windows Node 以 `ncrypto::CSPRNG` assertion 崩溃；保留 `SystemRoot/WINDIR/TEMP/TMP` 后 6 项真实 tsserver 用例通过，仍禁用自动 typing acquisition，不安装工具。
- 每项测试从仓库根开始并由 monkeypatch 恢复 cwd；从外部 cwd 执行独立回归也通过。包扫描先剪枝忽略的临时/工具目录，且显式 namespace package 用实际目录验证；编码扫描排除本就忽略的 `temp/`。没有放宽源码编码断言。

## M1–M5 保持证明

`git diff origin/main -- architecture_model tests/architecture_model` 为空，模型 schema、源码根、符号 ID、source hash、跨语言契约、版本维护和 M5 Verification 精确快照归属实现均未修改。真实工具参数显式传入已有本地配置，执行了全部 220 项模型测试，包括 Python 导出及其失败路径、TS/Rust 单独与混合根导出、回调双路径、跨根版本维护和验证归属。Node 原生业务播放器 7 项通过。

中途修改提取器期间，真实导出曾被“Source or extraction configuration changed during analysis”保护阻断；代码冻结后整组重跑通过。没有移除、绕过或弱化这项保护。该中途失败日志保留在复现归档中。

## 复现

Windows，Python 3.12，仓库已有 `.venv`。本轮没有 `.env`，不需要凭据；单元测试与显式本地工具事实导出均可执行。隔离 worktree 复用既有 venv，使用 `uv run --no-sync` 和显式 `PYTHONPATH` 指向本 checkout，防止 editable install 指回另一工作区。正常独立安装的 checkout 可直接 `uv run`。

```powershell
uv run pytest tests/static_analyzer tests/diagram_analysis tests/codeboarding_cli tests/test_optional_grammars.py -q -rs
uv run pytest --cov=. --cov-report=term --cov-fail-under=80
uv run black .
uv run mypy .
node --test tests/architecture_model/viewer_engine.test.cjs

# 不安装工具，指向已有的本地 native 配置：
$env:M5_TOOLS = '<existing-tools.json>'
$env:M1_NODE = '<existing-node.exe>'
$env:M1_PYRIGHT = '<existing-pyright/langserver.index.js>'
$env:M1_TOKEI = '<existing-tokei.exe>'
uv run pytest tests/architecture_model -q
```

main 的离线基线可将 [reproducers.zip](evidence/reproducers.zip) 的 `baseline.py` 解压到该 main checkout 的 `temp/q1/`，运行 `uv run python temp/q1/baseline.py`。wrapper 在缺 grammar 时明确抛错而不是跳过，以统计原始 Kotlin 阻断，同时禁止进入下载 loader。先不要使用 Q1 分支的 conftest 运行这个“修复前”对照。

## 剩余问题与证据

最终 6 项失败全部保留：4 项安装器 portability 测试、1 项 WSL bash 路径测试已在干净 main 同样失败；另外 1 项 manifest overwrite 测试的 `TemporaryDirectory` 清理触发 `WinError 145`，main 未复现，随后 **20 个独立进程复跑全部通过**。全仓仍按该次 6 项失败报告，没有用重跑覆盖成 5 项失败，也未将这个新观察草率归为原有问题。

完整复现命令、实际错误、优先级和影响边界见 [remaining-issues.json](evidence/remaining-issues.json)。全仓失败仍按失败报告，没有改为 skip，也没有将分析器目录排除出回归。原有覆盖率 omit 和 80% 门槛不变；模块覆盖率不能替代全仓门禁。

原工作区还保留了一份未跟踪的 Q1 临时证据目录：自动审批拒绝了其递归清理。最终提交只包含独立 worktree 中的代码和精简证据；原工作区的其他工作没有纳入本 PR。
