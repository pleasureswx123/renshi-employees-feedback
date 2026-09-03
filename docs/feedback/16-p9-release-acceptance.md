# P9 安全、性能、迁移与首期验收

## 1. 验收结论与边界

2026-09-03，P9 实现及本地首期业务验收完成。P8 已本地提交为 `b59e62b`，P9 已本地提交为 `c817b32`；未推送或部署。根 `README.md` 与后端 `.env.dev` 的用户已有改动保留。本文保留 P9 提交时的验收快照，后续用户指定的内置浏览器完整复核、修复及最终测试结果见[P0–P9浏览器验收](./18-p0-p9-browser-acceptance.md)。

**已验证**：评价模块 256 项后端测试、前端 146 项测试、16 项 Mock 浏览器交互回归和 2 项真实登录/后端/PostgreSQL 浏览器流程通过。当前开发库已经严格接管 Alembic，原有评价数据保留。1000 名被评价人的团队报告读取中位数从 2346.125ms 降到 150.980ms，结果与完成率对账不变。

**已分类但未解决的既有问题**：全仓库非 AI 测试集经过完整运行及失败复验，合并结果为 1483 项通过、4 项失败、1 项环境跳过；4 项失败均在 P8 提交的隔离副本复现。可选 AI 样例测试因缺少 `agno` 无法收集。具体用例、原因与影响见第 7 节；本报告不声明全仓库测试全绿。

**设计约定**：保持原计分、冻结、提交不可变性和首期范围；评价业务仍是核心模块，正式数据库仍是 PostgreSQL。公共模块内存单元测试的 `aiosqlite` 仅作为测试依赖补齐。

**待确认/未执行**：生产域名、部署环境、角色名单、备份保留策略和目标环境上线验收。本地验收不代表已部署或可正式使用。可复现流程见 [运维手册](./17-operations-runbook.md)。

## 2. 任务与退出证据

| 任务 | 交付与直接证据 | 状态 |
|---|---|---|
| P9-01 权限与范围 | 28 个真实路由矩阵；28 个未登录拒绝、20 个员工访问 HR 拒绝；真实 PostgreSQL 五类范围及并集/空角色/管理员 | 已完成 |
| P9-02 越权与篡改 | 用户/任务/项目/目标/版本/页面/题目/选项归属；拒绝后原答案和任务状态不变；真实登录负向请求 | 已完成 |
| P9-03 状态与并发 | P5 双发布、P6 双提交和暂存竞争、P7 双向锁竞争及双完成、P8 双计分和故障回滚 | 已完成 |
| P9-04 迁移 | 空库与基线完整升级、备份恢复、既有数据接管、故障注入回滚、实际开发库 213 字段核验 | 已完成 |
| P9-05 性能 | 200/1000 人真实服务数据集、待办/进度/报告执行计划与耗时；按实际瓶颈修复结果集合反复遍历 | 已完成 |
| P9-06 审计 | 最小参数白名单、安全异常边界、请求追踪；真实 `sys_oper_log` 持久化及原文脱敏检查 | 已完成 |
| P9-07 自动化 | 相关门禁通过；全仓库失败按环境/既有问题分类、补依赖复验、P8 基线复现 | 已完成，保留 4 项既有失败及环境缺口 |
| P9-08 业务场景 A 至 F | 真实浏览器、完整 RuoYi 应用、PostgreSQL 对账，见第 6 节 | 已完成 |
| P9-09 运维交付 | 启动/部署配置、权限、迁移、备份恢复、故障排查和状态边界 | 已完成；部署本身未执行 |

## 3. 安全审计与修复

### 3.1 权限入口

[实际接口矩阵](./evidence/p9-api-matrix.md) 由 `scripts/feedback_p9_api_audit.py` 读取四个控制器实际注册结果生成。全量 28 个方法/路径均有 RuoYi `PreAuth`，27 个业务接口均有明确权限码，健康检查要求已登录。不存在报告导出、公开参评或员工个人报告接口。

`tests/module_feedback/controller/test_p9_security.py` 保留真实认证/权限依赖的判定行为，替换数据库连接以单独测量拒绝边界；真实登录令牌、后端与数据库归属则由真实浏览器及 PostgreSQL 服务测试补充，不将依赖替换测试称为完整登录验收。

### 3.2 数据范围

公共 `common/aspect/data_scope.py` 原实现对无角色用户构造空 `or_()`，可能成为不受限条件。本轮改为显式 `false()`；管理员提前使用平台全量范围。其他五种范围和多角色并集沿用原实现。

`test_p9_data_scope_postgresql.py` 在一个回滚事务中建立父/子/外部部门、用户和自定义部门角色，通过实际 SQL 验证：全部、自定义部门、本部门、本部门及子部门、本人、角色并集、空角色、未知范围、无部门、无角色管理员。HR 详情由项目 owner 范围限制；报告、进度和原始答案再叠加被评价人范围。员工身份仅来自当前用户，不能通过请求字段替换。

### 3.3 资源归属和输入篡改

以下均包含已执行的直接测试，不以页面隐藏替代后端检查：

| 边界 | 证据 |
|---|---|
| 所有 HR 接口拒绝普通员工 | `controller/test_p9_security.py` 的 20 个方法/路径请求；真实浏览器访问配置 API 返回业务 403 |
| 他人的任务/已提交答案不可读 | `service/test_p6_postgresql.py::test_cross_user_and_version_page_question_option_references_are_rejected`；真实登录读取他人自评任务返回 404 |
| 注入评价人/被评价人/快照或分数 | `entity/test_p6_answers.py`、`entity/test_p5_publication_vo.py`；真实请求添加 `evaluatorUserId` 返回 422 |
| 版本、页码、题目、选项所属不匹配 | `service/test_p6_postgresql.py` 归属用例；`entity/test_p6_answers.py` 非法引用/题型/精度/选项/必答/附加原因用例 |
| HR 越范围项目、目标或答卷 | `service/test_p7_completion_postgresql.py`、`service/test_p8_postgresql.py::test_scope_isolation_and_raw_submitted_answers`；真实局部范围 HR 验收 |
| 报告权限不能读取原始答案 | `controller/test_p8_http_contract.py` 及真实浏览器 report-only 账号；已关闭未完成答卷不会被原始答案接口返回 |
| 失败不会改写既有草稿/正式答案 | `test_failed_transaction_preserves_existing_draft_and_no_formal_score`、P7 回滚用例、P8 部分写入回滚和部分已有结果拒绝覆盖 |

### 3.4 日志、异常与追踪

- 所有 `/feedback/` Pydantic 请求错误只返回 `type/loc/msg`，移除原始 `input`、`ctx`；非法答案和身份注入不能借 422 响应回显原文。
- 评价控制器未预期异常统一为安全 HTTP 500。公共 `Log` 装饰器及全局异常边界记录异常类型，不记录异常字符串、SQL 参数或完整 traceback；其他模块保留已有响应契约。
- 项目创建、问卷保存、配置保存、发布、修改和删除使用最小操作日志字段白名单。提交/暂存不记录答案参数与响应；报告与原始答案读取不记录内容。完成原因仍是明确的业务审计字段。
- P7 完成失败保留事件名、失败阶段、项目、操作人、请求 ID 和 trace ID；日志队列失败不覆盖已完成的业务响应。
- 真实浏览器最终核对 `sys_oper_log` 存在成功发布、提交、完成、报告生成和原始答案读取记录；检查本次密码、题目答案值、建议原文及 Token 字段未写入参数/响应/错误日志。
- `test_p9_security.py` 验证错误响应包含追踪头且无敏感输入；P7/P8 HTTP 日志测试检查允许字段、权限拒绝和队列故障。业务完成事实由同事务 `fb_project_completion_audit` 保存。

## 4. 真实 PostgreSQL 并发与迁移

### 4.1 并发门禁

所有下列用例均显式启用 `RUN_FEEDBACK_POSTGRES_TESTS=1`，使用隔离库与不同数据库会话，包含实际锁等待及最终数据库对账：

- P5 `test_p5_two_sessions_publish_once_without_duplicate_tasks`：双发布只生成一组唯一任务；发布中途失败回滚。
- P6 `test_duplicate_parallel_submit_is_idempotent_and_changed_payload_conflicts`、`test_draft_and_submit_race_never_overwrites_or_half_submits`：双提交幂等，变更负载冲突，暂存不覆盖已交内容。
- P7 `test_p7_slice_7_*`：提交先获得锁、完成先获得锁及双完成；旧预检被拒绝，关闭数量与完成审计一致。
- P7 `test_p7_slice_8_real_lock_summary_flush_and_commit_failures_roll_back_everything`：锁/汇总/flush/commit 故障都回滚。
- P8 `test_concurrent_generation_is_idempotent`、`test_partial_write_failure_rolls_back_all_targets`：双生成只保存一组结果，第二人写入失败不产生半份报告。发布配置和原始答案不可变性保持不变。

### 4.2 启动与迁移边界

平台及插件启动的公共 `Base.metadata.create_all` 均排除 `fb_` 表。运行时不会替代 Alembic 创建评价结构。健康检查经 `controller → service → dao` 读取实际迁移版本和结果精度，缺版本或旧精度返回 503。

`feedback_p2_schema_verify.py` 的只读命令现可验证当前配置库；对当前配置库的迁移循环一律拒绝，其余降级演练继续限制在独立测试库。已实际运行当前库的命令行核验，并通过两项结构工具回归。

`scripts/feedback_p9_migration.py` 提供只读审计、一致快照备份、全新隔离库恢复及严格接管。只归一 PostgreSQL 明确等价的默认值、主键名称及转储后常量数组类型表达式；未知结构差异、部分 P4 字段、缺索引、约束变化均拒绝。

`tests/module_feedback/migration/test_p9_migration_rehearsal.py` 每次新建唯一命名的三个独立库，执行：

1. 从空库初始化 RuoYi 基线并升级完整 Alembic 链，再做空表条件下的基线往返。
2. 备份并恢复为独立副本；只在这个空副本构造已知的旧混合结构，加入既有项目/版本/页面。
3. 一致快照备份、恢复与行摘要对账；已有文件和已有恢复库被拒绝覆盖。
4. 在接管最终行摘要检查注入失败，确认全部结构、版本标记和原有记录回滚。
5. 正常接管到 P8 head，核对原有行摘要、213 个字段及约束/索引；仅清理本用例创建的数据库。

P6/P7/P8 既有迁移测试另验证高总分、高精度结果、已授权权限及非空完成审计的降级保护。

### 4.3 当前开发库接管结果

接管前 `ruoyi-fastapi` 有 15 张评价表但没有 Alembic 标记，缺少两个 P4 字段和页面唯一约束，三个数值列仍使用早期精度。库内存在 1 个项目、1 个版本、1 个页面，没有已提交答卷或正式结果。

本轮先在恢复副本执行失败回滚和成功接管演练，再在当前库单事务接管。最终已验证：

- revision=`20260903_08_feedback_scoring`；15 张表、213 个字段/中文注释。
- 8 个 `NUMERIC(12,4)`、1 个 `NUMERIC(18,4)`、2 个不限制小数位的正式结果 `NUMERIC`。
- 16 项关键约束、12 项关键索引；原有项目/版本/页面的全部原字段摘要保持一致。
- 新增 5 条固定关系属于既有发布迁移的确定性回填；不创建角色或给账号自动授权。
- 未修改 `.env.dev`。原备份保存在后端 `.tmp/p9/ruoyi-fastapi-20260903-snapshot.dump` 及同名 JSON；摘要与步骤见运维手册。

本机 PostgreSQL 为 17.11，使用 PostgreSQL 17 的 `pg_dump/pg_restore`；本轮不依赖 Docker。

## 5. 查询性能与正确性

`scripts/feedback_p9_performance.py` 只允许 P9 隔离测试库，通过实际配置、发布、提交、完成和计分服务创建数据，测量后清理本次项目及人员。每个被评价人包含 3 项同级任务及 1 项自评，1 项同级提交，其余关闭，完成率 25%。列表每页 20 人，断言返回得分 `45.55`，计分依据的精确复算另由 P8 PostgreSQL 测试核对。

| 场景 | 200 人/800 任务，修复前中位数 | 1000 人/4000 任务，修复前中位数 | 1000 人/4000 任务，修复后中位数 | 每次查询数 |
|---|---:|---:|---:|---:|
| 员工待办 | 2.314ms | 3.329ms | 15.146ms | 2 |
| HR 回收进度 | 8.766ms | 36.673ms | 73.086ms | 8 |
| 团队报告 | 104.890ms | 2346.125ms | 150.980ms | 15 |

每次先预热一次，再测量三次；复测期间存在前端测试/构建负载，因此待办与进度波动也如实保留。报告修复后三次为 150.241/197.506/150.980ms；首次生成 1000 人报告约 2.25s。这是本机服务层样本，不是 HTTP 吞吐或生产延迟承诺。

实际 `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` 显示，报告修复前最慢的单条 SQL 约 17ms；2.3s 主要耗在每个目标都重新遍历全部结果行。`report_service.py` 改为一次按目标分组后逐人校验，保留重复行、缺项、计算版本和数量检查。查询次数不变、正式答案和计分公式不变，P8 完整性、精确复算及并发测试继续通过。本轮没有增加无依据的冗余索引。

脱敏后的耗时、节点、实际行数、索引和排序摘要在 [性能证据 JSON](./evidence/p9-performance.json)。完整原始计划留在本机 `.tmp/p9/performance-1000-before.json` / `performance-1000-after.json`；200 人样本在后端 `.tmp/p9/performance.json`。

可重复命令（先准备独立 P9 库并迁移到 head）：

```powershell
.venv\Scripts\python.exe scripts/feedback_p9_performance.py --database ruoyi_feedback_p9_fresh_20260903_test --targets 1000 --output ..\.tmp\p9\performance-1000.json
```

## 6. 首期业务场景 A 至 F

真实流程文件为 `feedback-frontend/tests/live-e2e/employee-answering.spec.js`，使用完整 RuoYi 应用、真实登录令牌、PostgreSQL 和 Redis 3，不拦截业务 API。两条用例最终均通过。

| 场景 | 直接验收证据 |
|---|---|
| A 完整闭环 | 第二条浏览器用例从 HR 创建项目开始，真实鉴权 HTTP 保存问卷/指标/人员关系，再由 UI 发布 5 项任务、员工逐人提交 2 人、HR 完成并生成报告。配置编辑交互本身沿用 P4/P5 组件及 Mock 浏览器门禁，未宣称第二条用例逐控件完成全部配置 |
| B 暂存恢复 | 第一条用例通过五题型 UI 填写、暂存、刷新恢复、必答失败定位、补齐后提交；数据库答卷/答案逐条对账 |
| C 未完成时结束 | 第一条用例含已交/草稿/未开始任务，HR 实时预检并关闭未交；提交答案保持不变，员工不可再写，报告完成率 50% |
| D 权限隔离 | 第一条含仅报告 HR、局部范围 HR 和普通员工；第二条真实 HTTP 验证 HR 配置拒绝、跨用户任务 404、注入评价人字段 422；五种角色范围另用真实 PostgreSQL 验证 |
| E 不可变与并发 | 发布冻结、提交只读由真实浏览器核验；并发请求、锁竞争、重复幂等与最终唯一性由第 4 节真实 PostgreSQL 双会话用例补足 |
| F 关系缺失/权限/形式 | 第二条同一项目两人分别没有下级任务、已配置下级但未提交；两人应交为 2/3、总计 2/5=40%，报告分别“不适用/缺失关系”。同级原权重 50%、实际权重 100%，分数均 80；第一条验证报告和原始答案权限分离。页面无导出按钮，28 个路由无导出接口 |

新增页面截图 `output/playwright/p9-not-applicable-report.png`、`p9-missing-relation-report.png` 已查看，关系、完成率、原/实际权重展示一致。第一条继续覆盖手机与长文本。截图仅使用验收账号和合成内容，不进入版本库。

真实用例结束已清理测试账号、角色、两条用例的项目及临时凭据，恢复测试 Redis 验证码配置。运行产物放在 `.tmp` / `output/playwright`，已纳入忽略规则。

## 7. 自动化命令、完整结果与遗留问题

### 7.1 相关门禁

| 验证 | 命令或入口 | 本轮结果 |
|---|---|---|
| 后端评价模块 | `RUN_FEEDBACK_POSTGRES_TESTS=1`、`RUN_FEEDBACK_MIGRATION_TESTS=1` 后运行项目 `.venv` 的 `pytest tests/module_feedback -q -p no:cacheprovider` | 完整仓库运行中 256 项全部通过，包含真实数据库和创建新库的迁移演练 |
| 最终 DAO/就绪/生命周期复验 | `pytest tests/module_feedback/service/test_p9_data_scope_postgresql.py tests/module_feedback/controller/test_feedback_controller.py tests/config/test_lifecycle.py -q -p no:cacheprovider` | 11 项通过 |
| 全仓库非 AI 测试 | `pytest tests --ignore=tests/plugins/sample_plugins/test_ai_plugin.py -q -p no:cacheprovider`，同时启用上述两个真实数据库标记 | 首轮 1425 通过、62 失败、1 跳过；补依赖后 58 项通过，4 项仍失败且在 P8 基线复现；合并为 1483 通过、4 失败、1 跳过，不能写成一次全绿运行 |
| 独立迁移演练 | `RUN_FEEDBACK_MIGRATION_TESTS=1` 的 `test_p9_migration_rehearsal.py` | 独立执行及完整仓库执行均通过 |
| 前端 | `node.exe node_modules/vitest/vitest.mjs run` | 28 文件、146 项通过 |
| 构建 | `node.exe node_modules/vite/bin/vite.js build` | 通过 |
| Mock 浏览器 | `node.exe node_modules/@playwright/test/cli.js test --config playwright.config.js` | 16 项通过 |
| 真实浏览器 | `node.exe node_modules/@playwright/test/cli.js test --config playwright.live.config.js` | 最终 2 项通过，49.0s；修复了新增验收夹具的权限、选择器和日志 JSON 解析问题 |
| 格式与静态检查 | 对本轮 Python 改动运行 Ruff check / format check；`git diff --check` | 通过 |

真实浏览器和使用相同测试 PostgreSQL/Redis 3 的后端验收串行执行。完整回执位于本机 `.tmp/p9/backend.xml`、`recheck.xml`、`baseline.xml` 和 `final-targeted.xml`。

### 7.2 分类记录

| 分类 | 证据和影响 | 处理结果 |
|---|---|---|
| 测试依赖缺失 | 58 项公共部门/菜单/通知/插件/时间字段测试均缺 `aiosqlite` | 项目 `.venv` 安装 0.21.0，并加入 `requirements-test.txt`；58 项原失败全部通过。业务数据库仍是 PostgreSQL |
| Windows CLI Bash 补全 | `test_completion_show_bash_outputs_completion_script`、`test_completion_install_json_output_has_stable_contract`：UTF-8 解码本机命令输出失败；后者因此无 JSON | 两项在 `b59e62b` 隔离副本、同一 Python 和开发配置下复现。本轮业务通过 `app.py` 启动，不依赖补全安装；保留缺陷记录 |
| CLI PowerShell 补全协议 | `test_powershell_completion_protocol_returns_candidates_without_not_supported_error`：把 `COMP_CWORD=comp` 当整数处理 | 在同一 P8 隔离副本复现；不影响 HTTP 业务接口，需单独修复 CLI 补全注册/协议 |
| 代码生成器方言用例 | `test_python_templates_handle_audit_timestamps_by_exact_column_name`：当前 PostgreSQL 配置下，输入的 MySQL `datetime` 被生成成 `String`，断言要求 `DateTime` | P8 隔离副本相同失败；评价领域实现没有使用生成器产生正式逻辑。以后使用生成器时必须先确认方言并预览，不将本用例标为通过 |
| 可选 AI 测试无法收集 | `tests/plugins/sample_plugins/test_ai_plugin.py` 导入缺少 `agno` | 从本轮全仓库执行中明确排除此文件并记录，未安装或执行额外 AI/provider；评价核心不依赖该插件，若启用需单独补依赖验收 |
| Windows 符号链接权限 | `test_resolve_file_within_root_rejects_symlink_escape` | 测试自行报告当前环境不能创建符号链接，1 项 skip；不能当作通过 |

4 项既有失败的复现使用 `git archive b59e62b ruoyi-fastapi-backend` 的隔离副本和相同配置，不切换当前工作树。未修改对应 CLI、生成器或测试来掩盖失败。

非阻塞提示保留：`async_lru` 事件循环提示、`sqlglotrs` 弃用提示、VueUse PURE 注释移除提示及构建包超过 500kB 的提示。构建成功；本轮性能验证范围是业务查询，不包含公网首屏或高并发容量压测。
