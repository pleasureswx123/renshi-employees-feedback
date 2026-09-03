# P8 计分与基础报告实施契约

## 1. 范围与状态

2026-09-03 已完成 P8 实现与阶段验收。本文第 2 至 4 节是实现契约，第 6 节记录直接验证证据；该结论限于已迁移的独立开发/测试环境，不代表通过 P9 上线验收。

- 复用冻结问卷、关系、任务、已提交答卷、`fb_score_result` 和 RuoYi 双层数据范围。
- 后端纯计算器 → 服务层事务 → PostgreSQL 结果和依据 → HR 网页表格。
- 不开放员工个人报告，不提供导出，不改变完成项目状态机。

## 2. 计分与精度

- 使用 `Decimal`，局部计算上下文精度为 50 位有效数字；中间步骤不按展示位数量化。循环小数受该上下文精度约束。
- `fb_score_result.score/effective_weight` 通过 P8 迁移改为 PostgreSQL 无固定小数位的 `NUMERIC`，完整保存计算器输出；原始题分与配置权重继续使用已有四位小数协议。
- 对外分数、权重、完成率均由后端 `ROUND_HALF_UP` 显示两位小数；排序使用未量化的持久化总分，相同正式分数并列（1、1、3），同分按被评价人 ID 升序，空分置后且不排名。只在当前可见范围内排名，姓名筛选不改变该范围排名。
- 每份答卷按全部绑定计分题最高分之和作为指标分母。已提交答卷漏答可选计分题时，分母不减少、该题不增加分子，同时记录漏答数量；不补写零分答案。题目明细的均分仅对实际有答案者计算，并显示漏答数量。没有已提交答卷的关系仍为空，不能当零分。
- 同关系多人先分别算指标分再平均；按已提交计分关系原权重归一化。自评只作对照，只有发布目标的 `only_self_evaluation` 为真时才按自评 100% 计入总分。非计分关系只展示。
- 正式总分按冻结指标权重合成；缺少有效正式关系时为空并显示“数据不足”。自评分和他评分分别展示，不互相填补。
- 校验输入版本、冻结规则版本、指标/关系权重快照、已提交状态、题分及提交快照一致性；不一致时拒绝生成，不能忽略损坏答卷。

## 3. 生成与不可变依据

- `POST /feedback/projects/{id}/reports/calculate`：权限 `feedback:report:view`，仅已完成项目可用。显式生成当前数据范围内可见目标的全部结果。
- 按项目排他锁串行化生成，锁内校验完成状态与项目/目标范围；同一事务写入关系指标、综合指标、个人总分和覆盖率。
- 已有完整结果返回幂等成功，不更新结果、依据或计算时间。部分结果、未知计算版本返回冲突；失败全部回滚。不提供覆盖重算入口。
- `calculation_basis` 保存计分器版本、发布规则、冻结题目/指标/关系、目标仅自评标记、任务集合、已提交答卷 ID/摘要/题分，以及中间值。个人结果同时保存不含身份和原文的报告投影；查询不把内部依据暴露给报告权限。
- P8 精度迁移保留既有结果；降级若会损失任一结果精度必须拒绝，禁止静默四舍五入。
- 生成前核验结果字段实际精度；旧表返回 `REPORT_SCHEMA_NOT_READY`，禁止依靠 ORM 类型声明把完整精度结果写入仍为四位小数的数据库。

## 4. 查询、权限与页面

| 接口 | 权限 | 内容 |
|---|---|---|
| `GET /feedback/reports/projects` | `feedback:report:view` | 可见已完成项目，支持名称筛选和分页；不依赖项目列表权限 |
| `GET /feedback/projects/{id}/reports` | `feedback:report:view` | 是否已生成、范围说明、完成率、团队排名/指标/自评/他评 |
| `GET /feedback/projects/{id}/reports/{target_user_id}` | `feedback:report:view` | 个人指标、关系原/实际权重、不适用/缺失、题目汇总 |
| `GET /feedback/projects/{id}/answers` | `feedback:answer:view` | 已提交答卷列表，可按被评价人筛选；不返回草稿 |
| `GET /feedback/projects/{id}/answers/{assignment_id}` | `feedback:answer:view` | 已提交原始答案、评价人快照与只读问卷；不依赖报告权限 |

- 每个接口必须同时检查项目归属范围和发布时被评价人部门范围；全部目标不可见、指定目标/答卷不可见统一 404。
- 沿用 RuoYi 权限依赖的 `HTTP 200 + code=403` 拒绝信封；资源范围错误使用 HTTP 404，未完成项目和数据冲突使用 HTTP 409。前端统一请求层按业务码处理拒绝。
- 局部范围只返回可见人员、数量、分数和排名，明确提示不能代表全项目。查询不按评价人当前部门过滤。
- 报告响应不包含评价人 ID/姓名、答卷 ID、选项选择、附加原因、问答原文、答案摘要或内部计算依据。原始答案是单独请求，不预取。
- 报告与答案访问通过 RuoYi 操作日志记录元数据，禁用完整响应/答案内容日志。响应加 `Cache-Control: no-store`。
- 路由 `/hr/reports`、`/hr/projects/:projectId/reports`、`/hr/answers`、`/hr/projects/:projectId/answers`。报告入口支持仅报告权限账号；原始答案入口支持单独答案权限。
- 使用 Element Plus 表格、表单校验、抽屉和只读题型组件，Pinia 保存会话内状态。切换项目、目标、退出或权限错误时清除旧数据并丢弃过期响应。

## 5. 验收清单

- 固定手算 A=83、B/C=86.25、仅自评=92，补充多人、多指标、零值、全部缺失、自评不能兜底、可选漏答、循环小数和临界舍入。
- 真实 PostgreSQL：服务生成、结果/依据/API 对账、同分/空分排序、局部数据范围、快照改名不变、重复/并发生成、故障回滚、异常输入拒绝。
- 权限与 HTTP：普通员工 403，仅报告权限无法读取原始答案，独立答案权限可读已提交且不能读草稿，项目/目标越权 404。
- 前端：API、Store、路由、表格/抽屉和异步上下文隔离测试；生产构建。
- 真实浏览器：已有发布/逐人提交/完成闭环扩展至生成报告、刷新恢复、个人题目汇总与授权原文；数据库三方对账。
- 迁移真实升级/往返/精度损失降级保护；相关回归、Ruff、格式和差异检查。

## 6. 已验证的阶段交付

### 6.1 实现与对账

- 后端入口：`controller/report_controller.py` → `service/report_service.py` / `scoring_input.py` → `dao/report_dao.py` / `calculators/report_score.py`，响应经 `entity/vo/report_vo.py` 白名单序列化。
- 前端入口：HR“评价报告” → 已完成项目 → 生成报告 → 团队表格 → 个人报告抽屉；“原始答案”使用独立权限和独立请求。
- 固定样例验证 83、86.25、92、有效零分、空分、多指标、多人关系、可选漏答、权重归一化和舍入边界；纯计算输入可从持久化依据复算。
- 真实 PostgreSQL 验证并发/重复生成只保留一组结果、第二人写入失败整体回滚、部分既有结果拒绝覆盖、损坏提交依据拒绝生成、未完成项目拒绝生成、旧精度字段拒绝写入，以及同分并列、空分末尾、局部范围和原始答案权限。
- 真实浏览器沿用发布和答题夹具：两人各提交一份他评，HR 关闭两份未交自评；报告完成率 50.00%，两人正式分均为 `45.550847457627118644…`，数据库完整保存、API/页面显示 `45.55`，均排名第 1，自评显示数据不足。
- 已验证刷新恢复、个人指标/关系/题目汇总、授权原始答案只读、仅报告账号读取原始答案被拒绝，以及局部范围只显示 1 人、1/2 份。报告查询与生成没有改动原始任务和答卷。

### 6.2 命令与结果

以下命令在对应工程目录执行，结果采集于 2026-09-03：

| 验证 | 命令 | 结果 |
|---|---|---|
| 后端完整评价模块回归 | `$env:RUN_FEEDBACK_POSTGRES_TESTS='1'` 后运行 `./.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/module_feedback --tb=short` | 194 项通过，包含真实 PostgreSQL 服务/并发/迁移测试 |
| 前端单元与组件 | `node.exe node_modules/vitest/vitest.mjs run` | 28 个文件、146 项通过 |
| 前端生产构建 | `node.exe node_modules/vite/bin/vite.js build` | 通过 |
| 既有浏览器回归 | `node.exe node_modules/@playwright/test/cli.js test --config playwright.config.js` | 16 项通过；这些用例使用 Mock 接口 |
| 完整真实业务闭环 | `node.exe node_modules/@playwright/test/cli.js test --config playwright.live.config.js` | 1 项通过；完整 RuoYi 登录/权限、后端、PostgreSQL 和 Redis，不拦截业务 API |
| 数据库结构 | `./.venv/Scripts/python.exe scripts/feedback_p2_schema_verify.py --database ruoyi_feedback_dev`；测试库同命令替换库名 | 双库 head 为 `20260903_08_feedback_scoring`，15 张表、213 个字段/中文注释、8 个 NUMERIC(12,4)、1 个 NUMERIC(18,4)、2 个不限定小数位的 NUMERIC，16 项关键约束、12 项关键索引 |
| 迁移精度保护 | `tests/module_feedback/migration/test_p8_scoring_migration.py` | 真实 PostgreSQL 临时同名表上升级→降级→升级通过；高精度已有结果使降级拒绝，原值保留，测试事务回滚 |
| 静态检查 | 对评价模块、相关测试/脚本/迁移运行 Ruff 检查和改动文件格式检查；`git diff --check` | 通过 |

页面证据保存在本地 `output/playwright/p8-team-report.png`、`p8-person-report.png`、`p8-team-report-mobile.png`。已核验 1440 像素桌面及 390 像素窄屏，窄屏表格可横向滚动，页面本身不横向溢出；截图和测试凭据不进入版本控制。

非阻塞提示：既有 `async_lru` 测试事件循环提示、第三方 VueUse PURE 注释提示及构建大 chunk 提示仍存在。性能与打包基线由 P9 继续检查。

## 7. P8验收时的本地环境边界（历史记录）

**P9后续更新（2026-09-03）**：下列内容保留P8验收时的事实。P8已本地提交为`b59e62b`；P9已完成当前开发库备份、副本接管/故障回滚演练及原库严格迁移接管，当前`ruoyi-fastapi`已达到P8 head，原有记录摘要保持不变，`.env.dev`未改动。最新状态和回执见[P9验收报告](./16-p9-release-acceptance.md)。

**已验证**：用户当前 `.env.dev` 指向 `ruoyi-fastapi`，该库已有 15 张评价表，但没有 `alembic_version` 表，且 `fb_score_result.score/effective_weight` 仍为 `NUMERIC(12,4)`。本次保留该库和用户配置，没有给它直接 stamp 或试跑迁移。现有本地服务因此不能视为 P8 运行验收环境。

**已交付保护**：生成接口检查实际列精度并返回 HTTP 409 / `REPORT_SCHEMA_NOT_READY`，页面提示联系管理员完成数据库升级，避免静默丢失正式得分精度。

**后续实施事项**：P9 需先审计该既有库与迁移链的结构/数据差异，形成有备份和回退路径的接管迁移方案；或由用户明确切换到已验证的 `ruoyi_feedback_dev`。不能仅凭表名相同直接标记 Alembic head。P8 独立环境阶段门禁已通过，尚未提交、推送或部署。
