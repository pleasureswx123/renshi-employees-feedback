# 首期启动、迁移、权限与运维手册

## 1. 交付状态与工程边界

本文是可复现的开发运维手册和部署约定。2026-09-03 的实际验收记录见 [P9 验收报告](./16-p9-release-acceptance.md)。开发完成、测试通过、已部署、可正式使用是四种不同状态；本轮没有发布到生产环境。

- `ruoyi-fastapi-backend` 是唯一后端，`module_feedback` 复用系统账号、组织、权限、异步 PostgreSQL、Redis 和日志。
- `ruoyi-fastapi-frontend` 负责系统管理及角色授权；`feedback-frontend` 承载 HR 和员工业务。
- 正式分数、冻结、提交和项目完成由后端事务控制。员工通过登录后的“我的待办”参评。
- 生产启用前仍需部署负责人确认域名/TLS、访问范围、备份保留期、恢复时间目标及正式 HR 角色名单，并完成目标环境的真实登录验收。这些事项不影响本地开发验收。

## 2. 本地启动与检查

在仓库根目录打开不同的 PowerShell 终端。使用后端项目自己的虚拟环境，不使用系统同名 Python：

```powershell
Set-Location D:\work\renshi-employees-feedback\ruoyi-fastapi-backend
.venv\Scripts\python.exe scripts/feedback_p2_schema_verify.py --database ruoyi-fastapi
.venv\Scripts\python.exe app.py --env dev
```

```powershell
Set-Location D:\work\renshi-employees-feedback\feedback-frontend
node.exe node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort
```

本地平台地址为 `http://localhost:5174`，`/dev-api` 代理到后端 `127.0.0.1:9099` 并去掉代理前缀。前端有安装好的锁定依赖时可直接使用上述 Node 入口；首次安装应按工程锁文件安装，不能因为命令包装器失败而升级依赖。

登录后请求 `/feedback/health`，正常返回 `status=ready`、`phase=P9` 和 `schemaRevision=20260903_08_feedback_scoring`。该接口受 RuoYi 登录保护；它检查实际迁移版本及正式结果列精度，不替代完整结构核验。缺版本或旧精度返回 HTTP 503 / `FEEDBACK_SCHEMA_NOT_READY`。未登录时要同时检查响应业务码，平台认证错误沿用 RuoYi 的响应契约。

平台启动仅自动创建非 `fb_` 公共表；评价表必须经过 Alembic。启动成功不能替代迁移成功。

结构核验脚本允许只读检查当前配置库；当前配置库禁止使用任何迁移循环选项。降级/升级演练仅用于独立测试库。

## 3. 数据库升级与接管

### 3.1 新库和已有 Alembic 库

数据库固定 PostgreSQL。新库先初始化 `sql/ruoyi-fastapi-pg.sql` 的系统基线，再升级评价迁移；独立开发/测试库可使用既有 P0 工具：

```powershell
.venv\Scripts\python.exe scripts/feedback_p0_database_precheck.py --create --yes
```

该命令针对独立 `ruoyi_feedback_dev`、`ruoyi_feedback_test` 和 Redis 测试逻辑库，不切换当前 `.env.dev`。已有 Alembic 库使用其正确环境配置运行：

```powershell
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
```

连接和目标库来自 `APP_ENV` / `DB_DEFAULT_SOURCE` / `DB_SOURCES`。升级前核对目标库、备份和现有版本；升级后运行 `feedback_p2_schema_verify.py --database <目标库>`。本轮 head 为 `20260903_08_feedback_scoring`，应验证 15 张表、213 个字段/中文注释、16 项关键约束和 12 项关键索引。

### 3.2 早期 create_all 形成的无版本库

只适用于 P9 工具明确识别的混合结构。未知字段、类型、默认值、约束、索引或中文注释差异都会拒绝接管。不得绕过检查直接 `stamp head`。

以下示例是本轮已经执行过的流程形状，备份文件名及恢复库名每次必须新建。工具默认使用本机 PostgreSQL 17 客户端；其他安装目录通过 `--pg-bin` 指定。

```powershell
# 只读比对当前库与已迁移的独立参考库
.venv\Scripts\python.exe scripts/feedback_p9_migration.py audit --database ruoyi-fastapi --reference ruoyi_feedback_dev

# 在维护窗口停止业务写入，用一致快照生成备份及校验元数据
.venv\Scripts\python.exe scripts/feedback_p9_migration.py backup --database ruoyi-fastapi --file ..\.tmp\p9\new-backup.dump --yes

# 恢复只允许原先不存在的 ruoyi_feedback_p9_*_test，不会覆盖任何已有库
.venv\Scripts\python.exe scripts/feedback_p9_migration.py restore --database ruoyi_feedback_p9_new_rehearsal_test --file ..\.tmp\p9\new-backup.dump --yes
```

读取备份同名 `.dump.json` 中的 `schemaSha256`，先对恢复副本运行 `adopt`，再进行完整结构验证；副本通过后才对原库运行同一接管流程。`--expected-schema-sha` 必须使用该次备份的实际值：

```powershell
$backupMetadata = Get-Content ..\.tmp\p9\new-backup.dump.json -Raw | ConvertFrom-Json
.venv\Scripts\python.exe scripts/feedback_p9_migration.py adopt --database ruoyi_feedback_p9_new_rehearsal_test --reference ruoyi_feedback_dev --file ..\.tmp\p9\new-backup.dump --expected-schema-sha $backupMetadata.schemaSha256 --yes
.venv\Scripts\python.exe scripts/feedback_p2_schema_verify.py --database ruoyi_feedback_p9_new_rehearsal_test
```

接管在单个数据库事务中锁定评价表，复用既有迁移，校验每一条原有记录的全部原字段摘要，再登记实际达到的版本。备份后评价数据发生变化会拒绝，必须重新备份并演练。它只允许当前配置库或明确的 P9 隔离库。

**本机当前状态**：`ruoyi-fastapi` 已在副本演练和故障回滚验证后完成接管，保留原有项目、版本及页面，补齐 5 条固定关系。不要对这个已经有版本的库再次执行 `adopt`。

## 4. 备份、恢复与回退

- `backup` 使用 PostgreSQL 导出的同一个可重复读快照完成 `pg_dump`、结构摘要和 15 张评价表的行摘要；备份文件及元数据必须成对保管，不能放进 Git。
- `restore` 先校验备份 SHA-256，再恢复到全新隔离库，核对结构和全部评价行摘要。系统基础表随完整数据库转储恢复；P9 自动摘要对账的范围是评价表。
- 接管中发生结构、行摘要或最终版本核验失败会整体回滚；不得用新的 stamp 掩盖失败。
- 已有正式答案、完成审计和高精度结果时，不用降级脚本作为日常回退方法。P7 审计有记录、P6 权限已授权或结果可能丢失精度时，相关降级会拒绝。
- 应用回退优先回退到兼容当前结构的代码。需要恢复数据库时，在停止写入后恢复到新库，核对数据与权限，再由运维明确切换连接并验证；不直接覆盖运行库。正式恢复还需对备份之后的新增答卷做核对，不能静默丢弃。

本轮升级前备份位于仓库 `ruoyi-fastapi-backend/.tmp/p9/ruoyi-fastapi-20260903-snapshot.dump`，SHA-256 为 `96e44e7794a51d844b1f89299b8bfcd6b039f30d147cfec451838074338b25be`。这是本机开发库备份，不是生产备份策略。保留其同名 `.dump.json`。

## 5. 权限初始化

P6 权限迁移登记 15 个权限码到系统管理端“评价平台权限”目录，不创建角色、不自动给现有账号授权。通过管理端的角色、菜单权限和数据权限配置完成授权，然后退出并重新登录核对 `/getInfo`。

| 使用者 | 需要的权限 | 范围要求 |
|---|---|---|
| 员工 | `feedback:task:view`、`feedback:task:answer`、`feedback:task:submit`、`feedback:history:view` | 本人任务，评价人从登录上下文取得 |
| HR 项目配置 | `feedback:project:list/add/edit/remove` 对应四个独立权限；`feedback:questionnaire:edit`、`feedback:participant:manage` | 项目 owner 及可选择系统用户的数据范围 |
| HR 发布 | `feedback:project:publish` | 必须覆盖全部配置人员 |
| HR 回收与完成 | `feedback:progress:view`、`feedback:project:complete` | 完成操作要求覆盖整个项目的被评价人 |
| HR 报告 | `feedback:report:view` | 可见范围内生成和查看汇总报告；局部排名明确标注范围 |
| HR 原始答案 | 额外授予 `feedback:answer:view` | 同时通过项目和被评价人范围检查，只能读取已提交答卷 |

五种角色数据范围为全部、自定义部门、本部门、部门及子部门、仅本人，多个角色取并集。非管理员没有角色或范围值无效时返回空范围；管理员沿用平台全量范围。员工不通过自报用户 ID 获得身份。完整方法/路径映射见 [接口矩阵](./evidence/p9-api-matrix.md)。

## 6. 部署配置约定（尚未在生产执行）

| 配置 | 部署要求 |
|---|---|
| `APP_ENV` / 环境文件 | 使用独立生产配置；禁止把本地 `.env.dev` 及测试验证码配置作为生产配置 |
| `DB_DEFAULT_SOURCE`、`DB_SOURCES` | 选择唯一 PostgreSQL 主库；设置 `db_echo=false`；密码通过受控环境提供 |
| `REDIS_HOST/PORT/USERNAME/PASSWORD/DATABASE` | 使用部署环境缓存及隔离逻辑库，验证认证、会话和日志队列 |
| `JWT_SECRET_KEY` | 持久、独立、受控的密钥，多个应用进程一致 |
| `TRANSPORT_CRYPTO_*` | 使用既有传输策略和稳定密钥对，前端读取公共配置；多进程必须共享一致密钥 |
| `APP_RELOAD` / `APP_WORKERS` | 生产关闭自动重载，按部署容量设定 worker；本轮性能样本不是并发容量承诺 |
| `APP_ROOT_PATH` / `VITE_APP_BASE_API` | 生产前端默认 `/prod-api`；反向代理去掉这个前缀后转发至后端，后端 root path 与入口一致 |
| TLS / 代理信任 | 在受控入口终止 TLS，正确转发协议/来源地址，限制可信代理地址 |

平台前端执行 `node.exe node_modules/vite/bin/vite.js build` 生成 `feedback-frontend/dist`。静态服务需支持 Vue Router history 回退到 `index.html`，并将 `/prod-api/` 代理到后端；管理端单独构建和托管。后端可用项目虚拟环境执行 `app.py --env prod`，由宿主服务管理器负责进程重启。以上配置需在实际部署环境执行登录、刷新、发布、答题、完成、报告和权限验收后，才能标记“可正式使用”。

## 7. 常见故障与定位

| 现象 | 处理 |
|---|---|
| 503 `FEEDBACK_SCHEMA_NOT_READY` / 409 `REPORT_SCHEMA_NOT_READY` | 核对真实目标库、Alembic head 和完整结构；有版本用正常升级，无版本走审计与副本接管流程 |
| 401 / 登录反复失效 | 检查业务响应码、`/getInfo`、Redis 会话、JWT 密钥及浏览器 Token；不要复制他人 Token 到日志 |
| 403 / 项目或目标 404 | 在管理端核对角色权限和部门范围，详情 404 可能是资源不可见；不要通过移除范围过滤解决 |
| 409 版本冲突 | 重新读取当前版本后由用户决定操作；完成/提交出现未知结果时先核对状态，不自动重发 |
| 500 通用失败提示 | 使用响应 `request-id` / `trace-id` 对照应用日志，结合项目/任务 ID 和操作日志定位；错误响应不包含 SQL 参数或答案 |
| 报告为空或数据不足 | 核对已提交数、关系状态及项目完成状态；未交和已暂存答卷不参与计分 |
| 只有报告权限看不到原始答案 | 这是权限约定，需要单独授权 `feedback:answer:view` 且满足数据范围 |
| 测试中断留下账号 | 停止对应验收服务后运行 `scripts/feedback_p6_e2e_fixture.py cleanup --state .tmp/p6-live-automated.json`；只清理这次夹具并恢复测试验证码配置 |

关键写入和原始答案读取沿用 `sys_oper_log`，完成事实另由同事务 `fb_project_completion_audit` 保存。审计参数采用最小字段白名单；答案原文、原因附言、Token 和 SQL 参数不能进入通用错误响应及操作日志。完成原因作为明确业务审计字段保留。日志队列故障会记录安全错误，不应把已成功提交的业务响应改成失败。
