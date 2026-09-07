# 2026-09-07 部署前检查

## 结论与边界

**检查结论：暂不建议直接按仓库默认配置部署到生产。** 核心评价后端测试通过，但生产交付配置存在明确缺口，浏览器验收也尚未全绿。

检查基线为 `9541a62`。检查开始时仅 `ruoyi-fastapi-backend/.env.dev` 存在用户修改，本轮未修改业务代码、环境配置，未提交、推送或部署。本报告为本次检查新增文档。历史验收不能代替当前版本验收。

本次覆盖评价前端、管理前端、后端非 AI 测试、真实 PostgreSQL 评价链路、独立迁移演练、本地配置库只读结构核验、现有浏览器用例及仓库部署文件。未连接目标服务器，未实际构建 Docker 镜像，未做公网安全扫描、依赖漏洞审计或生产并发压测；移动端工程不属于本平台首期部署链路。

## 已确认的部署阻塞项

| 优先级 | 问题及证据 | 部署影响与处理要求 |
|---|---|---|
| P1 | `ruoyi-fastapi-backend/.env.prod:67` 默认 `db_type=mysql` | 与评价业务 PostgreSQL 约束不符。不能直接照运维手册使用原样 prod 配置启动；需注入明确的 PostgreSQL 数据源并核验实际目标库。 |
| P1 | `docker-compose.pg.yml` 只包含管理前端、后端、PostgreSQL、Redis，没有 `feedback-frontend`；管理端生产及 Docker 环境的 `VITE_FEEDBACK_APP_URL` 为空 | 默认 Compose 不提供员工/HR 评价入口，管理端跳转按钮也不可用。需构建并托管评价端，配置实际入口、API 代理与 history 回退，并在管理端构建前填入评价地址。 |
| P1 | `Dockerfile.pg:14` 直接启动应用；Compose 只导入系统 SQL；`config/lifecycle.py:24` 明确排除 `fb_` 表 | 全新部署不会自动创建评价表。上线流程必须包含系统基线初始化、正确环境下的 Alembic 升级、结构核验和登录后的 `/feedback/health` 就绪核验，不能只检查进程存活。 |
| P1 | `docker-compose.pg.yml:44` 使用示例数据库密码；数据库和 Redis 端口分别映射到宿主 `15432`、`16379`；未配置 PostgreSQL 数据目录的显式命名卷或绑定挂载 | 若直接部署到可达服务器，数据库和未配置认证的 Redis 暴露范围过大。需使用受控凭据并限制访问，配置明确数据卷及备份恢复流程。PostgreSQL 镜像可能创建匿名卷，但 Compose 未提供稳定的显式卷关联，不能据此保证重建后的数据恢复。 |
| P1 | `ruoyi-fastapi-backend/Dockerfile.pg:5` 使用 `COPY . .`，该构建上下文没有 `.dockerignore` | 从当前工作目录构建会带入 `.env.dev`、`.venv`、本地备份和运行产物等；Git 忽略规则不会过滤 Docker 上下文。需限定镜像内容，生产敏感配置在运行时注入。 |
| P1 | `.env.prod:73` 启用 `db_echo=true`；Compose 覆盖的 `DB_SOURCES` 未提供 `db_echo`，`config/env.py:79` 默认值为 `True` | SQLAlchemy 会输出 SQL 及参数，可能把评价答案等写入日志并增加日志容量。生产数据源应显式关闭 SQL echo，保留必要业务审计与异常日志。 |
| P2 | `.env.prod:39`、`.env.dockerpg:39` 的 JWT 密钥为空；`config/env.py` 对空值生成随机密钥 | 重启会导致旧登录令牌失效，多进程也不能保证一致。部署前需配置持久且各进程一致的专用 JWT 密钥；传输密钥也应作为受控生产配置管理。 |

这些是对仓库现有文件的检查结果。服务器若已有独立生产配置、代理、数据卷及迁移流程，需要用实际配置逐项证明已解决，不能直接视为仍有同样缺陷，也不能假定已经解决。

## 已确认的页面与测试问题

### 指标权重提示溢出（P2，实际布局缺陷）

在问卷编辑器配置指标权重 `100% + 20.0001%` 时，右侧提示内容超出提示框右边界约 `5.28px`。完整模拟接口浏览器测试和单独复测均得到 `1250.28125 > 1245`，可以稳定复现。

相关位置：`feedback-frontend/src/components/feedback/IndicatorPanel.vue:196` 使用 `flex-wrap: nowrap` 和 `white-space: nowrap`；断言位于 `tests/e2e/questionnaire-editor.spec.js:215`。建议适配长精度提示及窄面板宽度，保留准确数值与错误信息，再跑该用例。该用例在此提前结束，本次不能声称其后续保存重载与预览步骤已通过。

### 浏览器用例与当前页面不一致（P2，验收缺口）

- `tests/e2e/workspace-display.spec.js:57` 在项目列表查找 `.workspace-page-header`，当前列表已没有此元素。用例因此未继续验证后续主题恢复、弹窗和下拉菜单；这个失败本身不证明主题功能损坏。
- `tests/live-e2e/employee-answering.spec.js:186` 等待名含 `P5闭环` 的标题，而进度页当前标题固定为“评价进度”，项目名另行展示。该用例已完成真实发布、员工暂存恢复、提交及部分数据库对账，但没有继续完成后半段 HR 完成与权限验证。
- 第二条真实用例已执行创建、发布、提交、完成和报告断言，最后 `:512` 的审计断言失败：期望包含“已提交评价原始答案”。该用例自身未读取原始答案明细，而相应读取位于第一条用例后段，第一条此前已失败。现有断言存在跨用例证据依赖；不能据此直接断定生产审计丢失，也不能标记完整审计验收通过。应让每条用例独立生成所需审计行为并复验。

### 全仓库后端四项失败

最终完整非 AI 测试仍有以下失败，与仓库既有 P9 报告记录的类别一致；本次没有重新检出历史提交做基线复现：

1. Bash 补全脚本输出：Windows 字符编码问题。
2. PowerShell 补全协议：`COMP_CWORD` 处理失败。
3. 补全安装 JSON 输出：受补全输出错误影响。
4. 代码生成器时间字段：PostgreSQL 配置下 MySQL `datetime` 用例期望不符。

这些失败不位于评价 HTTP 核心业务路径，但全仓库不能标为全部通过。可选 AI 样例测试明确排除，未验证其功能与部署依赖。

## 本次验证结果

| 验证 | 实际结果 | 证据文件（仓库本地，不随 Git 分发） |
|---|---|---|
| 评价前端 Vitest | 43 文件，275 项通过 | `output/release-review-frontend.log` |
| 评价前端生产构建 | 通过；存在大包提示 | `output/release-review-feedback-build.log` |
| 管理前端生产构建 | 通过 | `output/release-review-admin-build.log` |
| 管理首页回归 | 5 项通过 | `output/release-review-admin-tests.log` |
| 管理端插件视图回归 | 1 个测试脚本通过 | `output/release-review-admin-plugin-tests.log` |
| 后端依赖一致性 | `pip check` 通过 | 本次命令回执 |
| 后端全仓库非 AI 测试 | 1475 通过、4 失败、45 跳过；本轮未启用真实数据库标记，另行专测 | `output/release-review-backend-recheck.log` |
| 评价模块真实 PostgreSQL 回归 | 291 项通过；首次迁移演练临时目录权限错误，随后单独复测通过 | `output/release-review-feedback-postgres.log` |
| 独立迁移、备份恢复和接管回滚 | 1 项通过；与上行合计 292 项评价模块测试通过，非一次全绿运行 | `output/release-review-migration.log` |
| 当前配置库只读结构核验 | 通过：15 张表、213 字段/中文注释、16 关键约束、12 关键索引，版本 `20260903_08_feedback_scoring` | `output/release-review-schema.log` |
| 模拟接口浏览器回归 | 26 通过、2 失败 | `output/release-review-browser-mock-recheck.log` |
| 编辑器失败单独复验 | 权重提示溢出稳定复现 | `output/release-review-editor-recheck.log` |
| 真实业务浏览器回归 | 2 项未通过，具体停点见上文 | `output/release-review-browser-live.log` |

首轮后端全量测试受系统临时目录权限影响，出现 415 项夹具错误，已改用仓库内独立 `--basetemp` 完整重跑；不将这些错误归为业务缺陷。首次浏览器运行受沙箱 `spawn EPERM` 阻止，放宽执行限制后才得到上述页面验收结果。

真实数据库测试针对隔离库，迁移演练只创建和清理自身生成的独立库；本地业务配置库只做结构读取。真实浏览器夹具已执行清理，临时状态文件 `ruoyi-fastapi-backend/.tmp/p6-live-automated.json` 已不存在。失败截图和跟踪文件保留在本地 `output/` 和前端 `test-results/`。

## 推荐的上线前收口顺序

1. 确定服务器采用容器还是宿主进程部署，准备可审查的生产配置，解决上表入口、数据库、迁移、存储、凭据和日志问题。
2. 修复权重提示布局，并更新不匹配当前页面的测试；消除真实用例间的审计依赖，重新通过两条真实流程。
3. 在目标服务器测试环境完成部署，验证 TLS/代理、双端登录与授权、刷新直达、HR 发布、员工暂存提交、HR 完成、报告及原始答案权限；确认备份与恢复。
4. 目标环境上述门禁通过后，才对正式用户开放。当前本地数据库结构通过、构建通过和核心测试通过，均不能单独替代这个步骤。

## 同日按用户要求修复后的复验

上文保留首次检查现场。本轮已修改PostgreSQL生产配置、双前端与独立迁移Docker服务、命名卷、文件密钥、SQL日志开关、JWT校验和Docker构建排除规则。部署方法见[生产Docker部署](./22-production-docker-deployment.md)。

- 指标权重提示允许完整换行，28项模拟接口浏览器测试通过（`output/deploy-browser-mock.log`）。
- 真实用例修正页面标题，并独立读取原始答案以产生审计记录；窄屏检查等待侧栏过渡动画结束。2项完整业务用例通过（`output/deploy-browser-live-2.log`），夹具完成清理。
- Windows补全生成与协议已修复；生成器时间类型测试按方言隔离。后端全仓库非AI测试1489项通过、45项跳过（`output/deploy-backend-all.log`）。此轮未启用数据库标记；没有把跳过项描述为通过。
- 评价前端43文件、275项测试通过（`output/deploy-frontend-unit.log`）。
- 部署入口单元及独立PostgreSQL回归合计10项通过（`output/deploy-entrypoint-pg-2.log`），覆盖全新系统基线升级、重复执行、结构核验和无版本旧库拒绝；首次回归因测试读取不存在的版本表而失败，已改为核验该表未被创建后复测通过，未修改业务迁移来迁就断言。
- 本次修复未修改用户`.env.dev`、未提交、推送或部署目标服务器。

### Docker验证的实际边界

- Compose参数与依赖关系校验通过。评价前端镜像 `tongjian-feedback:review` 构建成功，在一次性容器中执行 `nginx -t` 通过。
- 独立项目 `tongjian-review` 的PostgreSQL17与Redis7.4容器健康；新库系统基线有2个初始化账号、0张评价表，符合尚未执行评价迁移的阶段；Redis文件密码与健康检查工作正常，两个服务没有宿主端口映射。
- 初次密钥由受限沙箱账号创建，Docker宿主无法读取；重新使用当前用户权限在新的隔离测试目录生成密钥后启动成功，未向其他用户开放密钥读取权限。
- 后端基础镜像补齐gcc、libc6-dev及libpq-dev；依赖层兼容Windows CRLF并单独缓存。Docker构建在Debian包索引下载阶段多次超时重试，管理端npm依赖下载未完成，停止未完成的构建。未取得后端/管理端镜像完整构建和整套Docker启动通过的证据。
- Docker记录保存在 `output/deploy-build*.log`、`deploy-pull.log`、`deploy-infrastructure-2.log`；本次新建的测试容器、网络及命名卷已清理，记录见 `output/deploy-cleanup.log`。保留已下载镜像与忽略目录中的测试材料，未清理任何原有业务容器或卷。
- 原生环境的真实迁移入口及两条完整业务浏览器测试通过，不能替代尚未完成的Linux镜像和服务器验收。实际部署应先完整执行[生产部署手册](./22-production-docker-deployment.md)的构建、迁移、启动和业务验收。
