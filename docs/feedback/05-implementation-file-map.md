# 计划文件清单

本清单同时登记已落地文件和下一阶段计划。标记“计划”的路径尚未创建，不代表已经实现；P4已按[技术预检](./11-p4-questionnaire-designer-precheck.md)完成，后续计划从P5开始。

## 1. 后端

```text
ruoyi-fastapi-backend/
├─ module_feedback/                         # 已存在：评价核心模块入口
│  ├─ __init__.py                           # 已存在：模块路由注册
│  ├─ controller/
│  │  ├─ feedback_controller.py             # 已存在：受登录保护的只读健康接口
│  │  └─ project_controller.py              # 已存在：项目CRUD和P4问卷草稿GET/PUT
│  ├─ service/
│  │  ├─ project_service.py                 # 已存在：P3项目状态、权限、数据范围和事务
│  │  ├─ questionnaire_service.py           # 已存在：P4聚合草稿事务、恢复、校验和乐观锁
│  │  └─ state_transition_service.py        # 已存在：项目与任务状态门禁
│  ├─ dao/
│  │  ├─ project_dao.py                     # 已存在：项目查询、锁定和持久化
│  │  ├─ questionnaire_dao.py               # 已存在：问卷草稿查询、锁定和整体替换
│  │  ├─ assignment_dao.py                  # 已存在：评价任务查询与锁定
│  │  ├─ answer_dao.py                      # 已存在：答卷查询与锁定
│  │  └─ score_result_dao.py                # 已存在：计分结果查询
│  ├─ entity/do/
│  │  ├─ mixins.py                          # 已存在：审计和乐观锁字段
│  │  ├─ project_do.py                      # 已存在：评价项目实体
│  │  ├─ questionnaire_do.py                # 已存在：问卷、题目、选项和指标实体
│  │  ├─ relation_do.py                     # 已存在：评价关系实体
│  │  ├─ participant_do.py                  # 已存在：被评价人快照和任务实体
│  │  ├─ answer_do.py                       # 已存在：答卷和答案实体
│  │  └─ score_do.py                        # 已存在：计分结果实体
│  ├─ entity/vo/
│  │  ├─ project_vo.py                      # 已存在：P3项目请求和响应协议
│  │  ├─ questionnaire_vo.py                # 已存在：P4问卷页面、富文本和聚合草稿协议
│  │  ├─ questionnaire_question_vo.py       # 已存在：五种题型Pydantic判别联合
│  │  └─ indicator_vo.py                    # 已存在：指标及稳定题目Code绑定协议
│  ├─ calculators/                          # 计划：P8计分实现
│  ├─ validators/
│  │  └─ questionnaire_validator.py         # 已存在：结构错误、富文本与发布就绪校验
│  └─ enums/
│     └─ feedback_enums.py                  # 已存在：P2领域枚举
├─ alembic/versions/
│  ├─ 2026_09_02_1100-20260902_01_feedback_baseline.py
│  │                                          # 已存在：RuoYi PostgreSQL基线revision
│  ├─ 2026_09_02_1200-20260902_02_feedback_domain.py
│  │                                          # 已存在：13张P2领域表及约束、索引、注释
│  └─ 2026_09_02_1300-20260902_03_feedback_designer.py
│                                             # 已存在：P4富文本说明和页面稳定标识迁移
├─ scripts/
│  ├─ feedback_p0_database_precheck.py       # 已存在：独立开发/测试库与Redis隔离预检
│  └─ feedback_p2_schema_verify.py           # 已存在：P2/P4结构和两级可逆迁移验证
├─ tests/scripts/
│  └─ test_feedback_p0_database_precheck.py  # 已存在：P0预检脚本直接测试
└─ tests/module_feedback/
   ├─ controller/                            # 已存在：模块入口、项目和草稿API测试
   ├─ enums/                                 # 已存在：枚举契约测试
   ├─ service/                               # 已存在：状态门禁及P3/P4真实PostgreSQL服务测试
   ├─ entity/                                # 已存在：模型、约束元数据和P3/P4 VO测试
   ├─ dao/                                   # 已存在：DAO单元及真实PostgreSQL事务测试
   └─ migration/                             # 已存在：结构验证器门禁测试
```

具体拆分可以随实现调整，但Controller、Service、DAO、实体、计算器和发布校验职责不得混在单一大文件中。

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
├─ index.html                               # 已存在：应用入口
├─ src/
│  ├─ main.js                               # 已存在：Vue、Pinia、Router、Element Plus入口
│  ├─ App.vue                               # 已存在
│  ├─ api/
│  │  ├─ auth.js                            # 已存在：登录、当前用户和退出接口
│  │  └─ feedback/
│  │     └─ projects.js                     # 已存在：项目CRUD和P4聚合问卷草稿接口
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
│  │     └─ questions/
│  │        ├─ questionTypeRegistry.js       # 已存在：五题型完整注册定义
│  │        ├─ QuestionRenderer.vue          # 已存在：编辑预览共用渲染入口
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
│  │  └─ index.js                           # 已存在：固定路由与权限守卫
│  ├─ stores/
│  │  ├─ auth.js                            # 已存在：Token与会话恢复
│  │  ├─ permission.js                      # 已存在：权限并集与入口判定
│  │  └─ questionnaireDraft.js              # 已存在：多页/题目/指标编辑、保存和ID水合动作
│  ├─ utils/
│  │  ├─ request.js                         # 已存在：请求、401、错误和下载
│  │  ├─ auth.js                            # 已存在：Token持久化
│  │  ├─ sessionCache.js                    # 已存在：会话级策略缓存
│  │  ├─ transportCryptoPolicy.js           # 已存在：后端传输策略同步
│  │  ├─ transportCrypto.js                 # 已存在：加解密信封实现
│  │  ├─ questionnaireDraft.js              # 已存在：P4草稿规范化、校验和满分预览
│  │  ├─ fixedDecimal.js                    # 已存在：四位定点数运算与序列化
│  │  └─ stableCode.js                      # 已存在：页面、题目、选项和指标稳定标识
│  └─ views/
│     ├─ auth/LoginView.vue                  # 已存在：Element Plus登录表单
│     ├─ errors/                             # 已存在：403与404页面
│     ├─ hr/
│     │  ├─ ProjectListView.vue              # 已存在：P3项目草稿管理
│     │  └─ QuestionnaireEditorView.vue      # 已存在：P4五题型、多页、指标设计器
│     └─ shared/PlaceholderView.vue          # 已存在：明确未实现业务边界
└─ tests/
   ├─ api/                                   # 已存在：登录、项目和草稿API测试
   ├─ components/                            # 已存在：工作台、五题型注册表和共享渲染测试
   ├─ constants/feedbackEnums.test.js        # 已存在：P2枚举契约测试
   ├─ stores/                                # 已存在：权限和P4聚合草稿Store测试
   ├─ utils/                                 # 已存在：四位定点数直接测试
   └─ e2e/                                   # 已存在：登录路由和P4完整编辑器浏览器测试
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
└─ 11-p4-questionnaire-designer-precheck.md
```

## 5. 文件创建原则

- 不一次性创建没有行为的空代码文件。
- 每个实现阶段只创建能形成完整垂直功能或明确公共能力的文件。
- 创建后及时把本清单中的“计划”更新为实际路径和状态。
- 不为未来能力预建模板、强制分布或复杂图表目录。
