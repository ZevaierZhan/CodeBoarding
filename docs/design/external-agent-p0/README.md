# P0 源码可行性与复现报告

结论：可以复用真实静态引擎、限定分组的语义回填、原生 JSON 和文档 renderer；持续维护的自主逻辑组件、场景步骤、证据分型与更新责任需要新增模型操作层。此 PR 是调查与小验证，不是完整产品。

产品规格和下一阶段任务见 [external-agent-models.md](../external-agent-models.md)。`experiment.py` 是本 PR 的内部 Python API 适配脚本，不是原生已有 CLI。

## 调查版本与仓库决策

调查日期：2026-11-04（Asia/Shanghai）。开始时 `F:\CodeBoarding` 为空，无未提交工作，无 `.codegraph/`；按约定未建立索引。读取根 AGENTS.md、CLAUDE.md、CONTRIBUTING.md。没有创建内部 LLM `.env`；这是用户明确要求的路径。

| 层 | 固定输入、来源与许可 | 决策 |
|---|---|---|
| 核心 Python 引擎、工作流、文档 renderer | [CodeBoarding commit 156806c](https://github.com/CodeBoarding/CodeBoarding/tree/156806c0eedcfded65eb8d02c39b3cf618a8254b)，`pyproject.toml` 0.15.3，根 LICENSE MIT，默认 main | gh 用户 ZevaierZhan，无已有主 fork，创建 [ZevaierZhan/CodeBoarding](https://github.com/ZevaierZhan/CodeBoarding)；集中交付一个 fork 内 Draft PR |
| 独立 MCP | [commit 4757d65](https://github.com/CodeBoarding/CodeBoarding-MCP/tree/4757d652a4716598b2de171a6fdf9b7c83c68e31)，mix-server 0.1.0，独立 LICENSE MIT | 只读 checkout 到临时目录，不 fork；没有本轮需要修改的模型操作实现 |
| VS Code wrapper / Webview / 扩展 MCP | [Marketplace 0.14.2](https://marketplace.visualstudio.com/items?itemName=Codeboarding.codeboarding)，发布日期与页面内容按本次获取记录；根引擎未包含对应 TS 源码树 | 发布包调查结果见下面；不凭引擎 MIT 推断全部许可；不 fork 未确认来源的 wrapper |
| 官网交互平台 | [app.codeboarding.org](https://app.codeboarding.org)、Marketplace 产品说明 | 独立产品表面；未执行线上上传/账户操作，公开后端源码和模型写 API 未确认；不作为 MVP 的前置依赖 |

本机全局 Git 代理不可用；本次 clone/fetch/push 命令用 `git -c http.proxy=`，不改全局配置。fork/main 为调查 base，工作分支 `p0/external-agent-models`；PR 明确 `--repo ZevaierZhan/CodeBoarding --base main`，不向上游提交、不合并。

## 当前源码入口与能力边界

以下文件行号均对应固定核心 commit；可在上面的 commit 链接内查阅，不能把函数名线索当成验证结果。

| 问题 | 源码依据 | 结论 |
|---|---|---|
| 无 LLM 静态提取 | `static_analyzer/__init__.py:287` StaticAnalyzer，`:712` analyze；`static_analyzer/scanner.py:63` ProjectScanner | 独立构造，需 Tokei、真实 LSP 及 parser 依赖。context manager 启停；`skip_cache=True` 全静态，changed_files+cache 可 warm start。不需要 provider |
| 原 CLI 配置阻塞 | `codeboarding_cli/bootstrap.py:29` bootstrap_environment | configure_models、validate_api_key_provided 在工具准备前执行。不能宣称现有 full CLI 已有无 provider 开关 |
| 库内模型调用 | `diagram_analysis/diagram_generator.py:755` _grouper、`:772` _scope_agent、`:800` _apply_scope_semantics | 默认 affinity 聚类不调用 LLM，planner grouper 会；语义分析需要 ScopeAnalysisAgent。模型初始化是按需的，不是所有内部 API 构造都必然调用 |
| 结构导出与范围上下文 | `agents/llm_renderers/scope.py:31` render_scope_context；`static_analyzer/analysis_result.py`；`static_analyzer/cfg/edge.py:13` | scope context 是语义输入 JSON，含分组、文件、边界理由、调用例子，预算会裁剪。完整图提供 symbol、文件、行、调用点、contains/inherits；typeref/import 类型存在但 edge.py 明说尚无引擎发出，注册/配置关系不保证提取 |
| 外部语义写入 | `agents/scope_analysis_agent.py:52` ScopeComponentSemantics、`:86` ScopeAnalysisResult；`diagram_analysis/scope_assembly.py:95` apply_semantics | Python 入口可复用；固定 group_id，名称/描述/key_entities/关系。未知组被过滤，成员、父子、独立 rationale 不是 schema 字段；无静态边的关系还需 evidence 和有效 key_edges，否则丢弃。P0 描述不能把 evidence 字段标签误当实际运行证明 |
| JSON 与回读 | `diagram_analysis/analysis_json.py:149` UnifiedAnalysisJson、`:452` build_unified_analysis_json、`:508` parse_unified_analysis | root/nested components、relations、files、methods_index、metadata/tree_spec。手工解析仅选已知字段，新增字段不能直接获得持久化保证；schema 类型通过不等于引用/来源/业务含义通过 |
| 保存 | `diagram_analysis/io_utils.py:359` save_analysis、AnalysisStore、write_text_atomic、snapshot_analysis/restore_analysis | 原生已有 filelock 与同目录临时文件替换，可复用；full/incremental 包装有 analysis.json 回滚。不是多文件事务或 expected_revision 协议，单次 atomic write 也不替代语义校验 |
| 原生划分 | `static_analyzer/clustering/service.py:96` ClusteringService；`names/spec.py:31` ComponentRule、`:86` ScopeSpec、`:136` SPEC_VERSION；`names/replay.py:50` replay | 原生不是简单目录分组：规则可按前缀、词、文件、角色、affinity 分组。成员归属由 TreeSpec 重放决定。直接改 file_methods 可保存，未改 TreeSpec 时刷新会恢复；没有已公开外部 Agent 结构操作契约 |
| 展示 | `codeboarding_cli/render.py:16`；`output_generators/rendering.py:113` _load_entries；`output_generators/html.py:12` generate_cytoscape_data、`:64` generate_html | 真实 HTML 为 Cytoscape 文档图和详情，组件名称/描述/key_entities 可见，展开链接到子 HTML；节点及文件名以 sanitize(name) 派生，改名影响视图身份。独立理由、场景步骤、证据分型、影响视图和当前步骤定位均缺失 |

业务场景不能用 components_relations 数组替代。它没有步骤身份、执行次序、条件转移、场景间复用或子流程协议。图关系方向也不能证明一次实际执行顺序。源码可以证明 fixture 有三个调用，不证明所有动态业务边完整。

## 模型方案比较与推荐

| 方案 | 优点 | 代价/限制 |
|---|---|---|
| 扩展原生 Component/TreeSpec | 部分层级和 renderer 可以沿用 | 原生单一 ownership、点分 ID、聚类生命周期与 file_methods 更新耦合；多逻辑解释共享源码、跨层级移动、场景引用需改深层算法及所有转换；未知字段当前丢失 |
| 关联模型引用原生事实（推荐） | Agent 自主逻辑身份和来源分型，不受静态 ownership 限制；结构可刷新而解释保留；首版版本化 JSON 即可 | 新增严格校验、操作库、事实适配及只读展示；原 renderer 只能作为有限投影，必须声明投影损失 |

推荐先建立模型操作库和 CLI，而非把业务解释塞进 name/description 后称为自主建模。P0 将划分理由写进 description 仅验证可见链路；正式模型应有独立 rationale 和 claim_kind。场景引用逻辑 component_id 与 binding_id；同一源码可以支持多种逻辑解释，原生 component_id 只作可失效映射。

## 刷新责任与身份范围

| 路径/变化 | 代码证实的行为 | 实验范围与应对 |
|---|---|---|
| full | run_full/generate_analysis 重建全树、重新 draft TreeSpec、语义回填并保存，旧未知字段不被保留 | 不执行内部 LLM full；根据源码结论，不能拿 full 作为解释维护机制 |
| incremental | static warm start + TreeSpec 重放（生产路径读取持久化 spec；P0 实验仅复用内存 service.spec） + 受影响 scope 语义更新；未变组继承既有字段，重建 file_methods/关系；引擎版本冲突 CLI 可按约定恢复 full | 实验只调用静态 warm start 与聚类/成员重放，完整语义增量未执行；新增解释文件不得由此覆盖 |
| partial | 针对 component_id 展开 subtree，保存既有其余 subtree，准备受限结构/语义 | 完整语义 partial 未执行；不是结构编辑接口，也不是扫描全仓更新 |
| 函数体修改 | method key 为 `<file_path>|<qualified_name>`；content_hash 变化可判别，分组重放可保留 ID | P0 实测体编辑；描述保留不证明仍正确；实验保留了“乘十”的旧描述，正好说明必须标记复核 |
| 行增减 | key 不含行，位置与 hash 可更新；原生 source reference 修复需重新 resolver | 本轮未跑行移动实验；不可称持久化行号稳定 |
| 文件移动、符号改名 | key/path/qname 会变；原生按文件/单位、基线与 spec 处理，不能保证外部绑定 identity | 本轮未跑；建议 old binding 转 missing/ambiguous，保留旧版本/位置/hash/描述与候选，不自动认同 |
| 源码删除 | 静态更新 invalidates 文件/边，原生可删除空规则、关系或 unresolved 引用 | 本轮未跑；解释层保留历史对象与待复核，显式 delete/redirect |
| 完整重建/层级收缩 | draft_tree 的 ID 不是全局身份保证；TreeSpec.reroot 明确可能重新映射 ID | 本轮未跑；逻辑 ID 独立于 native ID，刷新只修订映射 |

## CLI 与 MCP

必要操作先于传输：范围读取、源码依据查询、候选校验、同 ID 更新、结构操作、场景引用、refresh/diff。CLI 足够启动 M1，可用 JSON 输入输出和退出码；后续 MCP 应调用同一库，不重复实现事务和校验。

独立 MCP 的真实工具名是 `tools/get_codebase_context.py` 内的 `get_context_with_code` / `get_context_without_code`（README 的 onboarding 名称与实现不同）。`server.py` 创建 FastMCP；`utils/read_repo.py` 从 GitHub main 的 Markdown 聚合、选择性替换源码链接并写 `.cache`。这不是本地 CodeBoarding 模型存储；缓存无 revision 刷新契约；没有 model apply、结构更新或 source-refresh 工具。不值得为 P0 fork。它的 formatting helper 可参考，但没有关键模型写能力可直接复用。

扩展内 MCP 与独立仓库不能仅从“可配置 MCP”判定相同，发布包的实际工具与数据源调查见实验记录补充。官网、VS Code Webview 与本文档 HTML renderer 分属不同实现；只有 HTML 是本轮实际验证的公开 renderer。

## 复现

输入是本目录 `fixture/*.py.txt` 的受控测试 fixture（不是外部生产仓库）。脚本复制成 `.py` 后交给真实引擎，不用伪造 StaticAnalysisResults。Python 3.12，依赖使用仓库已有 uv.lock。下载工具、虚拟环境与缓存都在 ignored temp，不提交。

PowerShell，从仓库根执行：

```powershell
uv sync --frozen --python 3.12
npm install --prefix temp/p0-tools --cache temp/p0-npm-cache --no-audit --no-fund pyright@1.1.400
Invoke-WebRequest 'https://github.com/CodeBoarding/tools/releases/download/tools-2026.04.05/tokei-windows.exe' -OutFile temp/p0-tools/tokei.exe
# 对照 registry.py 校验工具 hash；Windows 预期：
# 7db547cb6bfa1722e89ca52a43426fb212aa53603a60256af25fb6e59ca12099
Get-FileHash temp/p0-tools/tokei.exe -Algorithm SHA256
$env:PATH = (Resolve-Path temp/p0-tools).Path + ';' + $env:PATH
# experiment.py 在导入原生模块前自行关闭遥测；无需从父进程继承这两个变量。
uv run python docs/design/external-agent-p0/experiment.py --output temp/p0-results --pyright-js temp/p0-tools/node_modules/pyright/langserver.index.js
uv run codeboarding-render temp/p0-results/native/analysis.json --format html --output-dir temp/p0-results/html
```

Linux/macOS 使用同 release 的 `tokei-linux`/`tokei-macos`，校验 registry.py 对应 hash，赋可执行权限并放入 PATH；本轮执行环境为 Windows，其他系统尚未运行。

预期检查：fixture 三条调用及位置；ScopeAnalysisResult 与 UnifiedAnalysisJson schema；save/reload 成员和 ID；resolved key_entities；内部调用 guard 零次；成员移动可保存但被 native replay 恢复；体编辑改变 content_hash。结果文件和 HTML 需要分别检查，不能只看 schema。

LLM 排除证据：脚本不读 user provider 配置或进入 bootstrap；profile 在主线程及新 Python 线程对配置/校验/初始化、ScopeAnalysisAgent.analyze 和 LangChain 调用入口抛错；不可卸载的 Python audit hook 拦截 socket.connect/getaddrinfo/sendto，覆盖主线程、新线程和退出回调；telemetry 在原生导入前关闭并断言 client 为空。LSP 是 stdio 子进程；该 guard 不能证明任意第三方子进程绝不访问网络，声明范围限于本脚本路径和固定 Pyright。外部语义是实施 Agent 根据八个源码文件编写的固定样例，验证写入链路，不证明业务分析自动化。

实验 A/B 与检查的实际运行结果在同目录 `results.md` 中记录，机器摘要见 `results.json`。完整增量 LLM 流程、真实业务执行、官网/VS Code 运行操作、文件移动/重命名/删除/完整重建尚未验证。


## P2 审阅整改复现（2026-11-04，17:08 起）

本轮机器产物、快照和截图已替换为本轮真实输出；上一轮调查与工程检查在 results.md 的历史章节保留。执行前 `.env` 不存在，未建立 provider 配置。生产源码、锁文件、fixture 保持不变，没有新增依赖。

在上述已准备好的环境中，从仓库根运行（每轮使用新的输出目录）：

```powershell
$env:PATH = (Resolve-Path temp/p0-tools).Path + ';' + $env:PATH
Remove-Item Env:CODEBOARDING_TELEMETRY -ErrorAction SilentlyContinue
Remove-Item Env:DO_NOT_TRACK -ErrorAction SilentlyContinue
uv run python docs/design/external-agent-p0/experiment.py --output temp/p2-final --pyright-js temp/p0-tools/node_modules/pyright/langserver.index.js
# 期望 0；results.json: status PASS, telemetry_client_absent true, guard_attempts []
uv run python docs/design/external-agent-p0/check-guard-negatives.py temp/p2-final temp/p0-tools/node_modules/pyright/langserver.index.js
# 期望 0：旧实验完整链路中注入并吞掉一次连接异常仍退出 0；新版 caught/thread/exit 探针均退出 1。
$env:P0_PLAYWRIGHT_MODULE = 'C:\Users\BW011222\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright'
$env:P0_BROWSER_CHANNEL = 'msedge'
node docs/design/external-agent-p0/check-render-negatives.cjs temp/p2-final
# 期望 0：两类故障页面旧检查器退出 0、新检查器退出 1；最后正常页面退出 0。
node docs/design/external-agent-p0/check-render.cjs temp/p2-final
# 单独检查正常页面，期望 0。
```

Playwright 路径是本次复用的桌面运行时；其他机器可按前文安装 Playwright 1.62.1 后将变量设为对应模块绝对路径。两个负例程序从本地 Git 中读取固定审阅基线，不需要在线访问 GitHub。原始日志和临时浏览器 HTML 均在 ignored temp。

`p0_guard.py` 在标准库导入后、jsonschema/CodeBoarding 导入前设置原生 service.py 真正识别的两个开关，并安装保护；分析前断言原生 singleton 的 `_client is None`，没有可发送/flush 的客户端。不会通过 flush 发送积压事件。原生 StaticAnalyzer context manager 先关闭固定 Pyright stdio 服务器，再退出实验临时目录；main 的 finally 对新增 Python 线程进行最多十秒的合并，未结束则失败。进程退出时最后运行的实验 atexit 回调再次检查线程与累计 attempts，才写最终状态并打印 PASS/FAIL；失败使用非零退出，防止 atexit 异常不影响退出码。保护从不解除。RUNNING 会先覆盖旧结果，未完成核心断言只能得到 FAIL。

profile 覆盖主线程及新建 Python 线程的指定 LLM 配置/调用入口；audit hook 覆盖整个解释器中使用 CPython socket API 的连接、域名解析和 sendto，包括线程和退出回调。它不是 OS 防火墙，也不证明原生扩展直接系统调用或任意第三方子进程无法联网。实际外部工具边界仍限于 pinned Tokei 14.0.0、Node 24.20.0 和 Pyright 1.1.400 stdio 路径。故障注入地址为保留文档地址，调用在 OS connect 之前被截获；没有访问 PostHog 或 provider。

浏览器在导航前监听 pageerror、console error 和脚本加载失败，等待真实 Cytoscape core ready。只读探针读取原生库在 `#cy._cyreg.cy` 注册的实例，核对非 headless、有效可见绘制表面、每个节点/边的可见性与渲染边界、四个节点和 1→2、2→3、2→4 三条关系。该内部注册点属于固定 Cytoscape 3.23.0 的验证适配；库升级需要复核。canvas 仅用于确认有实际绘制表面，不以数量验收。检查一直覆盖到截图及隔离 context 关闭，随后统一判定页面异常。没有修改 renderer 或构造替代图。

实验 B 的重放参数仍是同进程内 `service.spec`，不能称已从磁盘重新加载 TreeSpec 后跨进程恢复；该验收留给 M1。保存/重读 analysis.json 已验证，与跨进程 spec 恢复是不同证据。


## P2 退出收尾补充验证

`finish()` 默认保持失败标记；报告写入、日志、stdout/stderr flush 全部完成后才允许成功。最外层 finally 执行 `os._exit(1)`，保证异常不会被 atexit 忽略后变成退出 0。收尾异常时尝试写 FAIL 并记录 traceback；这两步再次失败也不能跳过非零退出。磁盘持续不可写时，启动时的 RUNNING 文件可能留存，不能视为成功，进程退出码仍为 1。

```powershell
uv run python docs/design/external-agent-p0/check-finish-negatives.py temp/p2-finish-final
# 驱动期望 0：固定 a5b405ac 基线的 report+guard 为 0（复现缺口），新版十个故障探针均为 1。
$env:PATH = (Resolve-Path temp/p0-tools).Path + ';' + $env:PATH
Remove-Item Env:CODEBOARDING_TELEMETRY -ErrorAction SilentlyContinue
Remove-Item Env:DO_NOT_TRACK -ErrorAction SilentlyContinue
uv run python docs/design/external-agent-p0/experiment.py --output temp/p2-finish-core --pyright-js temp/p0-tools/node_modules/pyright/langserver.index.js
uv run python docs/design/external-agent-p0/check-guard-negatives.py temp/p2-finish-core temp/p0-tools/node_modules/pyright/langserver.index.js
```

新增负例通过 `sys.audit("socket.connect")` 命中并吞掉 guard 异常，不创建连接；分别注入 write_report、warning、stdout.flush、stderr.flush 及 warning/exception 双重日志失败。每种故障同时验证 guard 已命中和未命中的情况，确认最终报告写入失败本身也退出 1。真实核心与既有 caught/thread/exit 继续走原路径。最新证据单列在 `finish-validation/`，原有浏览器证据属于前一轮，本次未修改 renderer 或浏览器检查器。
