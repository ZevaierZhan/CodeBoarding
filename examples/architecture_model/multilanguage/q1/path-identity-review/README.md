# PR #7 路径身份往返修复

审阅基点：`d87eaaa700b574c49fc6c88361f3b5043313543a`。本轮只修复路径身份及缓存兼容性；同一 Draft PR，不开始 Q2，不整改已有 6 项全仓失败。

## 真实失败与修复结果

WSL Debian / **Python 3.12.16** 的真实 POSIX 文件系统同时创建 `a\b.py` 和 `a/b.py`，内容分别为 `literal`、`nested`。不是 Windows 模拟，也没有替换生产缓存类或其依赖。

| 检查 | 修复前 | 修复后 |
|---|---|---|
| 原始两个文件 | 不同 inode / 文件身份 | 仍不同 |
| `to_relative_path(a\b.py)` | `a\b.py` | `a\b.py` |
| 路径往返 | 错读 `a/b.py`，内容 `nested` | 原文件，内容 `literal` |
| `StaticAnalysisCache.save/get` | 两条路径均恢复为 `a/b.py`，两项内容均为 `nested` | 两个不同路径，分别为 `literal`、`nested` |

原始失败断言、JSON 结果和 traceback 见 [路径红灯](evidence/posix-red.log.gz)、[缓存红灯](evidence/posix-cache-red.log.gz)；修复后的同一探针与 POSIX pytest 见 [POSIX 验证](evidence/posix-final.log.gz)。[探针归档](evidence/reproducers.zip) 可在审阅基点和当前版本分别执行；解压到各 checkout 的 `temp/q1-path-review/`，从仓库根以该环境的 `uv run python` 执行，并令 `PYTHONPATH` 指向该 checkout。

## 路径协议与旧缓存

新 pickle 外层是 `{"path_format": "repo-paths-v1", "analysis": StaticAnalysisResults(...)}`，SHA 标签版本为 **v15**。每条序列化路径都有独立标签：

- `relative:a\b.py`：规范化仓库相对路径；只有 `/` 是目录分隔符，反斜线是 POSIX 文件名字符。
- `relative:a/b.py`：另一个文件，两者不合并。
- `relative:C:\b.py`：合法 POSIX 相对文件名，不能猜成 Windows 绝对路径。
- `posix:/external/file.py`、`windows:D:\external\file.py`、`windows:\\server\share\file.py`：显式绝对路径，不按当前根重新拼接。

这里的前缀是缓存编码，不是文件名、URI 或符号 ID。路径内容不做 URL 编解码，空格、`#`、`%`、冒号和反斜线不因前缀产生混淆；生产源文件路径只在 pickle 内带标签，恢复后回到本机原生路径。

原生输入与协议输入分开处理：缓存序列化明确把原生输入构造成本机 `Path`；外来的 Windows 相对输入用 `PureWindowsPath` 明确表达；解码后的规范相对路径用 `PurePosixPath` 表达，不再无条件替换反斜线。原有两项 Windows 分隔符测试只将输入改为显式 `PureWindowsPath`，所有原有期望断言保留。

兼容规则：

1. **有旧版本标签（包括 v14）的缓存整体失效**，由现有 engine-version 流程重新分析；已经丢失的双文件身份不能靠迁移补回。新旧版本都不会把不认识的 pickle 当成功结果使用。
2. 既有无标签、旧目录的缓存仍可供 ungated inspection，但仅恢复无歧义路径。相对路径含 `\`、带盘符（含看似绝对的盘符形式）或 UNC 等缺少来源信息的旧表示返回 cache miss，并记录具体异常及 traceback；SHA-gated / warm-start 仍拒绝无标签缓存。
3. 未知 `path_format`、缺失/非法路径标签、无法在当前操作系统表达的绝对路径、Windows 无法表达的 POSIX 反斜线/冒号文件名，都明确拒绝，不猜测为另一个文件。
4. 相对路径的 `..` 越界、盘符相对路径、实际 symlink 越界均拒绝；既有明确绝对路径保持外部路径身份，不因“看起来相似”而归入仓库。

序列化复用已有路径工具；只修改 `infra/repo_utils/path_utils.py` 和 `StaticAnalysisCache` 的路径读写边界，没有修改模型 schema、符号 ID、源码根、source hash、LSP URI 编码器、分组算法或 Kotlin Adapter。

## 最新验证

| 验证 | 最新结果 |
|---|---|
| Windows Q1 非 Kotlin 目标组 | **1810 passed / 48 skipped / 0 failed** |
| Windows 路径与缓存专项 | **92 passed / 4 skipped** |
| POSIX Python 3.12.16 路径与缓存专项 | **95 passed / 1 skipped** |
| M1–M5 + 真实 Python / TypeScript / Rust 导出 | **220 passed** |
| Node 业务播放器 | **7 passed** |
| Black / mypy / diff 检查 | **通过**；mypy 382 source files |

目标组 48 skips = 原有 29 Kotlin grammar + 15 workspace 前置条件 + 本轮 4 项必须真实 POSIX 文件系统的用例。Kotlin 29 项的 **nodeid 集合与 d87eaaa 逐项完全一致**，机制未改，未增加 Kotlin 跳过。详细结果见 [summary.json](evidence/summary.json)、[路径测试逐项状态](evidence/path-test-status.json)、[Kotlin 对照](evidence/kotlin-skips.json)及对应压缩原始 XML/log。

Windows 的 4 项跳过是三种 POSIX 字面反斜线文件名和真实 symlink 越界测试，它们全部在 POSIX 执行；POSIX 唯一跳过项是 Windows 专属“无法表达 POSIX 文件名时必须拒绝”测试。Windows 上保留纯路径协议测试，实际 POSIX 文件往返并未被它们替代。

回归还覆盖：缓存 source_files / CFG 节点 / diagnostics 的双身份，跨源码根同名文件，外部本机绝对路径，Windows 盘符与跨盘、UNC，POSIX 绝对路径，空格/`#`/`%`，反斜线 file URI 的 `%5C` 编码和真实回读，旧/未知格式拒绝及无歧义旧缓存读取。

```powershell
uv run pytest tests/static_analyzer tests/diagram_analysis tests/codeboarding_cli tests/test_optional_grammars.py -q -rs
uv run pytest tests/static_analyzer/test_cache_path_identity.py tests/static_analyzer/test_utils.py tests/static_analyzer/test_path_protocol.py tests/static_analyzer/test_analysis_cache.py -q
uv run pytest tests/architecture_model -q  # 显式设置既有 M1_* / M5_TOOLS 本地工具路径
uv run black .
uv run mypy .
node --test tests/architecture_model/viewer_engine.test.cjs
```

Windows 独立 worktree 复用原有 venv，验证时使用 `uv run --no-sync` 和显式 `PYTHONPATH`。POSIX 使用独立 Python 3.12.16 venv 和正常项目依赖；没有安装 Kotlin 工具链、grammar 或 Kotlin LSP。Linux 未运行全仓 pytest，也未运行 Linux 原生 Python/TS/Rust LSP 导出；必要的真实导出在 Windows 的 220 项模型专项中执行。

## 未改变的全仓门禁

本轮按要求不重跑或整改已有 6 项全仓失败，也没有重跑全仓 coverage。**39.11% 覆盖率、2882 passed / 6 failed / 59 skipped 是审阅基点 d87eaaa 的历史全仓结果，不是新 head 的全仓结果**；80% 门槛仍未获全仓通过证明。

原 6 项问题和归因记录见 [历史剩余问题](../evidence/remaining-issues.json)：5 项已证明是旧 main 失败，另 1 项 manifest 临时目录清理间歇失败曾在 20 个独立进程复跑通过。本轮未将它们转为 skip、删除断言或修改 coverage omit / 阈值。
