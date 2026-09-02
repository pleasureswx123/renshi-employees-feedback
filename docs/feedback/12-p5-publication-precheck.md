# P5人员关系、发布冻结与任务生成决策收口与技术预检

## 1. 文档状态

- 预检日期：2026-09-02。
- 适用阶段：P5“人员关系、发布冻结与任务生成”。
- 基线提交：`da9b53c feat: 完成评价平台P4完整问卷设计器与指标`。
- 预检结论：**允许进入P5实现；必须先完成发布前评价人选择配置表及默认关系迁移，再实现聚合配置、事务化发布和只读复核。**
- 实现状态：**P5-00至P5-08已全部实现并通过真实PostgreSQL、真实浏览器及前后端自动化门禁；允许进入P6员工逐人答题链路。**

结论分类：

- “已验证”表示已经由当前代码、数据库结构或P4阶段门禁确认。
- “设计约定”表示P5实现必须遵循的已收口方案。
- “推荐顺序”表示不改变产品边界的落地次序。
- “待确认事项”只保留会改变首期产品范围的内容；当前没有阻塞P5开工的待确认项。

## 2. 阶段范围与非目标

### 2.1 P5必须形成的闭环

```text
HR选择被评价人
  -> 配置项目内评价关系及权重
  -> 按被评价人和关系选择评价人
  -> 后端保存可恢复的准备期配置并返回任务预览
  -> 后端组合校验问卷、指标、人员、关系和任务计划
  -> HR二次确认发布
  -> 单事务刷新人员快照、冻结版本、生成任务、切换项目状态
  -> 刷新后只能查看冻结配置，真实任务数与预览一致
```

### 2.2 P5不扩大首期范围

- 不自动推断上级、同级或下级，只自动建立“自己”评价。
- 不新增员工、部门、角色、登录或权限体系，继续复用RuoYi的`sys_user`、`sys_dept`、认证、菜单权限和数据范围。
- 不实现模板、Excel导入、公开链接、二维码、小程序、邮件、短信或自动完成。
- 不实现答卷暂存、正式提交和“我评价的”；这些仍属于P6。
- 不实现HR回收进度和手动完成；这些仍属于P7。
- 不实现正式计分和报告；P5只冻结P8计算所需的规则和数据依据。
- 不把前端任务预览当作发布依据；发布任务集合必须由后端根据已保存配置重新生成。

### 2.3 P5与P6的验收边界

- P5负责生成`fb_assignment`真实任务，并用真实PostgreSQL证明按评价人可以查询到这些任务。
- P5浏览器验收覆盖HR配置、预览、发布和发布后只读；同时由测试进程核对数据库任务行。
- P6-01再把当前评价人的任务查询封装为员工“我的待办”正式API，P6-02实现员工待办页面。P5不得用占位页面或Mock任务冒充员工待办已经完成。

## 3. 当前基线核验

### 3.1 已验证能力

| 能力 | 当前证据 | P5结论 |
|---|---|---|
| 项目状态与发布字段 | `fb_project`已有`PREPARING/ACTIVE/COMPLETED`、当前版本、发布人、发布时间和锁版本约束 | 不新增平行发布状态；发布后进入`ACTIVE` |
| 问卷冻结 | `fb_questionnaire_version`已有`DRAFT/FROZEN`、冻结人、冻结时间、`scoring_rule_snapshot`和锁版本 | 直接冻结当前草稿版本，不复制第二套问卷表 |
| 关系配置 | `fb_relation`已有关系类型、稳定Code、启停、是否计分、`NUMERIC(12,4)`权重和版本复合外键 | 准备期编辑，发布时随版本原地冻结 |
| 被评价人快照 | `fb_project_target`已有用户、姓名、部门和仅自评字段 | 准备期保存临时展示值，发布事务内从RuoYi数据重新刷新 |
| 正式任务 | `fb_assignment`已有业务唯一键、人员快照、状态、锁版本和查询索引 | 只在发布事务内生成，不作为准备期选择草稿 |
| 任务查询 | `FeedbackAssignmentDao.list_evaluator_assignments`已按评价人查询并可限制状态 | P5用真实任务行验证生成结果；P6再提供员工API和页面 |
| 问卷发布校验 | P4已返回稳定`validationIssues`并验证指标权重、计分题绑定和满分 | P5必须在锁内复用同一权威校验器 |
| 并发基础 | P3/P4服务已按项目行、问卷版本行顺序加锁，并在服务层统一提交/回滚 | P5沿用并扩大该锁顺序，DAO不得提交事务 |
| 权限和数据范围 | 项目接口使用`PreAuthDependency`、接口权限和项目归属数据范围 | P5还要增加基于`SysUser.user_id/dept_id`的候选人员数据范围 |
| 前端路由 | 已有HR项目列表、问卷编辑器、权限守卫和Element Plus表单 | 新增固定发布配置路由，不建立第二套业务前端 |

### 3.2 已验证缺口

- 当前没有人员候选、发布配置、任务预览或发布API。
- 当前没有P5 VO、DAO、Service、组合校验器、Pinia Store和页面。
- 项目创建只创建草稿版本和第一页，不创建默认评价关系。
- `fb_assignment`是员工正式任务；若在准备期提前写入，会破坏“发布生成任务”和任务可见性边界。
- 当前没有能跨请求保存“某被评价人、某关系选择了哪些评价人”的独立配置表。
- 当前任务查询只按评价人过滤，不负责P6员工API的项目状态、权限和响应裁剪。
- P4问卷草稿接口只允许准备阶段，发布后尚无P5冻结配置只读入口。

## 4. 核心决策总表

| 决策 | 已收口方案 |
|---|---|
| 准备期选择持久化 | 新增长期领域表`fb_evaluator_selection`；保存评价人选择配置，发布后随版本冻结保留 |
| 正式任务边界 | `fb_assignment`只在发布事务内物化；准备阶段不创建正式任务 |
| 目标与关系生命周期 | `fb_project_target`、`fb_relation`在`DRAFT`阶段可编辑，版本变为`FROZEN`后服务层拒绝修改 |
| 默认关系 | 固定建立上级、同级、下级、自己、其他五类；除自己外初始禁用且权重为0，不预设组织权重 |
| 自评 | “自己”关系始终启用、不参与常规综合分、权重0；每个被评价人由后端自动派生一项自评选择 |
| 其他关系 | 只由HR手工选择评价人；不得根据部门、岗位或组织树自动推断 |
| 人员展示名 | 快照字段保存`sys_user.nick_name`；候选响应同时返回账号`userName`便于消歧 |
| 人员有效性 | 用户必须存在、未删除且状态正常；有部门ID时部门也必须存在、未删除且状态正常 |
| 数据范围 | 项目归属范围与人员范围同时生效；保存和发布都重新校验全部目标及评价人 |
| 保存协议 | 一个发布配置GET/PUT聚合接口，服务层单事务整体替换目标、关系和评价人选择 |
| 发布预览 | 由后端根据已保存选择生成，不接受客户端上传任务数量或正式任务列表 |
| 发布锁 | 固定按项目、问卷版本、人员ID升序锁定；数据库约束作为最后防线，不以Redis锁保证正确性 |
| 发布幂等 | 同项目同冻结版本的重复请求返回既有结果并标记`alreadyPublished=true`；只有第一次请求执行写入 |
| 发布后编辑 | 项目、问卷、人员、关系和选择配置全部只读；直接调用写API也必须失败 |
| 员工待办边界 | P5生成并验证真实任务；P6再交付员工待办API和页面 |

## 5. 数据库与迁移协议

### 5.1 设计约定：新增一张非临时领域表

计划新增Alembic revision：

```text
20260902_04_feedback_publication
down_revision = 20260902_03_feedback_designer
```

新增`fb_evaluator_selection`“评价人选择配置表”：

| 字段 | PostgreSQL类型 | 约束 | 用途 |
|---|---|---|---|
| `selection_id` | `BIGINT` | 自增主键 | 选择配置ID |
| `project_id` | `BIGINT` | 项目FK，非空 | 评价项目ID |
| `version_id` | `BIGINT` | 与关系、目标同版本，非空 | 问卷版本ID |
| `target_id` | `BIGINT` | 目标复合FK，非空 | 被评价人配置记录ID |
| `target_user_id` | `BIGINT` | `sys_user`及目标复合FK，非空 | 被评价人用户ID |
| `relation_id` | `BIGINT` | 关系复合FK，非空 | 评价关系ID |
| `evaluator_user_id` | `BIGINT` | `sys_user`FK，非空 | 评价人用户ID |
| RuoYi审计字段 | 既有Mixin类型 | 全部中文注释 | 创建、更新和备注 |

约束与索引：

- 唯一约束`uq_fb_evaluator_selection_business_key(project_id, evaluator_user_id, target_user_id, relation_id)`与正式任务业务键一致。
- 复合外键必须保证目标、关系、项目和版本一致，不能把其他项目或版本的ID拼入请求。
- 目标或关系在准备期被删除时，对应选择配置使用`ON DELETE CASCADE`清理；正式任务仍使用`RESTRICT`保护历史数据。
- 建立`(project_id, version_id)`和`(evaluator_user_id, project_id)`索引，分别服务聚合读取和发布任务物化。
- 该表使用`FeedbackAuditMixin`，不使用软删除和独立锁版本；聚合并发由项目与问卷版本锁统一控制。

这张表不是临时中转表：它是发布前选择方案和发布后任务来源的冻结审计输入。不能用请求体、浏览器存储、Redis或`fb_assignment`提前占位替代。

### 5.2 既有三张表的职责

| 表 | 准备阶段 | 发布事务 | 发布后 |
|---|---|---|---|
| `fb_relation` | 可编辑项目内关系 | 校验并进入计分快照 | 随`FROZEN`版本只读 |
| `fb_project_target` | 可编辑目标集合，展示值为临时快照 | 从当前RuoYi用户/部门刷新正式快照并派生`only_self_evaluation` | 历史快照只读 |
| `fb_evaluator_selection` | 可编辑评价人选择，包含后端派生自评 | 作为唯一任务生成输入 | 冻结保留，供任务来源复核 |
| `fb_assignment` | 不存在P5任务 | 一次性生成`PENDING`任务及评价人正式快照 | 员工待办、答卷和报告的正式入口 |

### 5.3 默认关系回填

迁移为所有现存`DRAFT`问卷版本确定性补齐以下固定关系；项目创建服务也必须为新项目写入同样的关系：

| `relation_code` | 类型 | 初始名称 | 初始状态 | 是否计分 | 权重 |
|---|---|---|---|---|---|
| `REL_SUPERVISOR` | `SUPERVISOR` | 上级 | 禁用 | 否 | `0.0000` |
| `REL_PEER` | `PEER` | 同级 | 禁用 | 否 | `0.0000` |
| `REL_SUBORDINATE` | `SUBORDINATE` | 下级 | 禁用 | 否 | `0.0000` |
| `REL_SELF` | `SELF` | 自己 | 启用 | 否 | `0.0000` |
| `REL_OTHER` | `OTHER` | 其他 | 禁用 | 否 | `0.0000` |

- 固定关系允许HR改名称、启停非自评关系、设置是否计分和权重，但不允许删除、改Code或改类型。
- `REL_SELF`允许改显示名称，但不允许禁用、删除、参与常规计分或设置非0权重。
- 自定义关系使用`CUSTOM`类型和`REL_<UUID>`稳定Code，可在发布前新增、改名、排序和删除。
- 迁移按固定Code逐项检查：已存在时必须验证类型和语义，缺失时只有默认名称和顺序均无冲突才插入；遇到冲突必须报告项目/版本并中止，不得静默跳过、改名或覆盖未知数据。
- 降级删除选择配置表，但不删除已经回填到P2既有表中的固定关系；再次升级不得重复。

### 5.4 迁移门禁

- 同步SQLAlchemy实体、关系、`__all__`导出、结构验证器、中文表/字段注释、约束和索引集合。
- P5-00已将评价领域表从13张增加到14张；按上述7个业务字段加5个审计字段计算，模型与数据库注释字段已从184个增加到196个。
- 在独立测试库执行P4→P5→P4→P5有数据往返：P4既有项目/问卷/目标不得丢失；P5选择表按降级语义移除并可重新创建；固定关系不重复。
- 开发库和测试库均升级到唯一head后，才允许开始依赖该表的Service实现。

## 6. 人员、关系和选择配置规则

### 6.1 人员来源和数据范围

- 新增项目内候选人员接口，只返回P5需要的`userId/userName/nickName/deptId/deptName`，不得把RuoYi系统用户管理完整响应直接暴露给业务端。
- 候选查询使用`DataScopeDependency(SysUser, user_alias='user_id', dept_alias='dept_id')`等价的数据范围表达式，同时要求项目本身位于`FbProject.owner_user_id/owner_dept_id`数据范围。
- 候选用户必须满足`sys_user.del_flag='0'`且`status='0'`。
- `dept_id`可以为空；不为空时必须能关联到`sys_dept.del_flag='0'`且`status='0'`的部门，否则不能保存或发布。
- 保存时拒绝越权或失效用户ID；发布时再次完整查询，防止配置后发生停用、删除、调岗或数据范围变化。
- 超级管理员仍走现有RuoYi权限和数据范围实现，不在P5另写“管理员绕过”分支。

### 6.2 人员快照

- 准备阶段为恢复页面可保存当前`nick_name`和部门展示值，但它们不是最终历史依据。
- 发布事务锁定全部参与用户和部门后，以当时的`nick_name`刷新`target_user_name/evaluator_user_name`，以当前有效部门刷新部门ID和名称。
- 账号`user_name`只用于候选列表消歧，不写入现有姓名快照字段。
- 发布后员工改名或调岗不得回写P5快照；历史页面和报告使用冻结快照。

### 6.3 选择和自评派生

- PUT请求用`targetUserId + relationCode + evaluatorUserIds[]`表达选择，不接受客户端提供`target_id/relation_id/selection_id`作为业务关联依据。
- 客户端只提交非自评选择；服务层为每个目标自动派生`targetUserId == evaluatorUserId`的`REL_SELF`选择。
- 非自评关系禁止`evaluator_user_id == target_user_id`，防止把自评伪装成其他关系。
- 同一评价人可以按明确业务键在不同关系下评价同一目标；同一关系下重复选择由请求结构校验和数据库唯一约束共同拒绝。
- `only_self_evaluation`由服务层根据是否存在任何非自评选择计算，客户端不能直接指定。
- 禁用关系不得保存选择；不参与计分的关系权重必须为`0.0000`，可保留非计分反馈任务。

### 6.4 关系计分规则

- 只要项目存在任何非自评选择，所有启用且参与计分的非自评关系权重必须精确合计`100.0000`。
- 参与计分的关系权重必须大于0；不参与计分或禁用关系权重必须为0。
- 正权重关系至少在一个目标下存在评价人选择。
- 每个目标始终至少有自动自评任务。
- 若目标没有任何非自评选择，则标记为仅自评，并在P8按自评有效权重100%处理。
- 若目标存在非自评选择，则至少要有一项属于启用且参与计分的非自评关系；非计分反馈任务不能单独替代正式他评关系。

## 7. 发布配置API协议

### 7.1 接口集合

```text
GET  /feedback/projects/{projectId}/participant-options
GET  /feedback/projects/{projectId}/publication-config
PUT  /feedback/projects/{projectId}/publication-config
POST /feedback/projects/{projectId}/publish
```

权限约定：

| 接口 | 权限 | 数据范围 |
|---|---|---|
| 候选人员GET | `feedback:participant:manage` | 项目归属范围 + RuoYi用户范围 |
| 发布配置GET | `feedback:participant:manage`或`feedback:project:publish` | 项目归属范围 |
| 发布配置PUT | `feedback:participant:manage` | 项目归属范围 + 全部参与人员范围 |
| 发布POST | `feedback:project:publish` | 项目归属范围；锁内再校验全部参与人员范围 |

路由继续挂在`PreAuthDependency`下；Controller只解析依赖和DTO，不承担领域校验、任务生成或事务提交。

### 7.2 聚合配置请求

```text
projectLockVersion
versionId
versionLockVersion
targets[]: { targetUserId }
relations[]: {
  relationCode, relationType, relationName,
  isEnabled, participatesInScore, weight, sortOrder
}
evaluatorSelections[]: {
  targetUserId, relationCode, evaluatorUserIds[]
}
```

- PUT整体替换当前`DRAFT`版本的目标、关系和选择配置，先完成结构校验，再按稳定Code和用户ID映射数据库ID。
- 保存允许配置尚未达到发布条件，响应返回完整问题清单；越权、未知引用、非法固定关系身份、重复和小数协议错误属于结构错误，必须拒绝保存。
- 保存锁顺序与P4一致：项目行→问卷版本行；成功后项目锁版本和版本锁版本都加1，避免问卷与发布配置互相覆盖。
- DAO只`flush`，Service统一`commit/rollback`。

### 7.3 聚合配置响应与权威预览

```text
projectId, projectName, projectStatus, projectLockVersion
versionId, versionLockVersion, versionStatus
editable
targets[]
relations[]
evaluatorSelections[]
preview: {
  targetCount,
  assignmentCount,
  evaluatorCount,
  targetSummaries[]: { targetUserId, selfCount, nonSelfCount, assignmentCount }
}
isPublishReady
validationIssues[]: { code, path, message }
```

- GET和PUT都返回服务端根据已保存配置生成的权威预览。
- 前端可以在编辑中即时显示“未保存预估”，但发布按钮必须要求无未保存改动，并使用最近一次服务端预览。
- `ACTIVE`项目的GET返回同结构冻结只读视图，`editable=false`；PUT必须拒绝。
- 不单独创建第二套“预览任务”表或预览保存接口。

### 7.4 发布请求与响应

发布请求只携带并发前置条件：

```text
projectLockVersion
versionId
versionLockVersion
```

发布响应：

```text
projectId, projectStatus, versionId, versionStatus
publishedBy, publishedTime
targetCount, assignmentCount, evaluatorCount
alreadyPublished
```

客户端不得上传任务数组、快照、权重合计、`isPublishReady`或发布时间。发布响应中的数量来自已提交事务后的数据库结果。

## 8. 校验器分层与稳定问题码

### 8.1 保存结构错误

以下问题直接拒绝PUT，不进入`validationIssues`软清单：

- 固定关系缺少、重复、Code或类型被篡改。
- 关系名称、Code或顺序重复，顺序不连续，权重超范围或超过四位小数。
- 目标、关系或评价人引用不存在；目标与选择引用不一致。
- 同一业务键重复；禁用关系仍携带选择；非自评关系中评价人与被评价人相同。
- 用户不在当前数据范围、已停用、已删除，或非空部门已失效。
- 项目或版本不是可编辑草稿，锁版本不匹配。

### 8.2 发布完整性问题

P5组合校验器先复用P4问卷问题，再按稳定顺序追加以下问题。实现时问题Code和Path必须直接测试：

| Code | 典型Path | 含义 |
|---|---|---|
| `TARGET_REQUIRED` | `targets` | 至少选择一名被评价人 |
| `TARGET_USER_UNAVAILABLE` | `targets.{i}` | 被评价人停用、删除、越权或部门失效 |
| `SELF_RELATION_REQUIRED` | `relations` | 缺少唯一、启用、权重0且不参与计分的自己关系 |
| `RELATION_WEIGHT_TOTAL_INVALID` | `relations` | 存在非自评任务时，参与计分关系权重未精确合计100 |
| `RELATION_POSITIVE_ASSIGNMENT_REQUIRED` | `relations.{i}` | 正权重关系没有任何评价人选择 |
| `EVALUATOR_USER_UNAVAILABLE` | `evaluatorSelections.{i}` | 评价人停用、删除、越权或部门失效 |
| `TARGET_SCORING_ASSIGNMENT_REQUIRED` | `targets.{i}` | 非仅自评目标没有任何参与计分的他评选择 |

- P4已有`QUESTIONNAIRE_NO_QUESTIONS`、`INDICATOR_WEIGHT_TOTAL_INVALID`、`SCORED_QUESTION_INDICATOR_REQUIRED`和`INDICATOR_SCORED_QUESTION_REQUIRED`继续原样返回。
- 问题按问卷、指标、目标、关系、选择的稳定顺序返回，一次给出全部可操作错误，不只抛出第一个模糊错误。
- 发布服务必须在锁内重新构造同一聚合模型并调用同一校验器；不能信任上一次GET/PUT结果。

## 9. 发布事务、锁顺序和幂等

### 9.1 单事务顺序

```text
1. 按项目数据范围 SELECT fb_project FOR UPDATE
2. 若已ACTIVE且versionId等于当前冻结版本，校验既有结果完整后返回幂等响应
3. 校验PREPARING、项目锁版本和请求versionId
4. SELECT 当前DRAFT问卷版本 FOR UPDATE，并校验版本锁
5. 读取完整问卷、指标、关系、目标和选择配置
6. 按user_id升序以FOR SHARE锁定全部目标/评价人，再按dept_id升序锁定有效部门
7. 复用P4校验并执行P5组合校验
8. 刷新目标快照、派生only_self_evaluation并构造计分规则快照
9. 按target、relation、evaluator稳定顺序生成fb_assignment PENDING任务
10. 将问卷版本改为FROZEN，写入frozen_by/frozen_time/scoring_rule_snapshot并增加锁版本
11. 将项目改为ACTIVE，写入current_questionnaire_version_id/published_by/published_time并增加锁版本
12. 只提交一次；任一步异常统一rollback
```

- 选中用户使用`FOR SHARE`而不是只读取快照，避免发布期间并发改名、调岗、停用或删除造成混合快照。
- 两个发布事务共享人员时均按用户ID、部门ID升序取锁；项目和版本锁始终先于人员锁，降低死锁风险。
- 事务内不发送邮件、短信或其他外部副作用，因此首期不需要补偿事务或Outbox。
- Redis不能代替PostgreSQL行锁、状态检查和唯一约束；Redis故障不得导致重复任务。

### 9.2 幂等和并发语义

- 第一次合法请求完成全部写入并返回`alreadyPublished=false`。
- 相同项目和相同版本的重试或并发后到请求不再次写入，返回同一冻结结果并标记`alreadyPublished=true`。
- 项目已发布到其他版本、项目已完成、版本不一致或既有任务数与冻结选择不一致时返回冲突/数据完整性错误，不能伪装成幂等成功。
- 项目行锁负责串行化同项目发布；`uq_fb_assignment_business_key`负责阻止重复任务；选择配置唯一约束负责阻止重复来源。
- 首期项目只能发布一次且不能重新打开，因此不额外引入客户端幂等键表。

## 10. 计分规则快照

发布时由后端生成`fb_questionnaire_version.scoring_rule_snapshot`，建议固定首期结构：

```json
{
  "schemaVersion": 1,
  "calculationVersion": "feedback-score-v1",
  "scoreScale": "100.0000",
  "decimalPlaces": 4,
  "missingRelationPolicy": "RENORMALIZE_SUBMITTED_NON_SELF",
  "selfPolicy": {
    "relationCode": "REL_SELF",
    "weightWhenNonSelfExists": "0.0000",
    "effectiveWeightWhenOnlySelf": "100.0000"
  },
  "indicatorWeights": [],
  "relationWeights": []
}
```

- 所有正式小数序列化为最多四位的十进制字符串，不写JSON浮点数。
- `indicatorWeights`按`sort_order/indicator_code`稳定排序，记录Code、名称和权重。
- `relationWeights`按`sort_order/relation_code`稳定排序，记录Code、类型、名称、启停、是否计分和权重。
- 目标适用关系由冻结的`fb_evaluator_selection`和生成的`fb_assignment`表达，不在JSON中复制任务矩阵。
- 题型、选项分值、指标绑定和满分继续由同一`FROZEN`问卷版本表表达；快照不复制整份问卷。

## 11. 前端交互与路由

### 11.1 路由和入口

- 新增固定路由`/hr/projects/:projectId/publication`和`PublicationConfigView.vue`。
- 路由权限使用`feedback:participant:manage`或`feedback:project:publish`任一可进入，页面内部再分别控制保存和发布按钮。
- 项目列表中准备阶段显示“配置并发布”；进行阶段显示“查看发布配置”。
- 问卷编辑器保留返回项目和前往发布配置的明确入口，不把发布表单塞入问卷编辑器。

### 11.2 页面结构

```text
项目/问卷摘要
  ├─ 1 被评价人
  ├─ 2 评价关系与权重
  ├─ 3 按目标和关系分配评价人
  └─ 4 发布检查、任务数量和不可逆确认
```

- 表单使用`ElForm/ElFormItem`和Element Plus校验；保存、回车和发布使用显式处理器，不使用原生`submit`主链路。
- 人员选择使用Element Plus表格、筛选、分页和左右已选区，不引入第二套UI框架；不能一次把全组织用户加载到浏览器。
- 自评行只读并标记“系统自动添加”；非自评由HR明确添加或移除。
- 脏数据未保存、保存中、有校验问题或无发布权限时禁用发布按钮。
- 发布确认框展示被评价人数、评价人数、任务总数和“发布后不可修改”；确认后防重复点击并统一处理409冲突。
- 发布成功或刷新`ACTIVE`项目后，所有控件切换只读，不以CSS禁用替代后端状态门禁。

## 12. 文件落点与职责

### 12.1 后端已实现落点

```text
module_feedback/
├─ constants.py                              # 已实现：五类固定关系和零权重默认协议
├─ controller/project_controller.py          # 已实现：候选人员、发布配置和发布接口
├─ service/publication_service.py             # 已实现：聚合配置、组合校验、锁和发布事务
├─ dao/publication_dao.py                     # 已实现：关系/目标/选择查询、替换、人员锁定和冻结读取
├─ entity/do/participant_do.py                # 已实现：新增FbEvaluatorSelection及关系
├─ entity/vo/publication_vo.py                # 已实现：配置、预览、问题和发布DTO
└─ validators/publication_validator.py        # 已实现：组合P4问题与P5人员/关系/任务问题

alembic/versions/
└─ 2026_09_02_1400-20260902_04_feedback_publication.py # 已实现
```

- `FeedbackProjectService.create_project`负责给新草稿创建固定关系；迁移负责既有草稿回填。
- `FeedbackStateTransitionService`继续维护状态转换合法性，但不承载整个发布编排。
- `FeedbackAssignmentDao`继续只负责正式任务持久化和查询；准备期选择由`FeedbackPublicationDao`负责。

### 12.2 前端已实现落点

```text
feedback-frontend/src/
├─ api/feedback/projects.js
├─ stores/publicationConfig.js
├─ views/hr/PublicationConfigView.vue
└─ components/feedback/publication/
   ├─ TargetSelectorPanel.vue
   ├─ RelationConfigPanel.vue
   ├─ EvaluatorSelectionPanel.vue
   └─ PublicationPreviewPanel.vue
```

按真实行为拆分组件，不预建空文件；Pinia只保存当前编辑会话，刷新必须重新读取后端。

## 13. 验证矩阵与阶段门禁

### 13.1 后端与数据库

| 场景 | 必须证明的结果 |
|---|---|
| 迁移升级/降级/再升级 | P4数据保留、选择表按预期创建/移除、默认关系不重复、模型/数据库契约一致 |
| 聚合保存/恢复 | 目标、关系、选择和后端派生自评保存后可从PostgreSQL完整恢复 |
| 数据范围 | 越权项目或越权人员ID即使直接构造请求也不能读取、保存或发布 |
| 人员变化 | 配置后改名/调岗，发布使用发布时值；发布后再变化不改变历史快照 |
| 人员失效 | 停用、删除或部门失效阻止发布，并返回稳定问题路径 |
| 组合校验 | P4问卷问题与P5人员/关系问题一次返回且顺序稳定 |
| 原子发布 | 在任务插入或状态切换前注入失败，版本、项目、快照和任务全部回滚 |
| 幂等重试 | 相同请求第二次不新增任务，返回相同发布摘要和`alreadyPublished=true` |
| 并发发布 | 两个独立AsyncSession同时发布，只有一个执行写入，最终任务数无重复 |
| 发布后只读 | 项目、问卷、关系、目标和选择的所有写入口均拒绝`ACTIVE`项目 |
| 任务可查 | 现有按评价人DAO只返回该评价人的真实`PENDING`任务，数量等于权威预览 |

### 13.2 前端与浏览器

- API、Store和组件测试覆盖加载、分页候选、整体保存、锁冲突、后端问题定位、脏状态和重复点击。
- 路由测试覆盖参与人管理权限、发布权限的任一进入，以及页面内按钮的分别授权。
- 真实浏览器至少完成：登录→创建项目→保存P4合法问卷/指标→配置目标/关系/评价人→保存→整页刷新恢复→查看权威预览→二次确认发布→刷新只读。
- 同一E2E运行由测试进程读取真实PostgreSQL，核对版本`FROZEN`、项目`ACTIVE`、快照、选择和`PENDING`任务数量完全一致。
- 使用直接API负向测试证明：篡改人员ID、版本ID、锁版本、预览数量或发布后调用PUT均失败。
- P5不得把员工占位页截图作为待办验收；员工端实际页面留到P6。

### 13.3 P5退出门槛

- 迁移、实体、字段字典和结构验证器一致，开发库/测试库均为唯一P5 head。
- HR发布是一个PostgreSQL事务；任何失败都没有部分冻结或部分任务。
- 冻结配置、任务和计分快照可追溯到同一问卷版本。
- 同项目并发发布只发生一次写入，安全重试不重复生成任务。
- 发布后前后端都不能回到编辑状态。
- 真实浏览器与真实PostgreSQL联合证据证明任务数等于发布前权威预览。
- 只有上述门槛全部通过，才允许进入P6员工答题链路。

### 13.4 P5-00已验证证据

- `ruoyi_feedback_dev`和`ruoyi_feedback_test`均已升级到唯一head `20260902_04_feedback_publication`，应用数据库、Redis隔离和传输加密诊断通过。
- 独立测试库完成P4→P5→P4→P5有数据往返；既有页面和目标保留，选择表按降级语义移除并重建，五类固定关系没有重复。
- 结构验证器确认14张表、196个中文注释字段、196项模型字段契约、12项关键约束和11项关键索引。
- 启用隔离PostgreSQL的`tests\module_feedback`共67项通过；覆盖新项目默认关系、选择持久化、业务唯一键和准备期不生成正式任务。
- Ruff检查和格式检查覆盖49个相关Python文件并通过。
- 这些证据只证明P5-00持久化基线，不证明人员配置接口、发布事务、页面或完整P5阶段已经完成。

### 13.5 P5完整阶段已验证证据

- 隔离测试库的`tests\module_feedback` 78项全部通过，其中真实PostgreSQL用例覆盖聚合保存/恢复、数据范围、人员快照、组合校验、原子回滚、幂等、双Session并发、发布后只读和任务唯一性。
- 前端12个文件共41项通过，覆盖协议序列化、四位小数、候选分页、脏状态、权威问题展示、冻结组件、后端问题回填、冲突和防重复发布；生产构建通过。
- Playwright 7项全部通过；P5用例验证完整配置/发布/只读链路，以及只有`feedback:participant:manage`或只有`feedback:project:publish`时的路由与页内按钮分治。
- 真实`admin`浏览器闭环创建P4合法问卷/指标，配置1名被评价人、2名评价人和2项预览任务，整页刷新恢复后二次确认发布。
- 同一闭环直接查询`ruoyi_feedback_test`，确认项目`ACTIVE`、版本`FROZEN`、计分规则快照保留四位小数字符串、2条选择和2条业务键唯一的`PENDING`任务；新页签刷新为冻结只读且控制台0错误/0警告。
- 结构迁移循环确认14张表、196个中文注释/模型字段、11个`NUMERIC`字段、12项关键约束和11项关键索引；Ruff检查和格式门禁55个Python文件通过。
- P5退出门槛已全部满足；员工待办、答题、暂存与提交仍为P6范围。

## 14. 推荐实施顺序

1. `P5-00`（已完成）：迁移、`FbEvaluatorSelection`、固定关系回填、模型/字段字典/迁移往返门禁。
2. `P5-01`（已完成）：项目内候选人员查询、被评价人保存和发布时快照规则。
3. `P5-02`（已完成）：固定/自定义关系和四位小数权重配置。
4. `P5-03`（已完成）：评价人选择聚合保存、自评派生和服务端任务预览。
5. `P5-04`（已完成）：组合P4/P5完整性校验器和稳定问题码。
6. `P5-05`（已完成）：发布事务、规则快照、正式任务物化和只读查询。
7. `P5-06`（已完成）：幂等、双会话并发、故障回滚和安全负向测试。
8. `P5-07`（已完成）：HR配置/发布/只读页面和权限交互。
9. `P5-08`（已完成）：真实浏览器与真实PostgreSQL联合验收，记录阶段结论。

## 15. 预检结论

P5没有产品范围阻塞项，也不需要替换现有技术栈。唯一必须先补的持久化能力是`fb_evaluator_selection`：它将准备期可恢复的评价人分配与发布后的正式任务分开，同时作为冻结任务来源长期保留。

P5-00至P5-08已按本文协议完成：准备期配置可恢复，发布在单事务内刷新快照、冻结版本、生成唯一任务并切换项目状态，失败时整体回滚，重试/并发不重复写入，发布后前后端均为冻结只读。P5阶段门禁已通过，下一实施起点固定为`P6-01`“我的待办和项目详情API”。
