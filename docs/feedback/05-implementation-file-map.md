# 计划文件清单

本清单登记已落地文件。P9安全、迁移、性能和验收文件已落地，功能完成状态、测试遗留项与直接验证证据以实施路线图和P9验收报告为准。

## 1. 后端

```text
ruoyi-fastapi-backend/
├─ module_feedback/                         # 已存在：评价核心模块入口
│  ├─ __init__.py                           # 已存在：模块路由注册
│  ├─ constants.py                          # 已存在：P5固定关系Code、类型和零权重默认协议
│  ├─ controller/
│  │  ├─ feedback_controller.py             # 已存在：受登录保护的只读健康接口
│  │  ├─ project_controller.py              # 已存在：项目、问卷、发布及P7进度/预检/完成接口
│  │  ├─ employee_controller.py             # 已存在：P6本人待办、草稿、提交和历史接口
│  │  └─ report_controller.py               # 已存在：P8报告生成、报告查询与独立原始答案接口
│  ├─ service/
│  │  ├─ project_service.py                 # 已存在：P3项目事务及P5新项目固定关系初始化
│  │  ├─ questionnaire_service.py           # 已存在：P4聚合草稿事务、恢复、校验和乐观锁
│  │  ├─ state_transition_service.py        # 已存在：项目与任务状态门禁
│  │  ├─ publication_service.py             # 已存在：P5聚合配置、发布校验、锁、快照和单事务发布
│  │  ├─ employee_service.py                # 已存在：P6身份归属、冻结问卷和只读历史
│  │  ├─ answer_service.py                  # 已存在：P6草稿/提交事务、乐观锁、幂等与快照
│  │  ├─ progress_service.py                # 已存在：P7统计、数据范围、预检和手动完成事务
│  │  ├─ report_service.py                  # 已存在：P8范围、精度门禁、幂等生成事务和报告投影
│  │  ├─ schema_service.py                  # 已存在：P9迁移版本与正式得分精度就绪门禁
│  │  └─ scoring_input.py                   # 已存在：P8冻结输入与已提交原始分一致性校验
│  ├─ dao/
│  │  ├─ project_dao.py                     # 已存在：项目查询、锁定和持久化
│  │  ├─ questionnaire_dao.py               # 已存在：问卷草稿查询、锁定和整体替换
│  │  ├─ assignment_dao.py                  # 已存在：评价任务查询与锁定
│  │  ├─ publication_dao.py                 # 已存在：P5关系/目标/选择替换、人员锁定和冻结读取
│  │  ├─ answer_dao.py                      # 已存在：答卷查询与锁定
│  │  ├─ employee_dao.py                    # 已存在：P6本人任务分页统计与项目/任务锁
│  │  ├─ progress_dao.py                    # 已存在：P7进度聚合、明细分页、项目/任务锁和完成审计
│  │  ├─ score_result_dao.py                # 已存在：计分结果查询
│  │  ├─ schema_dao.py                      # 已存在：P9只读查询实际Alembic版本
│  │  └─ report_dao.py                      # 已存在：P8范围内结果、精度检查、并列排名和提交答案查询
│  ├─ entity/do/
│  │  ├─ mixins.py                          # 已存在：审计和乐观锁字段
│  │  ├─ project_do.py                      # 已存在：评价项目及P7不可变完成审计实体
│  │  ├─ questionnaire_do.py                # 已存在：问卷、题目、选项和指标实体
│  │  ├─ relation_do.py                     # 已存在：评价关系实体
│  │  ├─ participant_do.py                  # 已存在：被评价人快照、评价人选择配置和正式任务实体
│  │  ├─ answer_do.py                       # 已存在：答卷和答案实体
│  │  └─ score_do.py                        # 已存在：计分结果实体
│  ├─ entity/vo/
│  │  ├─ project_vo.py                      # 已存在：P3项目请求和响应协议
│  │  ├─ questionnaire_vo.py                # 已存在：P4问卷页面、富文本和聚合草稿协议
│  │  ├─ questionnaire_question_vo.py       # 已存在：五种题型Pydantic判别联合
│  │  ├─ indicator_vo.py                    # 已存在：指标及稳定题目Code绑定协议
│  │  ├─ publication_vo.py                  # 已存在：P5人员候选、聚合配置、预览和发布协议
│  │  ├─ employee_vo.py                     # 已存在：P6员工查询、答案、保存和提交协议
│  │  ├─ progress_vo.py                     # 已存在：P7统计、明细、预检和完成协议
│  │  └─ report_vo.py                       # 已存在：P8报告安全响应与独立原始答案协议
│  ├─ calculators/
│  │  ├─ raw_score.py                       # 已存在：P6 Decimal原始分
│  │  └─ report_score.py                    # 已存在：P8百分制、关系归一化、缺失标记与可复算依据
│  ├─ validators/
│  │  ├─ questionnaire_validator.py         # 已存在：结构错误、富文本与发布就绪校验
│  │  ├─ publication_validator.py           # 已存在：P5人员、关系、选择和组合发布校验
│  │  └─ answer_validator.py                # 已存在：P6冻结版本引用、五题型及提交校验
│  └─ enums/
│     └─ feedback_enums.py                  # 已存在：P2领域枚举
├─ alembic/versions/
│  ├─ 2026_09_02_1100-20260902_01_feedback_baseline.py
│  │                                          # 已存在：RuoYi PostgreSQL基线revision
│  ├─ 2026_09_02_1200-20260902_02_feedback_domain.py
│  │                                          # 已存在：13张P2领域表及约束、索引、注释
│  ├─ 2026_09_02_1300-20260902_03_feedback_designer.py
│  │                                          # 已存在：P4富文本说明和页面稳定标识迁移
│  ├─ 2026_09_02_1400-20260902_04_feedback_publication.py
│  │                                          # 已存在：P5评价人选择配置表和固定关系回填
│  ├─ 2026_09_02_1500-20260902_05_feedback_answering.py
│  │                                          # 已存在：P6原始总分扩容与安全降级检查
│  ├─ 2026_09_02_1600-20260902_06_feedback_permissions.py
│  │                                          # 已存在：现有RuoYi授权目录增量，不自动授权
│  ├─ 2026_09_02_1700-20260902_07_feedback_completion_audit.py
│  │                                          # 已存在：P7不可变完成审计和受保护降级
│  └─ 2026_09_03_1000-20260903_08_feedback_scoring.py
│                                             # 已存在：P8正式结果/实际权重完整精度与降级保护
├─ scripts/
│  ├─ feedback_p0_database_precheck.py       # 已存在：独立开发/测试库与Redis隔离预检
│  ├─ feedback_p2_schema_verify.py           # 已存在：领域结构、注释和迁移往返验证
│  ├─ feedback_p6_e2e_fixture.py             # 已存在：P6至P9隔离库夹具、权限/审计/报告对账和精确清理
│  ├─ feedback_p9_api_audit.py               # 已存在：28个实际路由权限和数据范围审计
│  ├─ feedback_p9_migration.py               # 已存在：只读审计、一致快照备份恢复、严格接管与原行摘要校验
│  ├─ feedback_p9_performance.py             # 已存在：真实服务性能数据集与EXPLAIN ANALYZE采集
│  └─ feedback_p6_e2e_server.py              # 已存在：完整应用的隔离库E2E启动器
├─ requirements-test.txt                    # 已存在：项目虚拟环境测试依赖
├─ tests/scripts/
│  └─ test_feedback_p0_database_precheck.py  # 已存在：P0预检脚本直接测试
└─ tests/module_feedback/
   ├─ controller/                            # 已存在：模块入口、项目、草稿、P7完成、P8报告及P9全路由权限/脱敏测试
   ├─ calculators/                           # 已存在：P8手算、多人多指标、缺失、自评、零分与精度测试
   ├─ enums/                                 # 已存在：枚举契约测试
   ├─ service/                               # 已存在：状态门禁、P3至P8真实服务/并发/报告及P9五种数据范围/就绪检查
   ├─ entity/                                # 已存在：模型、约束元数据、P3/P4 VO及P5固定关系测试
   ├─ dao/                                   # 已存在：DAO单元及真实PostgreSQL事务测试
   └─ migration/                             # 已存在：结构、权限/审计/精度保护及P9全新库备份恢复/接管失败回滚
```

具体拆分可以随实现调整，但Controller、Service、DAO、实体、计算器和发布校验职责不得混在单一大文件中。

P9还修改公共`common/aspect/data_scope.py`、`common/annotation/log_annotation.py`、`exceptions/handle.py`与`config/lifecycle.py`，分别修复空角色范围、安全日志/错误边界和评价表不得绕过Alembic创建；公共生命周期有直接回归。

## 2. 平台前端

```text
feedback-frontend/
├─ AGENTS.md                                # 已存在：平台端规则
├─ README.md                                # 已存在：平台端说明和文档入口
├─ package.json                             # 已存在：依赖与开发、构建、测试命令
├─ package-lock.json                        # 已存在：锁定依赖版本
├─ vite.config.js                           # 已存在：Vite与后端代理配置
├─ vitest.config.js                         # 已存在：前端单元测试配置
├─ playwright.config.js                     # 已存在：浏览器E2E配置
├─ playwright.live.config.js                # 已存在：完整后端/数据库真实E2E配置
├─ index.html                               # 已存在：应用入口
├─ src/
│  ├─ main.js                               # 已存在：Vue、Pinia、Router、Element Plus入口
│  ├─ App.vue                               # 已存在
│  ├─ api/
│  │  ├─ auth.js                            # 已存在：登录、当前用户和退出接口
│  │  └─ feedback/
│  │     ├─ projects.js                     # 已存在：项目、问卷、发布及P7进度/预检/完成接口
│  │     ├─ tasks.js                        # 已存在：P6本人任务、暂存、提交和历史接口
│  │     └─ reports.js                      # 已存在：P8报告项目、生成、团队/个人报告和原始答案接口
│  ├─ constants/
│  │  └─ feedbackEnums.js                   # 已存在：与后端/数据库一致的领域枚举
│  ├─ components/
│  │  ├─ WorkspaceSwitcher.vue              # 已存在：双工作台切换
│  │  └─ feedback/
│  │     ├─ QuestionnairePreviewDialog.vue  # 已存在：P4五题型电脑/手机预览
│  │     ├─ QuestionnaireOutline.vue        # 已存在：多页大纲、排序和跨页移动
│  │     ├─ QuestionTypePanel.vue           # 已存在：五种题型入口
│  │     ├─ IndicatorPanel.vue              # 已存在：指标、权重和题目绑定
│  │     ├─ RichTextEditor.vue              # 已存在：受限Tiptap JSON编辑与只读渲染
│  │     ├─ EmployeeTaskCard.vue             # 已存在：P6被评价人任务卡片与权限入口
│  │     ├─ publication/                    # 已存在：P5目标、关系、评价人双栏和发布预览组件
│  │     ├─ progress/                       # 已存在：P7进度KPI、明细列表和完成预检抽屉
│  │     ├─ reports/PersonalReportPanel.vue # 已存在：P8个人指标、关系权重和题目明细表格
│  │     └─ questions/
│  │        ├─ questionTypeRegistry.js       # 已存在：五题型完整注册定义
│  │        ├─ QuestionRenderer.vue          # 已存在：编辑/预览/员工答题/历史只读共用入口
│  │        ├─ QuestionPropertiesPanel.vue  # 已存在：注册表驱动的属性面板
│  │        ├─ SingleChoiceProperties.vue   # 已存在：单选题属性表单
│  │        ├─ ScoreRangeProperties.vue     # 已存在：三种区间评分题属性表单
│  │        ├─ TextProperties.vue           # 已存在：问答题属性表单
│  │        ├─ SingleChoiceQuestion.vue      # 已存在：单选题编辑/只读渲染
│  │        ├─ StarRatingQuestion.vue        # 已存在：星级题编辑/只读渲染
│  │        ├─ NumericInputQuestion.vue      # 已存在：数字题编辑/只读渲染
│  │        ├─ SliderQuestion.vue            # 已存在：滑动题编辑/只读渲染
│  │        └─ TextQuestion.vue              # 已存在：问答题编辑/只读渲染
│  ├─ layouts/
│  │  ├─ WorkspaceLayout.vue                # 已存在：共享工作台框架
│  │  ├─ HrLayout.vue                       # 已存在
│  │  └─ EmployeeLayout.vue                 # 已存在
│  ├─ router/
│  │  └─ index.js                           # 已存在：固定路由、权限守卫及P5发布/P7进度/P8报告独立权限路由
│  ├─ stores/
│  │  ├─ auth.js                            # 已存在：Token与会话恢复
│  │  ├─ permission.js                      # 已存在：权限并集与入口判定
│  │  ├─ questionnaireDraft.js              # 已存在：多页/题目/指标编辑、保存和ID水合动作
│  │  ├─ publicationConfig.js               # 已存在：P5聚合配置、脏状态、预览和发布动作
│  │  ├─ answerSheet.js                     # 已存在：P6内存答卷、恢复、防重入与上下文隔离
│  │  ├─ projectProgress.js                 # 已存在：P7进度、预检、完成和未知结果状态隔离
│  │  └─ projectReports.js                  # 已存在：P8生成/查询、项目与目标隔离、权限错误清理
│  ├─ utils/
│  │  ├─ request.js                         # 已存在：请求、401、错误和下载
│  │  ├─ auth.js                            # 已存在：Token持久化
│  │  ├─ sessionCache.js                    # 已存在：会话级策略缓存
│  │  ├─ transportCryptoPolicy.js           # 已存在：后端传输策略同步
│  │  ├─ transportCrypto.js                 # 已存在：加解密信封实现
│  │  ├─ questionnaireDraft.js              # 已存在：P4草稿规范化、校验和满分预览
│  │  ├─ publicationConfig.js               # 已存在：P5配置规范化、固定关系与序列化校验
│  │  ├─ answerSheet.js                     # 已存在：P6五题型答案校验、恢复和定点序列化
│  │  ├─ fixedDecimal.js                    # 已存在：四位定点数运算与序列化
│  │  └─ stableCode.js                      # 已存在：页面、题目、选项和指标稳定标识
│  └─ views/
│     ├─ auth/LoginView.vue                  # 已存在：Element Plus登录表单
│     ├─ errors/                             # 已存在：403与404页面
│     ├─ hr/
│     │  ├─ ProjectListView.vue              # 已存在：P3项目草稿管理
│     │  ├─ QuestionnaireEditorView.vue      # 已存在：P4五题型、多页、指标设计器
│     │  ├─ PublicationConfigView.vue        # 已存在：P5人员关系配置、权威预览、发布和只读复核
│     │  ├─ ProjectProgressEntryView.vue     # 已存在：P7仅进度权限的项目定位入口
│     │  ├─ ProjectProgressView.vue          # 已存在：P7回收进度、筛选、预检和完成页面
│     │  ├─ ReportProjectsView.vue           # 已存在：P8仅报告权限可用的已完成项目列表
│     │  ├─ ProjectReportsView.vue           # 已存在：P8生成、团队排名、个人报告抽屉
│     │  └─ SubmittedAnswersView.vue         # 已存在：P8独立答案权限入口、列表和只读五题型抽屉
│     ├─ employee/
│     │  ├─ EmployeeProjectsView.vue         # 已存在：P6我的待办项目列表
│     │  ├─ EmployeeProjectView.vue          # 已存在：P6本人任务与独立进度
│     │  ├─ EmployeeHistoryView.vue          # 已存在：P6本人已提交历史
│     │  └─ AnswerSheetView.vue              # 已存在：P6分页表单、暂存、确认提交和只读详情
│     └─ shared/PlaceholderView.vue          # 已存在：明确未实现业务边界
└─ tests/
   ├─ api/                                   # 已存在：登录、项目、草稿、P5发布、P7完成和P8报告测试
   ├─ components/                            # 已存在：工作台、五题型、P5发布、P7进度和P8报告组件测试
   ├─ router/                                # 已存在：P8报告/原始答案权限路由与退出清理测试
   ├─ constants/feedbackEnums.test.js        # 已存在：P2枚举契约测试
   ├─ stores/                                # 已存在：权限、P4草稿、P5发布、P6答题、P7进度和P8报告隔离测试
   ├─ utils/                                 # 已存在：四位定点数和P5配置协议测试
   ├─ e2e/                                   # 已存在：登录、P4、P5发布及P7进度/完成浏览器测试（Mock接口）
   └─ live-e2e/employee-answering.spec.js    # 已存在：P6至P9两条真实闭环，覆盖场景A至F、权限和数据库/审计对账
```

## 3. 管理端

`ruoyi-fastapi-frontend` 原则上只需要：

- 评价平台权限码和角色配置。
- 必要的字典数据。
- 如确有必要，增加评价模块运维入口；不放置评价业务工作台。

## 4. 项目文档

```text
docs/feedback/
├─ README.md
├─ 01-product-baseline.md
├─ 02-architecture-and-boundaries.md
├─ 03-domain-model-and-state-machine.md
├─ 04-postgresql-data-design.md
├─ 05-implementation-file-map.md
├─ 06-mvp-scope-and-acceptance.md
├─ 07-code-generator-usage.md
├─ 08-decisions-and-open-questions.md
├─ 09-implementation-roadmap.md
├─ 10-p2-field-dictionary.md
├─ 11-p4-questionnaire-designer-precheck.md
├─ 12-p5-publication-precheck.md
├─ 13-p6-answering-precheck.md
├─ 14-p7-progress-completion-precheck.md
├─ 15-p8-scoring-reports-precheck.md
├─ 16-p9-release-acceptance.md
├─ 17-operations-runbook.md
└─ evidence/
   ├─ p9-api-matrix.md
   └─ p9-performance.json
```

## 5. 文件创建原则

- 不一次性创建没有行为的空代码文件。
- 每个实现阶段只创建能形成完整垂直功能或明确公共能力的文件。
- 创建后及时把本清单中的“计划”更新为实际路径和状态。
- 不为未来能力预建模板、强制分布或复杂图表目录。
