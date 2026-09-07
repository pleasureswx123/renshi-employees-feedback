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

2026-09-07新增可执行的PostgreSQL Docker交付，包含两个前端、独立迁移任务、文件密钥和命名数据卷，完整步骤见[生产Docker部署](./22-production-docker-deployment.md)。`.env.prod`已改为PostgreSQL模板并关闭SQL echo；生产JWT和RSA密钥必须独立配置，不能直接使用空模板启动。历史开发环境验收记录保持原样。

| 配置 | 部署要求 |
|---|---|
| `APP_ENV` / 环境文件 | 使用独立生产配置；禁止把本地 `.env.dev` 及测试验证码配置作为生产配置 |
| `DB_DEFAULT_SOURCE`、`DB_SOURCES` | 选择唯一 PostgreSQL 主库；设置 `db_echo=false`；密码通过受控环境提供 |
| `REDIS_HOST/PORT/USERNAME/PASSWORD/DATABASE` | 使用部署环境缓存及隔离逻辑库，验证认证、会话和日志队列 |
| `JWT_SECRET_KEY` | 持久、独立、受控的密钥，多个应用进程一致 |
| `TRANSPORT_CRYPTO_*` | 使用既有传输策略和稳定密钥对，前端读取公共配置；多进程必须共享一致密钥 |
| `APP_RELOAD` / `APP_WORKERS` | 生产关闭自动重载，按部署容量设定 worker；本轮性能样本不是并发容量承诺 |
| `APP_ROOT_PATH` / `VITE_APP_BASE_API` | 生产前端默认 `/prod-api`；反向代理去掉这个前缀后转发至后端，后端 root path 与入口一致 |
| 管理端 `VITE_FEEDBACK_APP_URL` | 首页跳转到独立评价平台的完整 HTTP(S) 地址，可含部署子路径；不填账号、密码、查询参数或片段。开发默认为 `http://localhost:5174/`，生产/预发布/Docker 配置需填写实际地址后构建 |
| TLS / 代理信任 | 在受控入口终止 TLS，正确转发协议/来源地址，限制可信代理地址 |

平台前端执行 `node.exe node_modules/vite/bin/vite.js build` 生成 `feedback-frontend/dist`。静态服务需支持 Vue Router history 回退到 `index.html`，并将 `/prod-api/` 代理到后端；管理端单独构建和托管。后端可用项目虚拟环境执行 `app.py --env prod`，由宿主服务管理器负责进程重启。以上配置需在实际部署环境执行登录、刷新、发布、答题、完成、报告和权限验收后，才能标记“可正式使用”。

### 6.1 管理端首页

- 首页复用当前登录用户和系统用户、部门、角色列表接口，统计遵守现有接口权限与数据范围；账号总数包含管理员和测试账号，部门总数包含公司及下级团队。
- 用户和角色列表只请求 `pageNum=1&pageSize=1` 并读取 `total`；无权限时不请求对应接口，失败或响应不完整时显示失败状态，不显示为 0。
- 管理入口按权限和已注册路由显示。页面重进、手动刷新时重新加载；账号或权限变化、离开页面后，旧请求不得回填。
- “进入评价平台”在新标签打开独立平台，不拼接登录令牌。平台按自己的登录状态和权限选择工作台；未配置有效地址时按钮禁用，页面提示联系管理员。
- 直接回归命令：在管理端运行 `node --test tests/dashboard/managementOverview.test.js`；构建命令为 `node node_modules/vite/bin/vite.js build`。

2026-09-03 已验证：5 项回归及生产构建通过；内置浏览器显示当前账号可见的 52 个账号、16 个部门，角色统计显示“无查看权限”；管理入口、重进/刷新、新标签进入真实 HR 工作台通过，未改动业务数据。本地截图位于 `output/playwright/admin-home.png`，不随 Git 分发。

### 6.2 两端登录页

- 两端统一使用员工反馈与 360° 评价平台标识，管理端说明组织、账号与权限职责，评价端说明 HR 发起评价和员工完成待办。账号和密码由公司管理员维护。
- 登录仍使用原有认证、验证码与传输加密接口；管理端保留记住密码及后端注册开关，评价端通过既有权限 Store 选择工作台。
- 点击和输入框回车使用同一处理器，Element Plus 校验前即锁定提交；校验不通过不发送登录、不刷新验证码。验证码未加载、请求失败或内容不完整时禁止登录，并提供重新加载入口。
- 登录失败显示错误并刷新已启用的验证码；组件离开后不再回填验证码或触发旧登录跳转。深色模式沿用管理端现有主题，窄屏使用单列布局。
- 直接回归命令：评价端运行 `node node_modules/vitest/vitest.mjs run tests/components/LoginView.test.js tests/api/auth.test.js`；两端分别运行 `node node_modules/vite/bin/vite.js build`。

2026-09-03 已验证：评价端 8 项登录组件测试和 2 项认证 API 契约测试通过，两端生产构建通过；内置浏览器检查两端登录页、必填提示和真实验证码刷新，管理端深色配色正常。工作台跳转与失败重试由模拟认证的组件测试覆盖，本次未使用真实账号重新登录。截图为本机 `output/playwright/admin-login.png`、`output/playwright/feedback-login.png`，不随 Git 分发。

### 6.3 评价工作台布局

- 评价平台参考管理端的深色侧栏、顶部面包屑和白色内容卡片，统一 HR 项目、问卷、人员配置、进度、报告以及员工待办、历史与答题页。
- 桌面侧栏可收起，折叠状态由本次访问的 Pinia Store 保存；760px 及以下改用 Element Plus 抽屉。桌面与移动导航复用同一权限菜单，子页面保持所属菜单高亮。
- HR 和员工工作台仍按现有权限切换，原始答案继续独立授权；管理端的用户、部门和角色页面不迁入评价平台。
- 表格和筛选区使用现有 Element Plus 组件，分页切换为中文。项目列表在窄屏取消操作列固定，横向滚动时不会由操作列遮住项目名称。时间显示保留原有时区语义，省略小数秒。
- 问卷设计器保留大纲、画布与属性面板；随宽度改为两栏或单栏。员工待办与历史采用卡片展示，答题仍保留原有校验、逐人暂存/提交和离开确认。

2026-09-03 已验证：评价端 31 个测试文件、165 项回归及生产构建通过。内置浏览器检查真实项目列表、问卷编辑器、人员关系配置、报告入口、工作台切换、员工待办和历史；桌面侧栏收起、子页定位及 390px/760px 实际页面容器布局正常。移动抽屉选择与关闭由真实 Element Plus 组件测试覆盖。当前账号没有评价任务或已完成报告，本次没有新增业务数据，答题和报告细节使用已有组件/Store 回归验证，未重跑真实提交、完成和计分闭环。

截图位于本机 `output/playwright/feedback-layout.png`、`feedback-editor-layout.png`、`feedback-publication-layout.png`、`feedback-employee-layout.png` 和 `feedback-responsive-layout.png`，不随 Git 分发。

2026-09-03 富文本工具栏调整：按需引入 `@iconify-vue/lucide@1.0.61`，保留 Tiptap、Element Plus 按钮和受限 JSON 契约。内置浏览器已验证九个格式图标的命令、选中高亮、中文焦点提示、回车触发，以及预览不显示工具栏且 `contenteditable=false`；生产构建通过。验证输入仅存在于独立标签页，未保存至项目。截图为本机 `output/playwright/iconify-toolbar.png`。

同日补充显示修复：全局 `font-synthesis: none` 使已有斜体标记的中文仍显示为正体，现仅在富文本区域允许字形合成；引用块补齐左侧竖线、浅色背景与内边距。内置浏览器已核对局部中文选择的斜体切换，以及编辑区、电脑和手机只读预览的实际显示，生产构建通过。截图为 `output/playwright/richtext-format-after.png` 和 `richtext-format-mobile-preview.png`；本轮仍未保存验证输入。

同日题型面板调整：五种入口改为“Iconify 图标＋题型名称”，原有说明通过 Element Plus 悬浮与焦点提示展示。内置浏览器已核对五个图标及对应题型添加、键盘回车添加和说明提示，生产构建通过；测试题目仅存在于独立标签页，未保存至项目。截图为本机 `output/playwright/question-type-icons.png`。

同日停用页面说明：编辑器、电脑/手机预览、员工答题和历史页只使用统一问卷说明；分页保留标题、顺序和题目。前端加载、新增页面及保存均移除 `pageDescription`，后端页面模型拒绝该字段且不再输出，数据库旧列仅保留冻结记录的历史兼容数据。

已验证：前端草稿 Store 和真实 Element Plus 答题组件共 12 项回归通过；后端 P4 模型/P4 PostgreSQL/P5 发布/P6 员工接口共 24 项通过，涵盖说明保存恢复及历史字段不再暴露；前端生产构建通过。内置浏览器核对两页编辑、电脑和手机预览，验证内容未保存至用户项目。本地后端重载后，OpenAPI 页面输入/输出模型均已移除该字段，真实编辑器读取正常。截图为本机 `output/playwright/no-page-description-editor.png` 和 `no-page-description-mobile-preview.png`。

同日画布编辑调整：题目标题、说明、单选选项/分值及五种题型参数改为画布内直接编辑；选中题目显示 Iconify 复制、上移、下移、删除按钮，支持中文提示、键盘触发、边界禁用和删除确认。右侧保留必答、计分、指标与所在页面规则；页面标题从左侧大纲重命名。所有修改仍经原有 Pinia、题型注册表、定点数工具及草稿 API 保存，预览和员工答题继续使用共享渲染器。

已验证：5 个相关测试文件共 40 项通过，覆盖五题型参数、内容编辑、复制独立标识、排序、删除取消与确认对象、指标及跨页移动、空字段定位、防重复保存、回车/输入法保护和模拟接口保存重载；生产构建通过。内置浏览器验证实际文本/数字输入、键盘复制与排序、删除取消/确认、大纲重命名、星数更新和电脑/手机预览；较长题目标题的大纲宽度已核对，输入框回车不会刷新页面。浏览器验证内容仅留在独立未保存标签页，未写入用户项目；本轮未重跑后端计分或正式发布流程。截图为本机 `output/playwright/canvas-inline-editing.png` 与 `canvas-inline-user-desktop.png`。

同日题目内容引导调整：五种题型统一使用图标题型标签、作答方式和可见的“题目内容”标签。新建题目不预填“新的××题”，仅显示对应业务示例占位提示；大纲、题目规则栏及指标选题列表标明待填写状态。已有标题原样保留，空题复制后继续接受必填校验，示例与图标元数据不会进入草稿保存载荷。

已验证：相关 5 个测试文件共 47 项通过，生产构建通过；`questionnaire-editor.spec.js` 单项模拟接口端到端回归通过，覆盖五题型、多页、指标、保存重载和手机预览。自动化浏览器首次因沙箱 `spawn EPERM` 未能启动，清理该次测试残留进程后在获准环境中重跑通过。内置浏览器逐一核对五题型空内容与示例、填写后大纲同步、空内容预览拦截及电脑/手机预览；预览仅展示填写内容，无示例泄漏或横向溢出。独立验证标签页已关闭且未保存测试内容，原页面两道题及四个单选选项/分值已核对保留。截图为本机 `output/playwright/question-content-empty.png`、`question-content-text.png`、`question-content-mobile-preview.png`、`question-content-user-desktop.png`；本轮不作为后端计分或正式发布流程的新验证证据。

同日题卡紧凑布局调整（已验证）：收紧题卡内外间距、标题/说明间距、选项行和参数区留白；宽画布评分参数并排，问答编辑预览改为两行。内置浏览器同一草稿、同一选中状态下，四选项单选题高度由约 348px 降至 250px，选中的星级题由约 339px 降至 266px；题目内容、选项和分值未改动。独立标签页核对五题型、长文本换行、选项错误提示撑开且不覆盖下一行、参数并排及无横向溢出；电脑预览仍使用 42px 选项行和四行问答输入。3 个相关测试文件共 31 项通过，生产构建通过。截图为本机 `output/playwright/question-compact-user.png`、`question-compact-parameters.png` 和 `question-compact-five-types.png`；验证标签页未保存且已关闭。

同日题目操作悬停调整（已验证）：鼠标移入任意题卡即可显示复制、上移、下移和删除图标；未选中题卡在移出后隐藏，选中或获得键盘焦点时保持显示，触屏设备保留可见入口。内置浏览器验证未选中题卡悬停前后高度均为约 142px，悬停不会改变当前选择；直接点击其复制按钮后，副本来自悬停题目。9 项画布交互回归及生产构建通过，独立验证标签页未保存并已关闭。截图为本机 `output/playwright/question-actions-hover.png`。

同日默认必答调整（已验证）：五种题型的 `createDefault()` 均显式设置 `isRequired: true`，新建题卡显示必答标识，右侧开关默认开启；已有草稿、复制及手动关闭的选答配置仍沿用原值。5 个相关测试文件共 52 项及生产构建通过，覆盖默认值、规范化、复制、序列化、画布开关和模拟接口保存。内置浏览器逐一确认五题型新建开关均为开启，关闭后可保持选答。原页面未保存的五道题已按内容、说明、选项/分值、评分参数和开关逐项核对保留，未保存或发布用户草稿。

同日整数默认值与实时预览调整（已验证）：单选题选项输入显示整数，批量设置拒绝非法分值并指出行号，历史小数分值提示重新设置而不自动取整；数字输入和滑动评分新题默认0位小数。大纲提供页/题型图标、题量、带提示的页面操作和选中状态。右侧默认展示当前页实时预览，编辑即时同步，可试填并单独重置；文案修改保留试填，约束变化只重置对应题目。电脑/手机弹窗共用预览文档组件，未填完整的草稿也可预览，保存校验仍保留。

本轮验证：前端5个相关测试文件59项通过；后端问卷契约及真实隔离库`ruoyi_feedback_test`共17项通过，包含整数保存/重载、小数保存拒绝后版本号与原分值不变、历史冻结配置保持可读取；Ruff检查及格式检查通过。Playwright问卷编辑、五题型、多页、指标、保存重载与手机预览1项通过（接口为测试夹具）。生产构建通过；最后一次首次构建在产物生成后遇到Windows Node/libuv退出断言，重新执行`npm run build`正常退出0。

内置浏览器独立标签核对五题型试填、整数批量校验、文案与选项实时同步、选项附加原因保持、滑块方向键作答、页面重命名同步和手机预览；1280px与2050px视口无横向溢出。原标签五道空内容必答题、问卷标题及其他配置已核对保留，当前新建数字/滑动题按要求设为0位小数；没有保存或发布用户草稿。截图为本机`output/playwright/live-preview-slider.png`、`live-preview-user-desktop.png`和`live-preview-mobile.png`。

同日单选题最低分调整（已验证）：新建题目的所有默认选项、新增选项和批量设置省略分值均默认1分，最低1分；显式0分和小数均不能保存或发布。历史已保存的0分与小数配置仍可读取，编辑器提示重新设置，历史冻结答案与计算结果不改写。前端3个相关文件40项、后端P3/P4契约与P4/P6隔离PostgreSQL回归33项通过，Ruff检查、格式检查及生产构建通过。内置浏览器核对默认/新增均为1分、输入0回到最低1分、批量拒绝0及省略分值默认1分；原标签选项文字、五题内容和数字输入最高分101已保留，将当前两个0分选项按要求改为1分，未保存或发布草稿。

同日预览去题框调整（已验证）：实时预览与电脑/手机弹窗改为连续问卷排版，移除单题外框、圆角和选中阴影，以题号及留白区分题目，当前题仅保留文字提示。内置浏览器核对多题预览的边框为0、阴影为none、无横向溢出，生产构建通过；仅调整共享预览样式，用户当前选项文字、3/2/1分值和未保存内容保持。

同日预览题号与选项调整（已验证）：五种题型在实时预览和电脑/手机弹窗统一显示“1、题目内容”，必答标记及题目说明保留，单选选项使用无边框的 Element Plus 单选按钮。内置浏览器验证长标题/长选项换行、选择选项后填写原因、文案修改保留试填，以及375px手机预览无横向溢出；相关组件测试33项和生产构建通过。交互验证在独立标签内完成，未保存测试文案。

同日问卷标题与预览分隔调整（已验证）：共享预览标题居中，实时预览的操作提示下增加分隔线及20px留白，问卷说明保持左对齐。内置浏览器核对实时、电脑和375px手机预览的标题对齐及无横向溢出，原标签的单选试填状态保留，生产构建通过。

同日滑动评分同行布局调整（已验证）：移除窄预览区域的强制折行，复用 Element Plus 滑块的弹性滑轨和固定宽度数值框。内置浏览器确认实时、电脑和375px手机预览的滑轨与数值框垂直中心一致、无横向溢出；方向键调整与数值输入双向联动正常，实际操作后清除未作答提示。生产构建通过，未修改题目配置或正式答案。

同日PC分页实时预览收口（已验证）：移除“电脑 / 手机预览”按钮及独立弹窗，首期仅通过PC登录作答。实时预览将当前页码、分页与重新试填操作移到通栏分隔线上方，正文移除页名，每页均显示问卷标题及说明；切页同步大纲与画布、回到问卷开头，保留各页试填内容。内置浏览器验证单页、空白新页、多页切换、单选及问答试填往返保留，实际滚动容器及问卷正文无横向溢出。相关组件测试25项、P4端到端测试1项及生产构建通过；浏览器测试文案未保存。前述手机预览记录保留为历史验证快照，不代表当前交付范围。

同日侧栏默认页签与宽度调整（已验证）：进入设计器默认选中题目属性，切换实时预览时按可用宽度加宽右栏，切回题目属性或评价指标恢复原宽度。内置浏览器实测2050px窗口为390→760px，1280px窗口为330→约407px，无横向溢出，切换页签保留试填选择。相关组件测试26项、P4端到端测试1项和生产构建通过。热更新触发编辑器重载后，已通过页面操作恢复当时未保存的4页结构及第二页3道空题，仍保持未保存状态。

同日纸张预览样式调整（已验证）：通栏分隔线下使用浅灰背景，问卷正文采用白纸、细边框、轻阴影和随宽度调整的页边留白；上方操作区独立保持白底。内置浏览器检查2050px和1280px窗口，正文及滚动容器无横向溢出，滑轨与数值框保持同行，切换题目属性后返回仍保留试填选择；生产构建通过。截图为本机 `output/playwright/paper-preview-wide.png` 和 `paper-preview-narrow.png`。本次仅调整样式，原标签未保存的4页草稿保持。

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
