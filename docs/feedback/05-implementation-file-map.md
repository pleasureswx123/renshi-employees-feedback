# 计划文件清单

本清单描述后续可能使用的文件和职责。标记“计划”的路径尚未创建，不代表已经实现。

## 1. 后端

```text
ruoyi-fastapi-backend/
├─ module_feedback/                         # 计划：评价核心模块
│  ├─ controller/
│  │  ├─ project_controller.py
│  │  ├─ questionnaire_controller.py
│  │  ├─ participant_controller.py
│  │  ├─ task_controller.py
│  │  ├─ progress_controller.py
│  │  └─ report_controller.py
│  ├─ service/
│  │  ├─ project_service.py
│  │  ├─ questionnaire_service.py
│  │  ├─ publication_service.py
│  │  ├─ task_service.py
│  │  ├─ answer_service.py
│  │  └─ report_service.py
│  ├─ dao/
│  ├─ entity/
│  │  ├─ do/
│  │  └─ vo/
│  ├─ calculators/
│  │  └─ score_calculator.py
│  ├─ validators/
│  │  └─ publication_validator.py
│  └─ enums/
│     └─ feedback_enums.py
├─ alembic/versions/
│  └─ 2026_09_02_1100-20260902_01_feedback_baseline.py
│                                            # 已存在：RuoYi PostgreSQL基线revision
├─ scripts/
│  └─ feedback_p0_database_precheck.py       # 已存在：独立开发/测试库与Redis隔离预检
├─ tests/scripts/
│  └─ test_feedback_p0_database_precheck.py  # 已存在：P0预检脚本直接测试
└─ tests/module_feedback/                    # 计划：评价业务测试
```

具体拆分可以随实现调整，但Controller、Service、DAO、实体、计算器和发布校验职责不得混在单一大文件中。

## 2. 平台前端

```text
feedback-frontend/
├─ AGENTS.md                                # 已存在：平台端规则
├─ README.md                                # 已存在：平台端说明和文档入口
├─ package.json                             # 计划
├─ vite.config.js                           # 计划
├─ index.html                               # 计划
├─ src/
│  ├─ main.js
│  ├─ App.vue
│  ├─ api/
│  │  ├─ auth.js
│  │  └─ feedback/
│  │     ├─ projects.js
│  │     ├─ questionnaires.js
│  │     ├─ participants.js
│  │     ├─ tasks.js
│  │     ├─ progress.js
│  │     └─ reports.js
│  ├─ components/feedback/
│  │  ├─ question-renderers/
│  │  ├─ questionnaire-editor/
│  │  ├─ participant-selector/
│  │  └─ score-display/
│  ├─ layouts/
│  │  ├─ HrLayout.vue
│  │  └─ EmployeeLayout.vue
│  ├─ router/
│  │  └─ index.js
│  ├─ stores/
│  │  ├─ auth.js
│  │  ├─ permission.js
│  │  └─ questionnaireEditor.js
│  ├─ utils/
│  │  ├─ request.js
│  │  ├─ auth.js
│  │  └─ transportCrypto.js
│  └─ views/
│     ├─ auth/
│     ├─ employee/
│     │  ├─ TodoList.vue
│     │  ├─ TodoDetail.vue
│     │  ├─ AnswerPage.vue
│     │  ├─ SubmittedList.vue
│     │  └─ SubmittedDetail.vue
│     └─ hr/
│        ├─ ProjectList.vue
│        ├─ ProjectEditor.vue
│        ├─ Participants.vue
│        ├─ Publication.vue
│        ├─ Progress.vue
│        └─ Reports.vue
└─ tests/                                   # 计划
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
└─ 09-implementation-roadmap.md
```

## 5. 文件创建原则

- 不一次性创建没有行为的空代码文件。
- 每个实现阶段只创建能形成完整垂直功能或明确公共能力的文件。
- 创建后及时把本清单中的“计划”更新为实际路径和状态。
- 不为未来能力预建模板、强制分布或复杂图表目录。
