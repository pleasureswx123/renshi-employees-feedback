# P4完整问卷设计器与指标技术预检

## 1. 文档状态

- 预检日期：2026-09-02。
- 适用阶段：P4“完整问卷设计器与指标”。
- 基线提交：`5fcf0c5 feat: 完成评价平台P3单选题垂直切片`。
- 预检结论：**允许进入P4实现，但必须先完成本文定义的迁移和通用协议改造，再逐题型扩展。**
- 实现复核日期：2026-09-02。
- 实现状态：**P4-01至P4-09已按本文协议完成并通过阶段门禁；本文同时保留开工时的设计依据和实现后的核验结果。**

结论分类：

- “已验证”表示已由当前代码、数据库结构或自动化/真实浏览器证据确认。
- “设计约定”表示P4实现必须遵循的已收口方案。
- “推荐方案”表示不影响产品边界的实现顺序或工程建议。
- “待确认事项”仅保留会改变产品范围的内容；当前没有阻塞P4开工的待确认项。

## 2. 预检范围与非目标

### 2.1 本次预检覆盖

- 星级评分题、数字输入评分题、滑动评分题和问答题。
- 单选题与四种新增题型共用的题型注册、编辑、预览、只读和校验协议。
- 多页问卷、页面排序、页内排序、题目跨页移动、复制和删除。
- 指标维护、权重、顺序和题目绑定。
- 问卷富文本说明的依赖、存储和安全边界。
- PostgreSQL结构适配、草稿保存事务、稳定标识和数据库ID映射。
- P4直接测试、真实PostgreSQL恢复测试和真实浏览器验收门禁。

### 2.2 本次预检不扩大首期范围

- 不加入问卷模板、代码导出、任意表单生成、Excel、公开链接或匿名参评。
- 不实现发布、人员关系和任务生成；这些仍属于P5。
- 不实现员工答卷保存和提交；这些仍属于P6。
- 不把前端满分预览作为正式计分结果；正式校验和计分继续由后端负责。
- 不使用拖拽库作为P4必要依赖；排序采用可测试、可键盘操作的明确按钮和跨页选择器。

## 3. 当前基线核验

### 3.1 已验证能力

| 能力 | 当前证据 | P4结论 |
|---|---|---|
| 五种题型枚举 | `QuestionType`和`ck_fb_question_type`已包含`SINGLE_CHOICE/STAR_RATING/NUMERIC_INPUT/SLIDER/TEXT` | 不新增题型枚举或改数据库检查约束 |
| 区间评分字段 | `fb_question.min_score/max_score`为`NUMERIC(12,4)`，`decimal_places`范围为`0..4` | 星级、数字和滑动题复用正式字段，不把分数塞入JSON |
| 题型扩展配置 | `fb_question.config`为`JSONB` | 只保存默认值、步长和字数上限等题型特有配置 |
| 多页与顺序 | 页面和题目均已有`sort_order`及唯一约束 | 现有表能承载多页，但页面缺少跨保存稳定业务标识 |
| 指标与绑定 | `fb_indicator`、`fb_indicator_question`已存在，题目绑定全表唯一 | 能表达“一题最多属于一个指标”，总权重仍需服务层聚合校验 |
| 答案值通道 | `fb_answer`已固定`OPTION/NUMERIC/TEXT`三种互斥值通道 | 五种题型不需要新增答案值列 |
| P3草稿链路 | 单选题已完成DTO、注册表、显式保存、锁版本、PostgreSQL恢复和预览 | P4在同一协议上扩展，不另建第二套设计器或保存接口 |
| P3验证基线 | 后端50项、前端17项、浏览器4项通过；真实浏览器保存/刷新恢复通过 | P4必须保留这些回归并扩大题型矩阵 |

### 3.2 已验证限制

- `QuestionDraftModel`仍是`Literal['SINGLE_CHOICE']`，草稿请求固定最多一页。
- `FeedbackQuestionnaireService`只构造单选题，并且保存时整体替换页面和题目。
- 前端题型注册表只有单选题，满分预览也只识别单选题。
- `fb_questionnaire_page`没有稳定`page_code`；只依赖会在整体替换后变化的数据库ID。
- 问卷说明当前只有`TEXT description`，无法以结构化、白名单方式保存富文本文档。
- `feedback-frontend`当前没有富文本编辑依赖，生产构建主chunk基线约为`1102.90 kB`、gzip约`366.47 kB`。

## 4. 数据库与迁移结论

### 4.1 设计约定：P4需要一条迁移

计划新增Alembic revision：

```text
20260902_03_feedback_designer
down_revision = 20260902_02_feedback_domain
```

只调整现有问卷配置表，不新增平行表：

| 表 | 变更 | 目的 |
|---|---|---|
| `fb_questionnaire_version` | 新增可空`description_doc JSONB`，中文注释“问卷富文本说明文档” | 保存经过白名单校验的Tiptap JSON；现有`description TEXT`继续保存纯文本摘要 |
| `fb_questionnaire_page` | 新增`page_code VARCHAR(64)`，回填后设为非空 | 页面在复制、排序、跨页移动和多次保存之间保持稳定业务身份 |
| `fb_questionnaire_page` | 新增唯一约束`(version_id, page_code)` | 防止同一问卷版本出现重复页面业务标识 |

### 4.2 迁移规则

- 既有页面按`P_<page_id>`确定性回填`page_code`，再设置非空和唯一约束。
- 新页面在前端创建时立即生成`P_<uuid>`并随草稿提交；后端不改写合法业务标识，但必须校验格式和版本内唯一性。
- `description_doc`允许为空；为空时继续使用`description`纯文本。P4新保存的富文本同时写入结构化文档和后端提取的纯文本摘要。
- 降级只删除新增约束和列，不删除页面、题目、指标或既有纯文本说明。
- 开发库和测试库都必须完成升级；测试库还必须执行一次P3 head → P4 head → P3 head → P4 head迁移循环。
- 迁移完成后同步更新SQLAlchemy模型、中文注释核验、P2字段字典的“P4增量”说明和结构验证测试。

### 4.3 不需要变更的结构

- 三种区间评分题继续使用`min_score/max_score/decimal_places`。
- 单选题继续使用`fb_question_option`；其他题型不得创建伪选项。
- 默认值、滑动步长、问答字数上限使用`fb_question.config`。
- 指标继续使用`fb_indicator`和`fb_indicator_question`。
- 正式答案仍使用`option_id/numeric_value/text_value`互斥通道。

## 5. 问卷草稿API协议

### 5.1 设计约定：保持一个聚合接口

继续使用：

```text
GET /feedback/projects/{projectId}/questionnaire-draft
PUT /feedback/projects/{projectId}/questionnaire-draft
```

请求根结构扩展为：

```text
versionId
lockVersion
title
description
descriptionDoc
settings
pages[]
indicators[]
```

保存仍是准备阶段问卷聚合的一次原子提交，不拆成页面、题目和指标各自提交，避免出现“题目已保存但指标绑定未保存”的中间状态。

GET和PUT响应在上述草稿数据之外增加：

```text
isPublishReady: boolean
validationIssues[]: { code, path, message }
```

P4实现并返回后端权威的发布完整性检查结果，前端只负责按`path`定位和展示问题；P5发布服务必须再次调用同一校验器作为硬门禁，不能信任前端传入的`isPublishReady`。

### 5.2 稳定标识、前端键与数据库ID

| 概念 | 规则 |
|---|---|
| `clientKey` | 只在前端编辑态使用，不进入正式API；水合时取对应业务`Code`，新建时立即生成 |
| `pageCode` | 页面稳定业务标识，版本内唯一，P4迁移后持久化 |
| `questionCode` | 题目稳定业务标识，继续版本内唯一 |
| `optionCode` | 单选题内稳定选项标识 |
| `indicatorCode` | 指标稳定业务标识，版本内唯一 |
| `pageId/questionId/optionId/indicatorId` | 后端数据库ID；新建对象传`null`，每次保存后必须用后端响应整体替换本地ID |

复制规则：复制页面、题目、选项或指标时，所有数据库ID清空，所有被复制对象生成新的业务`Code`；移动和排序只改变`sortOrder`，不得改变业务`Code`。

P4继续采用“准备阶段整份草稿替换”策略，因此数据库ID允许在保存后变化。客户端、指标绑定和编辑选择状态只能使用业务`Code/clientKey`关联，不得持有上一次保存的数据库ID作为业务身份。发布完成后，最终一次保存返回的数据库ID随冻结版本固定。

### 5.3 通用题目字段

所有题型使用Pydantic判别联合，判别字段为`questionType`：

```text
questionId: bigint | null
questionCode: string
questionType: QuestionType
title: string
description: string | null
isRequired: boolean
isScored: boolean
minScore: decimal-string | null
maxScore: decimal-string | null
decimalPlaces: 0..4
config: object
sortOrder: integer >= 1
options: QuestionOption[]
```

协议要求：

- 后端模型使用`extra='forbid'`，未知字段和未知题型明确失败。
- 所有正式小数在API中使用不超过4位小数的十进制字符串；前端组件边界可以转成`number`展示，但比较、求和、序列化使用四位定点字符串工具，不能依赖二进制浮点作为正式结果。
- 页面、题目、选项和指标的`sortOrder`保存前规范化为从1开始的连续整数。
- 同一版本内页面、题目和指标业务标识唯一；同一单选题内选项业务标识唯一。

### 5.4 题型判别协议

| 题型 | 答案通道 | 字段与配置 | 后端校验 | 原始满分贡献 |
|---|---|---|---|---|
| `SINGLE_CHOICE` | `OPTION` | 至少2个`options`；`minScore/maxScore=null`；`decimalPlaces=0`；`config={}` | 选项文字非空、业务标识和顺序唯一、分值`>=0` | 参与计分时取最高选项分 |
| `STAR_RATING` | `NUMERIC` | `minScore/maxScore`为整数；跨度`1..10`；无选项 | `0 <= minScore < maxScore`，`decimalPlaces=0` | 参与计分时取`maxScore` |
| `NUMERIC_INPUT` | `NUMERIC` | 区间必填；`decimalPlaces=0..4`；`config.defaultValue`可空 | 默认值在区间内且精度不超限；无选项 | 参与计分时取`maxScore` |
| `SLIDER` | `NUMERIC` | 区间必填；`config.step`和`config.defaultValue`；无选项 | `step>0`且精度不超限，默认值在区间内并落在合法步长上 | 参与计分时取`maxScore` |
| `TEXT` | `TEXT` | `config.maxLength=1..5000`；无选项 | 强制`isScored=false`、`minScore/maxScore=null`、`decimalPlaces=0` | 始终为0 |

星级题使用Element Plus `ElRate`。为同时支持可配置最低分和“未作答不等于0分”，UI星数定义为`maxScore-minScore+1`，实际分值为`minScore+uiStars-1`；未作答在协议中始终为`null`，仅在`ElRate`组件边界映射成0颗星。即使最低分为0，选择第一颗星得到的正式值也是0，仍与未作答`null`不同。

### 5.5 页面和移动规则

- 至少1页，首期每份问卷最多50页；每页最多200题，整份问卷最多500题。
- 页面支持新增、重命名、说明、上移、下移和删除。
- 删除非空页面前必须二次确认；至少保留1页。
- 题目支持页内上移/下移和“移动到页面”选择器；移动后追加到目标页末尾，再允许继续排序。
- P4不引入拖拽依赖。明确按钮和`ElSelect`跨页移动可覆盖键盘、自动化测试和桌面使用；若以后增加拖拽，只能作为同一Store动作的另一个触发入口。
- 展示题号按页面顺序和页内题目顺序动态计算，不持久化“第N题”。

## 6. 指标协议与完整性规则

### 6.1 指标草稿结构

```text
indicatorId: bigint | null
indicatorCode: string
indicatorName: string
description: string | null
weight: decimal-string
sortOrder: integer >= 1
questionCodes: string[]
```

### 6.2 设计约定

- 指标名称和`indicatorCode`在版本内唯一，权重范围为`0.0000..100.0000`。
- 一道题最多绑定一个指标；API用`questionCodes`表达绑定，后端在同一事务内映射成新生成的`question_id`。
- 问答题可以绑定一个指标用于定性归类，但不参与该指标分母或原始满分。
- 允许权重为0的定性指标；发布就绪时全部指标的权重总和必须精确等于`100.0000`。
- 删除仍有绑定题目的指标时明确拒绝，并提示先解除或迁移绑定；不静默删除绑定。

草稿保存和发布完整性使用同一校验模块的两级规则：

- 草稿保存硬校验：业务Code、顺序和引用合法；单题最多绑定一个指标；单项权重范围为`0.0000..100.0000`。结构性错误不得写入数据库。
- 发布完整性检查：指标权重总和精确等于`100.0000`；所有`isScored=true`题目恰好绑定一个指标；权重大于0的指标至少包含一道最高分大于0的计分题，不能只绑定问答题。
- 准备阶段允许保存尚未满足发布完整性的草稿，后端在响应中返回`isPublishReady=false`和稳定的问题码；P5发布时再将这些问题作为拒绝发布的硬门禁。

## 7. 富文本说明方案

### 7.1 设计约定

- 只将“问卷说明”升级为富文本；题目说明在P4继续使用纯文本，避免每道题都引入编辑器实例。
- 使用Tiptap Vue 3集成，计划锁定同一版本的`@tiptap/vue-3`、`@tiptap/pm`和`@tiptap/starter-kit`。2026-09-02预检基准版本为`3.30.2`，实际安装时三包必须使用相同精确版本并写入`package-lock.json`。
- 官方Vue 3安装要求这三个包；官方持久化说明优先推荐JSON而非HTML，因此数据库保存Tiptap JSON，不保存未经控制的任意HTML。
- 编辑器工具栏使用Element Plus按钮，不引入第二套UI框架。
- 只启用段落、二/三级标题、粗体、斜体、下划线、删除线、有序/无序列表、引用、换行和撤销/重做。
- 首期禁用链接、图片、表格、代码块、任意样式和原始HTML。
- 前端预览和只读展示使用相同Tiptap schema，不使用`v-html`渲染用户输入。

官方资料：

- [Tiptap Vue 3安装](https://tiptap.dev/docs/editor/getting-started/install/vue3)
- [Tiptap持久化建议](https://tiptap.dev/docs/editor/core-concepts/persistence)
- [StarterKit扩展清单](https://tiptap.dev/docs/editor/extensions/functionality/starterkit)

### 7.2 后端安全校验

- 根节点必须为`doc`，节点和mark必须属于白名单。
- 纯文本长度不超过5000字符，JSON序列化后不超过100KB，节点总数不超过1000，嵌套深度不超过20。
- 后端从结构化文档提取纯文本写入`description`，不信任前端同时提交的摘要。
- 未知节点、未知属性、脚本、事件、URL和HTML片段全部拒绝，不做静默清洗后保存。

## 8. 前端架构预检

### 8.1 题型注册表

现有注册表扩展为每种题型一个完整定义：

```text
type
label
description
answerType
createDefault()
propertyEditor
renderer
normalize(question)
validate(question)
serialize(question)
calculateMaxScore(question)
clone(question)
```

- 编辑画布、电脑/手机预览和P6答题必须通过同一注册表选择渲染器。
- 未知题型必须阻止保存和预览；不得降级成文本框。
- 复制操作由题型定义重建特有配置和子项业务标识。

### 8.2 Store与组件拆分

`QuestionnaireEditorView.vue`只负责页面编排，P4应拆出：

- `QuestionnaireOutline.vue`：页面、题目选择和移动入口。
- `QuestionTypePanel.vue`：五种题型入口。
- `QuestionPropertiesPanel.vue`：按注册表加载属性组件。
- `IndicatorPanel.vue`：指标、权重和题目绑定。
- `RichTextEditor.vue`：问卷说明编辑和只读schema封装。

Pinia Store统一提供新增、复制、删除、页内移动、跨页移动、指标绑定、规范化、校验、保存和后端响应水合动作。组件不得直接拼装API载荷。

### 8.3 Element Plus交互约束

- 属性表单继续使用`ElForm/ElFormItem`校验。
- 星级、数字、滑动和文本分别使用`ElRate`、`ElInputNumber`、`ElSlider`和`ElInput`的真实组件行为。
- 保存、删除、移动和预览使用明确`@click`/回车处理器；不使用原生表单提交链。
- 保存期间禁用所有结构变更入口，保留防重复提交、错误反馈和锁版本冲突提示。

### 8.4 构建体积门禁

- Tiptap和富文本组件只能由问卷编辑器路由懒加载，不得进入登录、员工工作台或项目列表首屏依赖。
- P4完成时记录构建前后chunk差异；主`index` chunk不得因Tiptap增加。
- 当前大chunk提示是已知非阻塞基线，但P4不得让依赖无界增长。

## 9. 后端分层与保存事务

### 9.1 推荐文件职责

| 层 | 计划文件或变更 | 职责 |
|---|---|---|
| Entity | `questionnaire_do.py` | 增加`description_doc/page_code`模型字段和约束 |
| VO | `questionnaire_question_vo.py` | 五种题型判别联合和题型特有配置 |
| VO | `indicator_vo.py` | 指标和题目业务标识绑定协议 |
| Validator | `validators/questionnaire_validator.py` | 富文本、题型、顺序、满分、指标和权重完整性校验 |
| DAO | `questionnaire_dao.py` | 锁定草稿、整体替换页面/题目/指标/绑定并重新加载 |
| Service | `questionnaire_service.py` | 状态、数据范围、锁版本、事务和响应映射 |
| Controller | `project_controller.py` | 保持现有草稿GET/PUT，不新增平行接口 |

### 9.2 原子保存顺序

```text
锁定项目
→ 校验项目为PREPARING且数据范围匹配
→ 锁定DRAFT问卷版本并校验lockVersion
→ 校验富文本、五种题型、顺序、稳定标识和指标结构
→ 计算发布完整性问题，但不因草稿尚未配完而拒绝保存
→ 删除旧草稿页面（级联题目、选项和旧绑定）
→ 删除旧指标
→ 写入页面、题目和选项并flush，建立Code到数据库ID映射
→ 写入指标并flush
→ 按questionCode建立指标绑定
→ 更新问卷和项目锁版本
→ 单事务commit
→ 从PostgreSQL重新加载完整草稿响应
```

任一步失败必须回滚。DAO不调用`commit`；服务层只在全部结构和映射完成后提交。过期锁版本明确返回冲突，不覆盖其他HR的修改。

## 10. 实施顺序与验证矩阵

### 10.1 推荐实施批次

1. **P4基础改造**：迁移、通用判别DTO、四位定点工具、通用注册表和整体文档保存。
2. **P4-01至P4-04**：依次完成星级、数字、滑动和问答题，每种题型完成后立即补DTO、组件和序列化测试。
3. **P4-05至P4-06**：多页、页面/题目排序、跨页移动、复制删除和稳定标识。
4. **P4-07至P4-08**：指标维护、绑定、权重、原始满分和后端权威校验。
5. **P4-09**：真实PostgreSQL无损恢复、完整题型矩阵和真实浏览器闭环。

### 10.2 必须覆盖的自动化测试

| 层级 | 必测内容 |
|---|---|
| 后端VO | 五种题型有效值、边界值、缺失值、未知字段、错误配置和Decimal精度 |
| 后端Validator | 富文本白名单、顺序、稳定标识、满分；区分草稿结构错误与发布完整性问题；覆盖权重精确100、计分题未绑定和只含问答题指标 |
| PostgreSQL | P4迁移升级/降级/再升级；五题型、多页、跨页、指标和绑定保存后新Session恢复 |
| 并发与权限 | 非准备阶段、冻结版本、过期锁、无权限和数据范围外请求拒绝 |
| 前端注册表 | 每种题型默认值、属性编辑、预览、只读、序列化、复制和未知题型失败 |
| 前端数值 | 未作答与0分、4位小数、步长、默认值、原始满分和权重合计 |
| 前端结构 | 页面增删排序、题目跨页、业务Code稳定、复制生成新Code、保存后ID水合 |
| 浏览器 | 创建含五种题型和两个页面的问卷，配置指标，保存，整页刷新恢复；覆盖滑动题键盘操作和电脑/手机预览，且预览不写答案 |

### 10.3 阶段门禁命令

P4实现完成时至少执行：

```powershell
cd ruoyi-fastapi-backend
python -m alembic -c alembic.ini upgrade head
python scripts\feedback_p2_schema_verify.py --database ruoyi_feedback_test
python scripts\feedback_p2_schema_verify.py --database ruoyi_feedback_test --designer-migration-cycle --yes
$env:RUN_FEEDBACK_POSTGRES_TESTS='1'; python -m pytest tests\module_feedback
python -m ruff check module_feedback scripts\feedback_p2_schema_verify.py tests\module_feedback
python -m ruff format --check module_feedback scripts\feedback_p2_schema_verify.py tests\module_feedback

cd ..\feedback-frontend
npm test
npm run build
npm run test:e2e
```

结构验证脚本应在P4实现时扩展为识别新revision、`description_doc/page_code`和新增中文注释，不能继续以P2字段数量作为P4完成证据。

## 11. 风险与处置

| 风险 | 处置 |
|---|---|
| JavaScript浮点误差导致满分或权重判断漂移 | API传十进制字符串；前端用四位定点整数工具；后端使用`Decimal`，最终以后端校验为准 |
| 整体替换导致数据库ID变化 | 业务关联只使用Code；保存后整体水合后端响应；发布冻结前禁止生成正式答卷 |
| 页面没有稳定身份 | 先执行`page_code`迁移，再开放多页编辑 |
| 富文本注入或协议漂移 | 保存JSON、节点白名单、后端限额、相同schema只读渲染，不使用任意HTML |
| 指标与题目替换后错绑 | 绑定请求只传questionCode，后端flush后按Code映射数据库ID，并在同一事务提交 |
| 发布校验过早导致半成品草稿无法保存 | 保存只硬拒绝结构错误；响应返回发布问题；P5复用同一后端校验器执行发布硬门禁 |
| 排序唯一约束冲突 | 草稿整体替换后按连续顺序写入，不对相邻行直接交换唯一序号 |
| 新编辑器依赖扩大首屏 | 路由级懒加载并记录chunk差异，Tiptap不得进入主chunk |
| P4越界到发布或答题 | 只保存DRAFT配置；不生成任务、答卷或答案 |

## 12. 开工结论与实现复核

### 已验证

- P3垂直切片、锁版本、真实PostgreSQL保存恢复和共享渲染入口可作为P4基线。
- P2已有五种题型枚举、区间分数字段、题型JSON配置、指标表、唯一绑定和三种答案通道。
- 开始本次文档工作前，工作区已有用户自己的`ruoyi-fastapi-backend/.env.dev`修改；本次工作不覆盖它。
- P4增量迁移、五题型判别联合、多页稳定Code、受限Tiptap JSON、指标绑定和两级校验已按本文协议实现。
- 测试库有数据迁移往返、真实PostgreSQL新Session恢复、前端32项测试、Playwright 4项回归和真实浏览器全链路均已通过。
- 真实浏览器预览后答卷和答案记录均为0，P4没有越界生成P5任务或P6答题数据。

### 设计约定

- P4先交付一条增量迁移和通用协议，再开发四种新增题型。
- 保持单一草稿聚合API、服务层事务、数据范围和锁版本；不新增平行后端或前端状态体系。
- 采用稳定业务Code关联、保存后数据库ID整体水合、发布后冻结的生命周期。
- 发布就绪时指标权重精确等于`100.0000`，所有计分题必须绑定指标，问答题只作定性归类；未配完的准备阶段草稿仍允许保存并返回问题清单。

### 推荐方案

- 第一实现批次从“迁移 + 判别联合DTO + 注册表接口 + 定点数工具”开始，不直接先写四个孤立页面组件。
- 每完成一种题型就补齐编辑、预览、只读、序列化和边界测试，最后再组合多页与指标闭环。

### 待确认事项

- 当前无P4遗留阻塞项；下一阶段需要单独收口P5人员快照、关系配置、发布事务和任务生成协议。
- 若需要富文本链接、图片、表格、拖拽排序、模板或导出，属于产品范围变化，必须先更新产品基线和MVP范围，不能在P4实现中顺带加入。
