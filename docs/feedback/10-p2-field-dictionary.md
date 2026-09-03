# P2领域表与P4/P5/P6增量字段字典

## 1. 文档状态

本文登记领域表及P4/P5/P6增量字段契约。P6新增`20260902_05_feedback_answering`（答卷总分容量）与`20260902_06_feedback_permissions`（授权项），前序迁移保持不变。字段类型、可空性、默认值、外键、唯一约束和中文说明以本文、迁移和SQLAlchemy实体三者一致为验收标准；业务完成状态以路线图验收记录为准。

P2 只建立领域持久化骨架，不代表项目、问卷、发布、答题、计分或报告 API 已经实现。

## 2. ER关系

```text
fb_project
  └─< fb_questionnaire_version
       ├─< fb_questionnaire_page ─< fb_question ─< fb_question_option
       ├─< fb_indicator ─< fb_indicator_question >─ fb_question
       ├─< fb_relation
       └─< fb_project_target
              ├─< fb_evaluator_selection >─ fb_relation
              └─< fb_assignment >─ fb_relation
                     └─1 fb_answer_sheet ─< fb_answer

fb_score_result
  ├─> fb_project_target
  ├─> fb_indicator（按结果粒度可空）
  └─> fb_relation（按结果粒度可空）
```

所有用户、部门引用继续复用 `sys_user.user_id` 和 `sys_dept.dept_id`，不建立平行员工表。

## 3. 通用字段约定

下列表使用统一审计字段：`fb_project`、`fb_questionnaire_version`、`fb_questionnaire_page`、`fb_question`、`fb_question_option`、`fb_indicator`、`fb_relation`、`fb_project_target`、`fb_evaluator_selection`。

| 字段 | PostgreSQL类型 | 可空 | 默认/约束 | 中文说明 |
|---|---|---|---|---|
| `create_by` | `VARCHAR(64)` | 否 | `''` | 创建者 |
| `create_time` | `TIMESTAMP WITHOUT TIME ZONE` | 否 | `CURRENT_TIMESTAMP` | 创建时间 |
| `update_by` | `VARCHAR(64)` | 否 | `''` | 更新者 |
| `update_time` | `TIMESTAMP WITHOUT TIME ZONE` | 否 | `CURRENT_TIMESTAMP` | 更新时间 |
| `remark` | `VARCHAR(500)` | 是 | 无 | 备注 |

配置类聚合根和并发写入对象使用 `lock_version INTEGER NOT NULL DEFAULT 0`，并由检查约束保证不小于0。

## 4. 项目与问卷配置

### 4.1 `fb_project` 评价项目表

另含第3节统一审计字段。

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `project_id` | `BIGINT` | 否 | 自增主键 | 评价项目ID |
| `project_name` | `VARCHAR(200)` | 否 | 无 | 评价项目名称 |
| `description` | `TEXT` | 是 | 无 | 评价项目说明 |
| `status` | `VARCHAR(20)` | 否 | `PREPARING`；仅允许`PREPARING/ACTIVE/COMPLETED` | 项目状态 |
| `owner_user_id` | `BIGINT` | 否 | FK `sys_user.user_id`，删除受限 | 项目负责人用户ID |
| `owner_dept_id` | `BIGINT` | 是 | FK `sys_dept.dept_id`，删除受限 | 项目归属部门ID |
| `current_questionnaire_version_id` | `BIGINT` | 是 | FK `fb_questionnaire_version.version_id`，发布后必填 | 当前问卷版本ID |
| `published_by` | `BIGINT` | 是 | FK `sys_user.user_id`，进行中/已完成必填 | 发布人用户ID |
| `published_time` | `TIMESTAMP` | 是 | 进行中/已完成必填 | 发布时间 |
| `completed_by` | `BIGINT` | 是 | FK `sys_user.user_id`，已完成必填 | 完成人用户ID |
| `completed_time` | `TIMESTAMP` | 是 | 已完成必填 | 完成时间 |
| `completion_reason` | `VARCHAR(500)` | 是 | 无 | 手动完成原因 |
| `del_flag` | `VARCHAR(1)` | 否 | `0`；仅允许`0/2` | 准备阶段项目草稿删除标志 |
| `lock_version` | `INTEGER` | 否 | `0`，且`>= 0` | 乐观锁版本 |

索引：`(status, create_time)`、`(owner_user_id, owner_dept_id)`。

### 4.2 `fb_questionnaire_version` 问卷版本表

另含第3节统一审计字段。

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `version_id` | `BIGINT` | 否 | 自增主键 | 问卷版本ID |
| `project_id` | `BIGINT` | 否 | FK `fb_project.project_id`；与`version_no`唯一 | 评价项目ID |
| `version_no` | `INTEGER` | 否 | `> 0` | 项目内版本号 |
| `status` | `VARCHAR(20)` | 否 | `DRAFT`；仅允许`DRAFT/FROZEN` | 问卷版本状态 |
| `title` | `VARCHAR(200)` | 否 | 无 | 问卷标题 |
| `description` | `TEXT` | 是 | 无 | 问卷说明 |
| `description_doc` | `JSONB` | 是 | P4新增；受限Tiptap文档或空 | 问卷富文本说明文档 |
| `settings` | `JSONB` | 否 | `{}` | 问卷全局设置 |
| `scoring_rule_snapshot` | `JSONB` | 否 | `{}` | 计分规则快照 |
| `frozen_by` | `BIGINT` | 是 | FK `sys_user.user_id`；冻结状态必填 | 冻结人用户ID |
| `frozen_time` | `TIMESTAMP` | 是 | 冻结状态必填 | 冻结时间 |
| `lock_version` | `INTEGER` | 否 | `0`，且`>= 0` | 乐观锁版本 |

唯一性：`(project_id, version_no)`；每个项目通过部分唯一索引最多存在一个`DRAFT`版本。

### 4.3 `fb_questionnaire_page` 问卷页面表

另含第3节统一审计字段。

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `page_id` | `BIGINT` | 否 | 自增主键 | 问卷页面ID |
| `version_id` | `BIGINT` | 否 | FK `fb_questionnaire_version.version_id` | 问卷版本ID |
| `page_code` | `VARCHAR(64)` | 否 | P4新增；版本内唯一 | 版本内稳定页面标识 |
| `page_title` | `VARCHAR(200)` | 否 | 无 | 页面标题 |
| `page_description` | `TEXT` | 是 | 无 | 页面说明 |
| `sort_order` | `INTEGER` | 否 | `> 0`；版本内唯一 | 页面顺序 |

### 4.4 `fb_question` 问卷题目表

另含第3节统一审计字段。

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `question_id` | `BIGINT` | 否 | 自增主键 | 题目ID |
| `version_id` | `BIGINT` | 否 | 与`page_id`组成复合FK | 问卷版本ID |
| `page_id` | `BIGINT` | 否 | FK同版本`fb_questionnaire_page` | 问卷页面ID |
| `question_code` | `VARCHAR(64)` | 否 | 版本内唯一 | 版本内稳定题目标识 |
| `question_type` | `VARCHAR(30)` | 否 | 首期五种题型枚举 | 题型 |
| `title` | `TEXT` | 否 | 无 | 题目标题 |
| `description` | `TEXT` | 是 | 无 | 题目说明 |
| `is_required` | `BOOLEAN` | 否 | `false` | 是否必答 |
| `is_scored` | `BOOLEAN` | 否 | `true`；问答题必须为`false` | 是否参与计分 |
| `min_score` | `NUMERIC(12,4)` | 是 | 三种区间评分题必填 | 最低分 |
| `max_score` | `NUMERIC(12,4)` | 是 | 三种区间评分题必填且大于最低分 | 最高分 |
| `decimal_places` | `SMALLINT` | 否 | `0`；范围`0..4` | 允许小数位数 |
| `config` | `JSONB` | 否 | `{}` | 题型特有配置 |
| `sort_order` | `INTEGER` | 否 | `> 0`；页面内唯一 | 页内题目顺序 |

题型仅允许：`SINGLE_CHOICE`、`STAR_RATING`、`NUMERIC_INPUT`、`SLIDER`、`TEXT`。索引：`(version_id, question_type)`。

### 4.5 `fb_question_option` 题目选项表

另含第3节统一审计字段。

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `option_id` | `BIGINT` | 否 | 自增主键 | 题目选项ID |
| `question_id` | `BIGINT` | 否 | FK `fb_question.question_id` | 题目ID |
| `option_code` | `VARCHAR(64)` | 否 | 题目内唯一 | 题目内稳定选项标识 |
| `option_label` | `VARCHAR(500)` | 否 | 无 | 选项文本 |
| `score` | `NUMERIC(12,4)` | 否 | `0` | 选项原始分 |
| `requires_reason` | `BOOLEAN` | 否 | `false` | 是否要求附加原因 |
| `sort_order` | `INTEGER` | 否 | `> 0`；题目内唯一 | 选项顺序 |

### 4.6 `fb_indicator` 评价指标表

另含第3节统一审计字段。

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `indicator_id` | `BIGINT` | 否 | 自增主键 | 指标ID |
| `version_id` | `BIGINT` | 否 | FK `fb_questionnaire_version.version_id` | 问卷版本ID |
| `indicator_code` | `VARCHAR(64)` | 否 | 版本内唯一 | 版本内稳定指标标识 |
| `indicator_name` | `VARCHAR(100)` | 否 | 版本内唯一 | 指标名称 |
| `description` | `TEXT` | 是 | 无 | 指标说明 |
| `weight` | `NUMERIC(12,4)` | 否 | `0..100` | 指标权重百分比 |
| `sort_order` | `INTEGER` | 否 | `> 0`；版本内唯一 | 指标顺序 |

### 4.7 `fb_indicator_question` 指标题目绑定表

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `binding_id` | `BIGINT` | 否 | 自增主键 | 指标题目绑定ID |
| `version_id` | `BIGINT` | 否 | 同时参与指标和题目复合FK | 问卷版本ID |
| `indicator_id` | `BIGINT` | 否 | FK同版本`fb_indicator` | 指标ID |
| `question_id` | `BIGINT` | 否 | FK同版本`fb_question`；全表唯一 | 题目ID |

`question_id`唯一保证首期一道计分题最多绑定一个指标。

## 5. 关系、人员与任务

### 5.1 `fb_relation` 项目评价关系表

另含第3节统一审计字段。

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `relation_id` | `BIGINT` | 否 | 自增主键 | 评价关系ID |
| `project_id` | `BIGINT` | 否 | 与`version_id`组成版本复合FK | 评价项目ID |
| `version_id` | `BIGINT` | 否 | FK同项目问卷版本 | 问卷版本ID |
| `relation_code` | `VARCHAR(64)` | 否 | 版本内唯一 | 版本内稳定关系标识 |
| `relation_type` | `VARCHAR(20)` | 否 | 六种关系枚举 | 评价关系类型 |
| `relation_name` | `VARCHAR(100)` | 否 | 版本内唯一 | 评价关系名称 |
| `is_enabled` | `BOOLEAN` | 否 | `true` | 是否启用 |
| `participates_in_score` | `BOOLEAN` | 否 | `true` | 是否参与综合计分 |
| `weight` | `NUMERIC(12,4)` | 否 | `0`；范围`0..100`；自评必须为0 | 关系配置权重百分比 |
| `sort_order` | `INTEGER` | 否 | `> 0`；版本内唯一 | 关系顺序 |

关系类型仅允许：`SUPERVISOR`、`PEER`、`SUBORDINATE`、`SELF`、`OTHER`、`CUSTOM`。

### 5.2 `fb_project_target` 项目被评价人快照表

另含第3节统一审计字段。

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `target_id` | `BIGINT` | 否 | 自增主键 | 项目被评价人记录ID |
| `project_id` | `BIGINT` | 否 | FK `fb_project.project_id` | 评价项目ID |
| `version_id` | `BIGINT` | 否 | FK同项目问卷版本 | 问卷版本ID |
| `target_user_id` | `BIGINT` | 否 | FK `sys_user.user_id`；项目内唯一 | 被评价人用户ID |
| `target_user_name` | `VARCHAR(100)` | 否 | 发布时冻结 | 被评价人姓名快照 |
| `target_dept_id` | `BIGINT` | 是 | FK `sys_dept.dept_id` | 被评价人部门ID快照 |
| `target_dept_name` | `VARCHAR(100)` | 是 | 发布时冻结 | 被评价人部门名称快照 |
| `only_self_evaluation` | `BOOLEAN` | 否 | `false` | 发布时是否仅配置自评 |

索引：`(project_id, target_dept_id)`，供后续RuoYi数据范围查询使用。

### 5.3 `fb_assignment` 评价任务表

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `assignment_id` | `BIGINT` | 否 | 自增主键 | 评价任务ID |
| `project_id` | `BIGINT` | 否 | FK `fb_project.project_id` | 评价项目ID |
| `version_id` | `BIGINT` | 否 | 与关系、被评价人快照保持同版本 | 问卷版本ID |
| `evaluator_user_id` | `BIGINT` | 否 | FK `sys_user.user_id` | 评价人用户ID |
| `evaluator_user_name` | `VARCHAR(100)` | 否 | 发布时冻结 | 评价人姓名快照 |
| `evaluator_dept_id` | `BIGINT` | 是 | FK `sys_dept.dept_id` | 评价人部门ID快照 |
| `evaluator_dept_name` | `VARCHAR(100)` | 是 | 发布时冻结 | 评价人部门名称快照 |
| `target_id` | `BIGINT` | 否 | 复合FK `fb_project_target` | 项目被评价人记录ID |
| `target_user_id` | `BIGINT` | 否 | FK `sys_user.user_id` | 被评价人用户ID |
| `relation_id` | `BIGINT` | 否 | 复合FK同项目版本`fb_relation` | 评价关系ID |
| `status` | `VARCHAR(20)` | 否 | `PENDING`；任务状态枚举 | 评价任务状态 |
| `saved_time` | `TIMESTAMP` | 是 | `DRAFT`时必填 | 最近暂存时间 |
| `submitted_time` | `TIMESTAMP` | 是 | `SUBMITTED`时必填 | 正式提交时间 |
| `closed_time` | `TIMESTAMP` | 是 | `CLOSED_INCOMPLETE`时必填 | 关闭未完成时间 |
| `lock_version` | `INTEGER` | 否 | `0`，且`>= 0` | 乐观锁版本 |
| `create_time` | `TIMESTAMP` | 否 | `CURRENT_TIMESTAMP` | 创建时间 |
| `update_time` | `TIMESTAMP` | 否 | `CURRENT_TIMESTAMP` | 更新时间 |

业务唯一键：`(project_id, evaluator_user_id, target_user_id, relation_id)`。索引：评价人/状态、被评价人/状态、项目/状态。

## 6. 答卷、答案与计分结果

### 6.1 `fb_answer_sheet` 评价答卷表

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `sheet_id` | `BIGINT` | 否 | 自增主键 | 答卷ID |
| `assignment_id` | `BIGINT` | 否 | 复合FK `fb_assignment`；唯一 | 评价任务ID |
| `project_id` | `BIGINT` | 否 | 与任务一致 | 评价项目ID |
| `version_id` | `BIGINT` | 否 | 与任务一致 | 问卷版本ID |
| `status` | `VARCHAR(20)` | 否 | `DRAFT`；仅允许`DRAFT/SUBMITTED` | 答卷状态 |
| `last_page_id` | `BIGINT` | 是 | FK `fb_questionnaire_page.page_id` | 最近填写页面ID |
| `answered_count` | `INTEGER` | 否 | `0`，且`>= 0` | 已作答题目数量 |
| `raw_total_score` | `NUMERIC(18,4)` | 是 | P6扩容；未提交为空 | 答卷原始总分 |
| `submission_snapshot` | `JSONB` | 否 | `{}` | 提交时校验与计分输入快照 |
| `saved_time` | `TIMESTAMP` | 否 | `CURRENT_TIMESTAMP` | 最近保存时间 |
| `submitted_time` | `TIMESTAMP` | 是 | `SUBMITTED`时必填 | 正式提交时间 |
| `lock_version` | `INTEGER` | 否 | `0`，且`>= 0` | 乐观锁版本 |
| `create_time` | `TIMESTAMP` | 否 | `CURRENT_TIMESTAMP` | 创建时间 |
| `update_time` | `TIMESTAMP` | 否 | `CURRENT_TIMESTAMP` | 更新时间 |

该表没有`del_flag`。索引：`(project_id, submitted_time)`。

### 6.2 `fb_answer` 评价单题答案表

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `answer_id` | `BIGINT` | 否 | 自增主键 | 单题答案ID |
| `sheet_id` | `BIGINT` | 否 | 复合FK同版本`fb_answer_sheet` | 答卷ID |
| `version_id` | `BIGINT` | 否 | 与答卷、题目一致 | 问卷版本ID |
| `question_id` | `BIGINT` | 否 | 复合FK同版本`fb_question` | 题目ID |
| `answer_type` | `VARCHAR(20)` | 否 | `OPTION/NUMERIC/TEXT`三选一 | 答案值类型 |
| `option_id` | `BIGINT` | 是 | 选项答案时必填，且必须属于当前题目 | 所选选项ID |
| `numeric_value` | `NUMERIC(12,4)` | 是 | 数值答案时必填 | 数值答案 |
| `text_value` | `TEXT` | 是 | 文本答案时必填 | 文本答案 |
| `reason` | `TEXT` | 是 | 与主答案同记录保存 | 选项附加原因 |
| `raw_score` | `NUMERIC(12,4)` | 是 | 问答题可空 | 题目原始得分 |
| `value_snapshot` | `JSONB` | 否 | `{}` | 答案展示值快照 |
| `create_time` | `TIMESTAMP` | 否 | `CURRENT_TIMESTAMP` | 创建时间 |
| `update_time` | `TIMESTAMP` | 否 | `CURRENT_TIMESTAMP` | 更新时间 |

业务唯一键：`(sheet_id, question_id)`。检查约束保证三种值通道恰好使用一个。该表没有`del_flag`。

### 6.3 `fb_score_result` 评价计分结果表

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `result_id` | `BIGINT` | 否 | 自增主键 | 计分结果ID |
| `project_id` | `BIGINT` | 否 | FK `fb_project.project_id` | 评价项目ID |
| `version_id` | `BIGINT` | 否 | 与被评价人、指标、关系保持同版本 | 问卷版本ID |
| `target_id` | `BIGINT` | 否 | 复合FK `fb_project_target` | 项目被评价人记录ID |
| `target_user_id` | `BIGINT` | 否 | FK `sys_user.user_id` | 被评价人用户ID |
| `result_type` | `VARCHAR(30)` | 否 | 四种结果粒度枚举 | 计分结果类型 |
| `indicator_id` | `BIGINT` | 是 | 指标粒度结果必填 | 指标ID |
| `relation_id` | `BIGINT` | 是 | 指标关系结果必填 | 评价关系ID |
| `score` | `NUMERIC` | 是 | P8保留计算精度；`0..100`，数据不足时为空 | 百分制得分 |
| `original_weight` | `NUMERIC(12,4)` | 是 | `0..100` | 发布快照中的原配置权重 |
| `effective_weight` | `NUMERIC` | 是 | P8保留归一化精度；`0..100` | 实际参与计算权重 |
| `expected_count` | `INTEGER` | 否 | `0`，且`>= 0` | 应完成任务数 |
| `submitted_count` | `INTEGER` | 否 | `0`，且不大于应完成数 | 已提交任务数 |
| `has_missing_data` | `BOOLEAN` | 否 | `false` | 是否存在缺失数据 |
| `calculation_version` | `VARCHAR(32)` | 否 | 无 | 计分规则版本 |
| `calculation_basis` | `JSONB` | 否 | 无 | 可复算的计分输入与过程依据 |
| `calculated_time` | `TIMESTAMP` | 否 | `CURRENT_TIMESTAMP` | 计算时间 |
| `create_time` | `TIMESTAMP` | 否 | `CURRENT_TIMESTAMP` | 创建时间 |

结果类型：`INDICATOR_RELATION`、`INDICATOR_COMPOSITE`、`PERSON_TOTAL`、`COVERAGE`。三个部分唯一索引分别保护关系指标、综合指标和个人/覆盖率结果。该表没有`del_flag`，得分允许为空以表达“数据不足”，不得用0替代缺失。

## 7. 状态和枚举对应

| 枚举 | 持久化值 |
|---|---|
| 项目状态 | `PREPARING`、`ACTIVE`、`COMPLETED` |
| 问卷版本状态 | `DRAFT`、`FROZEN` |
| 任务状态 | `PENDING`、`DRAFT`、`SUBMITTED`、`CLOSED_INCOMPLETE` |
| 答卷状态 | `DRAFT`、`SUBMITTED` |
| 题型 | `SINGLE_CHOICE`、`STAR_RATING`、`NUMERIC_INPUT`、`SLIDER`、`TEXT` |
| 答案值类型 | `OPTION`、`NUMERIC`、`TEXT` |
| 关系类型 | `SUPERVISOR`、`PEER`、`SUBORDINATE`、`SELF`、`OTHER`、`CUSTOM` |
| 结果类型 | `INDICATOR_RELATION`、`INDICATOR_COMPOSITE`、`PERSON_TOTAL`、`COVERAGE` |

数据库使用`VARCHAR + CHECK`，代码统一使用`module_feedback.enums`，不使用PostgreSQL原生ENUM。

## 8. 领域规则对应关系

| 领域要求 | 数据结构证据 |
|---|---|
| 发布冻结问卷和计分规则 | `fb_questionnaire_version.status/frozen_by/frozen_time/scoring_rule_snapshot` |
| 人员历史展示不受改名调岗影响 | `fb_project_target`及`fb_assignment`姓名、部门快照字段 |
| 任务业务唯一键 | `uq_fb_assignment_business_key` |
| 逐人一份答卷 | `fb_answer_sheet.assignment_id`唯一 |
| 单题答案唯一 | `uq_fb_answer_sheet_question` |
| 提交数据不可软删除 | `fb_answer_sheet`、`fb_answer`、`fb_score_result`均无`del_flag` |
| 正式分数不用浮点数 | 单题分数/权重为`NUMERIC(12,4)`，答卷原始总分为`NUMERIC(18,4)` |
| 缺失关系不能当0分 | `score`可空，另有`has_missing_data`、任务计数和原/实际权重 |
| 计分可复算 | `calculation_version`、`calculation_basis`、冻结版本和答卷快照 |

状态的合法转换由服务层 `FeedbackStateTransitionService` 维护；数据库检查约束负责拒绝未知状态和缺失终态时间，两层职责不能相互替代。

## 9. P4问卷设计器增量契约

### 9.1 迁移与兼容

- revision `20260902_03_feedback_designer`只为既有问卷版本增加`description_doc`，为既有页面增加`page_code`及唯一约束，不创建平行问卷表。
- 既有页面升级时按`P_<page_id>`确定性回填`page_code`；`description_doc`保持可空，`description`继续保存后端从富文本文档提取的纯文本摘要。
- 测试库已完成带既有页面的P3→P4→P3→P4往返，两次均回填相同页面标识，页面记录未丢失。

### 9.2 题型JSON配置

| 题型 | `config`结构 | 分数/选项约束 |
|---|---|---|
| `SINGLE_CHOICE` | `{}` | 仅此题型持久化两个及以上`fb_question_option`；选项分值为`NUMERIC(12,4)` |
| `STAR_RATING` | `{}` | 整数区间，星数为2至10；不创建伪选项 |
| `NUMERIC_INPUT` | `{"defaultValue": Decimal或null}` | 默认值在区间内且精度不超过`decimal_places` |
| `SLIDER` | `{"step": Decimal, "defaultValue": Decimal或null}` | 步长为正且不大于区间，默认值必须落在合法步长上 |
| `TEXT` | `{"maxLength": 1..5000}` | `is_scored=false`，无分数区间且不创建伪选项 |

指标继续使用`fb_indicator`和`fb_indicator_question`：接口以稳定`indicatorCode/questionCode`表达绑定，保存事务在数据库ID水合后写入关系；首期发布就绪要求指标权重精确合计`100.0000`，每道计分题恰好绑定一个指标。问答题可以归类到指标，但不参与原始满分。

## 10. P5-00发布配置已实现增量契约

### 10.1 实现状态

- 已实现revision：`20260902_04_feedback_publication`。
- `down_revision`：`20260902_03_feedback_designer`。
- 当前状态：迁移、实体、固定关系、人员聚合接口和发布事务均已实现；P5完整门禁见路线图。
- 目标：分离“发布前可编辑的评价人选择”和“发布后员工正式任务”，不提前向`fb_assignment`写任务占位记录。

### 10.2 `fb_evaluator_selection`评价人选择配置表

另含第3节统一审计字段，不含软删除和独立锁版本。

| 字段 | PostgreSQL类型 | 可空 | 默认/关系/约束 | 中文说明 |
|---|---|---|---|---|
| `selection_id` | `BIGINT` | 否 | 自增主键 | 评价人选择配置ID |
| `project_id` | `BIGINT` | 否 | FK `fb_project.project_id` | 评价项目ID |
| `version_id` | `BIGINT` | 否 | 与目标、关系组成同版本复合FK | 问卷版本ID |
| `target_id` | `BIGINT` | 否 | 复合FK `fb_project_target` | 项目被评价人记录ID |
| `target_user_id` | `BIGINT` | 否 | FK `sys_user.user_id`；与目标复合FK一致 | 被评价人用户ID |
| `relation_id` | `BIGINT` | 否 | 复合FK `fb_relation` | 评价关系ID |
| `evaluator_user_id` | `BIGINT` | 否 | FK `sys_user.user_id` | 评价人用户ID |

业务唯一键：`(project_id, evaluator_user_id, target_user_id, relation_id)`，约束名`uq_fb_evaluator_selection_business_key`，与`fb_assignment`正式任务业务键一致。

索引：

- `ix_fb_evaluator_selection_project_version(project_id, version_id)`，用于聚合恢复和发布物化。
- `ix_fb_evaluator_selection_evaluator_project(evaluator_user_id, project_id)`，用于按评价人复核计划来源。

目标或关系在准备期被删除时，选择配置通过复合外键级联清理；正式任务仍使用`RESTRICT`保护历史数据。服务层只允许`DRAFT/PREPARING`聚合替换，版本冻结后不得修改选择配置。

### 10.3 P5快照与发布对应

| 领域要求 | 数据结构证据 |
|---|---|
| 准备期选择可恢复 | `fb_evaluator_selection`保存项目、版本、目标、关系和评价人ID |
| 发布前不制造正式待办 | 准备期只写选择表，`fb_assignment`在发布事务内首次物化 |
| 自评不可伪造 | 服务层按每个`fb_project_target`派生`REL_SELF`选择，客户端不提交自评选择 |
| 发布时人员快照 | 事务内从有效`sys_user/sys_dept`刷新`fb_project_target`和`fb_assignment`姓名/部门字段 |
| 发布规则可复算 | 关系、目标、选择和任务与同一`version_id`关联，`scoring_rule_snapshot`记录规则版本和权重 |
| 发布后不可覆盖 | 项目`ACTIVE`且版本`FROZEN`后，所有配置写服务拒绝修改 |

结构验证器已从13张表、184个字段升级为14张表、196个字段；所有新增表、字段、约束和索引均有中文注释或稳定名称并与SQLAlchemy模型一致。完整API、默认关系、数据范围、锁顺序和门禁见[P5技术预检](./12-p5-publication-precheck.md)。

## 11. P6答卷与权限增量契约

- `20260902_05_feedback_answering`只扩容原始总分，不新增答卷表。降级前加表锁并检查所有值能否恢复到`NUMERIC(12,4)`，无法表示时拒绝降级，不截断分数。
- 草稿完整替换当前任务答案；`lock_version`每次成功写入递增，`last_page_id/saved_time`用于恢复。未作答不落一条伪零值答案。
- 提交原子保存答案、原始分、状态和时间；`submission_snapshot`保存`schemaVersion/submissionId/answerDigest/versionId/evaluatorUserId/targetUserId/relationId/scoringRule/questionScores`。只有规范化内容和幂等键同时相同的重试可返回已有提交。
- `fb_answer.value_snapshot`冻结题目Code/题型/标题、所选选项Code/文案；原始文本与原因保留在独立字段。正式答卷、答案和依据不能删除或覆盖。
- `20260902_06_feedback_permissions`仅在既有`sys_menu`登记15项`feedback:*`权限，不创建平行身份体系、不自动授予任何角色。既有同名权限不变；降级只删除本迁移标记的菜单，若已授予角色则拒绝删除。
- P6验收时结构门禁为14张领域表、196个字段/中文注释、10项`NUMERIC(12,4)`和1项`NUMERIC(18,4)`。完整接口与并发协议见[P6技术预检](./13-p6-answering-precheck.md)。

## 12. P7至P8当前结构增量

- P7新增不可变完成审计表`fb_project_completion_audit`，字段和保护性降级契约见[P7技术预检](./14-p7-progress-completion-precheck.md)。
- P8迁移`20260903_08_feedback_scoring`将`fb_score_result.score/effective_weight`改为不限定小数位的`NUMERIC`；原始题分、原权重和配置精度保持四位小数。降级先锁表，存在无法恢复为四位小数的值时拒绝降级。
- P8双独立库当前结构门禁为15张领域表、213个字段/中文注释、8项`NUMERIC(12,4)`、1项`NUMERIC(18,4)`和2项不限定小数位的`NUMERIC`，16项关键约束和12项关键索引。
- 结果按`calculation_version=feedback-score-v1`保存，`calculation_basis`记录冻结输入、提交答卷集合和精确中间值；后端只在对外展示时舍入两位小数。具体结构、对账和当前配置库限制见[P8实施契约](./15-p8-scoring-reports-precheck.md)。
