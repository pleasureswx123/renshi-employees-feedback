# P7 回收进度与 HR 手动完成契约收口与技术预检

## 1. 文档定位与阶段边界

- 基线：P0至P6已经完成并通过阶段门禁；P6员工待办、逐人暂存、正式提交和本人只读历史是真实PostgreSQL链路。
- 本文冻结P7实施契约并记录阶段验收证据；P7-01至P7-07已于2026-09-03实现并通过阶段门禁。
- P7只交付HR回收进度、完成预检和不可逆手动完成，不计算指标分、关系分、个人总分或报告。
- P8继续负责正式计分和基础报告，P9继续负责首期整体安全、性能、迁移和发布验收；本文不改变P8/P9产品范围。
- 不新增平行账号、员工、部门、角色、登录或答案体系，不引入邮件、短信、公开链接、自动完成或完成后重开。

## 2. 已验证的当前实现基础

### 2.1 后端真实链路

当前`module_feedback`已经具备以下可复用事实：

- 项目HR接口位于`/feedback/projects`，Controller使用`PreAuthDependency`、接口权限和`DataScopeDependency(FbProject, owner_user_id, owner_dept_id)`。
- `fb_project`已经有`ACTIVE -> COMPLETED`所需的`completed_by`、`completed_time`、`completion_reason`和`lock_version`字段，并有“已完成必须存在完成人和完成时间”的数据库检查约束。
- `fb_assignment`已经有`PENDING`、`DRAFT`、`SUBMITTED`、`CLOSED_INCOMPLETE`四种状态，以及`saved_time`、`submitted_time`、`closed_time`和项目/状态索引。
- `PENDING -> CLOSED_INCOMPLETE`、`DRAFT -> CLOSED_INCOMPLETE`是合法转换；`SUBMITTED`和`CLOSED_INCOMPLETE`是终态。
- P6写链路在`FeedbackEmployeeDao.lock_context`中先按当前登录评价人解析项目ID，再取得项目`FOR SHARE`锁，随后取得任务`FOR UPDATE`锁；答卷由同一事务继续排他处理。
- P6锁内重新检查项目必须为`ACTIVE`，并拒绝`CLOSED_INCOMPLETE`任务；因此P7只要遵守同一项目锁协议，就能与暂存/提交互斥。
- P6员工读取链路只允许Token中的评价人访问自己的任务；项目完成后，员工仍可读取本人已提交历史和本人关闭任务的只读状态，但所有写入必须拒绝。
- `fb_answer_sheet`和`fb_answer`保存草稿或正式答案。P7没有读取、返回、覆盖或删除这些记录的业务需要。

### 2.2 前端真实链路

当前`feedback-frontend`已经具备以下基础：

- HR现有路由只有项目列表、问卷编辑器和人员关系/发布页，尚无回收进度路由和页面。
- HR项目请求集中在`src/api/feedback/projects.js`，统一经过`src/utils/request.js`处理Token、传输加密、业务码、401和重复请求。
- 响应拦截器返回后端完整业务信封；现有详情类页面从`response.data`读取，分页接口从标准分页信封读取。
- 路由守卫按`meta.permissions`控制入口，但后端权限和数据范围仍是最终安全边界。
- 员工API位于`/feedback/employee`；待办、答题、提交和历史页面不会作为HR进度数据源。

### 2.3 当前缺口

以下能力在预检时尚未实现，必须由P7落地，不能把文档或静态页面当成功能：

- 后端HR回收统计、明细筛选、完成预检和完成项目接口。
- P7专用VO、DAO和Service事务编排。
- `/hr/projects/:projectId/progress`路由、HR回收进度页面、二次确认和完成后刷新。
- P7直接测试、真实PostgreSQL并发/回滚测试及真实浏览器端到端证据。

## 3. 回收统计口径冻结

### 3.1 唯一统计来源

- 回收统计只从当前项目的真实`fb_assignment`逐条聚合，不使用前端计数、本地缓存、答卷条数、答案条数或异步冗余计数作为权威来源。
- 统计任务集合必须同时满足：`project_id`等于当前项目、项目未软删除、任务属于项目发布时冻结版本。
- 一份任务只按当前`fb_assignment.status`计入一个状态桶。
- 统计必须能用同一数据范围内的进度明细逐条复算。

### 3.2 字段定义

| 字段 | 固定定义 |
|---|---|
| `totalCount` | 应完成数；项目发布生成的任务总数，包含已提交和后来关闭未完成的任务，项目完成后分母不减少 |
| `submittedCount` | `status = SUBMITTED`的任务数 |
| `draftCount` | `status = DRAFT`的任务数 |
| `pendingCount` | `status = PENDING`的任务数，页面文案为“未开始” |
| `closedIncompleteCount` | `status = CLOSED_INCOMPLETE`的任务数 |
| `incompleteCount` | `draftCount + pendingCount + closedIncompleteCount`，只作响应派生字段，不单独持久化 |
| `completionRate` | `submittedCount / totalCount × 100`；使用`Decimal`和`ROUND_HALF_UP`量化到两位小数，响应为字符串，例如`"66.67"` |

补充约定：

- `totalCount = submittedCount + draftCount + pendingCount + closedIncompleteCount`必须始终成立，否则接口报服务端一致性错误，不返回看似正常的统计。
- 理论上的零任务项目返回`completionRate = "0.00"`，不发生除零；P5发布门禁正常情况下不会产生零任务进行中项目。
- 草稿答了几题不影响状态桶；只要任务是`DRAFT`，就只计入`draftCount`。
- 完成率只看正式提交，不把暂存当完成，不把关闭未完成当完成，也不按0分处理关闭任务。
- P7不计算“关系完成率”或“报告有效率”。缺失关系影响只在完成预检中按任务关系提示，正式权重归一化仍由P8完成。

## 4. 筛选、排序与分页契约

### 4.1 进度明细请求

`GET /feedback/projects/{project_id}/progress`

权限：`feedback:progress:view`

路径参数：

| 字段 | 类型 | 规则 |
|---|---|---|
| `project_id` | `BIGINT` | 必填，大于0 |

查询参数：

| 字段 | 类型 | 默认值 | 规则 |
|---|---|---|---|
| `pageNum` | integer | `1` | 大于等于1 |
| `pageSize` | integer | `20` | 1至100 |
| `evaluatorUserId` | integer/null | null | 精确筛选评价人快照对应用户ID |
| `targetUserId` | integer/null | null | 精确筛选被评价人快照对应用户ID |
| `relationId` | integer/null | null | 精确筛选冻结关系ID，必须属于当前项目版本 |
| `status` | enum/null | null | `PENDING`、`DRAFT`、`SUBMITTED`、`CLOSED_INCOMPLETE`之一 |
| `evaluatorKeyword` | string/null | null | 去首尾空格后按评价人姓名快照模糊匹配，最长100字符 |
| `targetKeyword` | string/null | null | 去首尾空格后按被评价人姓名快照模糊匹配，最长100字符 |

筛选约定：

- 所有非空筛选条件使用AND组合。
- ID筛选优先用于选择器的稳定值；关键字只用于远程搜索和直接文本查询，不能替代ID权限判断。
- 未知状态、越界分页、负数ID或不属于项目的`relationId`返回422，不静默忽略。
- 筛选只影响`rows`和分页`total`；顶部`summary`始终是当前HR数据范围内该项目的全量统计，不随明细筛选变化。
- 固定排序为：任务状态业务顺序`DRAFT`、`PENDING`、`SUBMITTED`、`CLOSED_INCOMPLETE`，再按被评价人姓名快照、评价人姓名快照、关系顺序、`assignment_id`升序。分页期间不得使用不稳定排序。

### 4.2 进度明细响应

使用`DataResponseModel[ProgressPageModel]`，成功HTTP 200：

```json
{
  "code": 200,
  "msg": "操作成功",
  "data": {
    "projectId": 1,
    "projectName": "2026年度反馈",
    "projectStatus": "ACTIVE",
    "projectLockVersion": 3,
    "dataScopeComplete": true,
    "scopeMessage": null,
    "summary": {
      "totalCount": 10,
      "submittedCount": 6,
      "draftCount": 2,
      "pendingCount": 2,
      "closedIncompleteCount": 0,
      "incompleteCount": 4,
      "completionRate": "60.00"
    },
    "filterOptions": {
      "relations": [
        {
          "relationId": 8,
          "relationCode": "PEER",
          "relationName": "同级",
          "sortOrder": 2
        }
      ]
    },
    "rows": [
      {
        "assignmentId": 101,
        "evaluatorUserId": 12,
        "evaluatorName": "评价人姓名快照",
        "evaluatorDeptName": "评价人部门快照",
        "targetUserId": 21,
        "targetName": "被评价人姓名快照",
        "targetDeptId": 5,
        "targetDeptName": "被评价人部门快照",
        "relationId": 8,
        "relationCode": "PEER",
        "relationName": "同级",
        "status": "DRAFT",
        "savedTime": "2026-09-02T10:00:00",
        "submittedTime": null,
        "closedTime": null
      }
    ],
    "total": 10,
    "pageNum": 1,
    "pageSize": 20
  }
}
```

响应中的人员、部门和关系名称全部使用发布冻结快照或冻结关系，不回查当前组织名称覆盖历史语义。

- `dataScopeComplete`必须由后端比较项目全部发布目标与当前可见目标得出；前端不得根据任务数量自行推断。
- `scopeMessage`在局部数据范围时固定返回“当前数据范围仅覆盖部分被评价人”，完整范围时返回`null`。
- `filterOptions.relations`是当前HR可见任务涉及的完整冻结关系集合，按关系`sortOrder`和`relationId`稳定排序，不从当前分页`rows`反推，也不复用发布配置接口。

## 5. 数据范围与权限冻结

### 5.1 回收进度

访问进度必须同时通过：

1. 已登录及`feedback:progress:view`接口权限；
2. 项目未删除，并通过`FbProject.owner_user_id/owner_dept_id`的RuoYi项目数据范围；
3. 明细中的被评价人通过发布快照`FbProjectTarget.target_user_id/target_dept_id`的数据范围。

固定规则：

- 评价人的当前部门不作为进度数据范围主依据，避免跨部门评价被错误拆分。
- 被评价人使用发布时部门快照，不因后续调岗改变历史项目可见性。
- 超级管理员沿用RuoYi现有全数据范围语义，不新增P7特例。
- 项目不存在、项目越权和项目全部目标越权统一返回404，避免通过ID探测项目。
- 若HR只能看到项目部分目标，`dataScopeComplete=false`，只返回可见目标的统计和明细，并明确提示“当前数据范围仅覆盖部分被评价人”；页面不得把局部统计冒充全项目统计。

### 5.2 手动完成

手动完成的影响是整个项目，因此必须同时满足：

- `feedback:project:complete`权限；
- 项目通过项目数据范围；
- 当前HR数据范围覆盖项目全部发布目标，即预检返回`dataScopeComplete=true`。

只覆盖部分目标时，完成预检返回`canComplete=false`，完成请求返回403；禁止关闭HR看不到的目标任务。

## 6. 答案不可见边界冻结

P7进度和完成接口无论调用者是否另有`feedback:answer:view`，都不得返回或记录：

- `fb_answer`的选项、数值、文本、附加原因、原始题目分或展示值快照；
- `fb_answer_sheet`的答案集合、原始总分、提交快照、幂等键、答案摘要；
- 草稿已答题数、最近页面、草稿正文或任何可推断具体答案的字段；
- 完整请求体、完整答卷响应或日志中的答案内容。

P7允许返回的边界仅限项目、评价人/被评价人/关系冻结身份、任务状态、状态时间、数量和完成率。原始答案查看是独立能力，必须由未来专用只读接口同时校验`feedback:answer:view`和数据范围；不得借P7进度接口顺带开放。

## 7. 完成预检契约

### 7.1 接口

`GET /feedback/projects/{project_id}/completion-precheck`

权限：`feedback:project:complete`

成功使用`DataResponseModel[CompletionPrecheckModel]`：

```json
{
  "code": 200,
  "msg": "操作成功",
  "data": {
    "projectId": 1,
    "projectName": "2026年度反馈",
    "projectStatus": "ACTIVE",
    "projectLockVersion": 3,
    "dataScopeComplete": true,
    "canComplete": true,
    "summary": {
      "totalCount": 10,
      "submittedCount": 6,
      "draftCount": 2,
      "pendingCount": 2,
      "closedIncompleteCount": 0,
      "incompleteCount": 4,
      "completionRate": "60.00"
    },
    "missingRelations": [
      {
        "targetUserId": 21,
        "targetName": "被评价人姓名快照",
        "relationId": 8,
        "relationName": "同级",
        "assignmentCount": 2,
        "submittedCount": 0
      }
    ],
    "impactMessages": [
      "完成后2项已暂存任务和2项未开始任务将关闭且不可继续作答。",
      "报告只会使用6项已提交答卷；缺失关系不会按0分处理。"
    ],
    "precheckedAt": "2026-09-02T10:05:00"
  }
}
```

### 7.2 预检规则

- 预检只允许`ACTIVE`项目进入确认；`PREPARING`返回409和`PROJECT_NOT_ACTIVE`。
- 已完成项目返回已有完成结果摘要，`canComplete=false`，页面只展示完成信息，不再次弹出可执行确认。
- `missingRelations`按“某被评价人+某冻结关系生成过任务但提交数为0”生成，只是P8报告影响提示，不在P7计算分数。
- `impactMessages`由后端根据权威统计生成，前端不得自行拼装另一套业务结论。
- 页面点击“完成项目”时必须先实时调用预检，预检成功后用该响应展示二次确认；不得复用进入页面时的旧统计。
- 预检为保证一次响应内项目与任务统计一致，短暂按“项目`FOR SHARE`→任务按`assignment_id`升序`FOR SHARE`”读取；它不改变任何业务状态，只在请求事务持续期间让员工写入和项目完成短暂等待。最终完成请求仍必须在项目排他锁内重新统计并核对预检值。

## 8. 手动完成请求与响应契约

### 8.1 接口与请求字段

`POST /feedback/projects/{project_id}/complete`

权限：`feedback:project:complete`

请求模型`ProjectCompleteRequestModel`：

```json
{
  "projectLockVersion": 3,
  "completionReason": "本轮评价截止，按当前回收情况结束项目。",
  "expectedSummary": {
    "totalCount": 10,
    "submittedCount": 6,
    "draftCount": 2,
    "pendingCount": 2,
    "closedIncompleteCount": 0
  }
}
```

字段规则：

| 字段 | 规则 |
|---|---|
| `projectLockVersion` | 必填，非负，必须等于预检响应值 |
| `completionReason` | 必填，去首尾空格后1至500个Unicode字符；作为项目不可变完成原因保存 |
| `expectedSummary` | 必填，五个非负整数必须与刚才预检展示值一致，且总数恒等式成立 |

前端必须使用预检原值构造请求，不自行重新计算或省略计数。普通业务提交使用显式按钮处理器，确认期间禁用完成按钮并显示加载态；不得依赖原生表单submit主链路。

### 8.2 成功响应

使用`DataResponseModel[ProjectCompleteResultModel]`，首次成功HTTP 200：

```json
{
  "code": 200,
  "msg": "项目已完成",
  "data": {
    "projectId": 1,
    "projectStatus": "COMPLETED",
    "projectLockVersion": 4,
    "completedBy": 7,
    "completedTime": "2026-09-02T10:06:00",
    "completionReason": "本轮评价截止，按当前回收情况结束项目。",
    "alreadyCompleted": false,
    "summary": {
      "totalCount": 10,
      "submittedCount": 6,
      "draftCount": 0,
      "pendingCount": 0,
      "closedIncompleteCount": 4,
      "incompleteCount": 4,
      "completionRate": "60.00"
    }
  }
}
```

### 8.3 状态与错误语义

| HTTP状态 | 稳定问题码 | 语义 |
|---|---|---|
| 403 | `PROJECT_COMPLETION_SCOPE_FORBIDDEN` | 有权限码但数据范围不能覆盖项目全部发布目标 |
| 404 | `PROJECT_NOT_FOUND` | 项目不存在、已删除或项目数据范围越权 |
| 409 | `PROJECT_NOT_ACTIVE` | 项目仍为准备阶段，不能完成 |
| 409 | `PROJECT_VERSION_CONFLICT` | 项目锁版本与预检不一致 |
| 409 | `COMPLETION_PRECHECK_STALE` | 锁内最新任务统计与`expectedSummary`不一致；响应`data.latestPrecheck`返回最新预检，前端关闭旧确认框并要求重新确认 |
| 422 | `VALIDATION_ERROR` | 原因、计数、枚举或恒等式不合法 |
| 500 | `PROJECT_COMPLETION_FAILED` | 非预期失败；事务必须已回滚，不得返回成功 |

## 9. 项目排他锁与P6共享锁兼容顺序

### 9.1 P7固定锁顺序

手动完成必须在一个数据库事务中按以下顺序执行：

```text
1. 按项目数据范围定位project_id，不加任务锁
2. SELECT fb_project ... FOR UPDATE              项目排他锁
3. 锁内重新检查项目状态、项目lock_version和完整目标数据范围
4. SELECT fb_assignment ...
   WHERE project_id = ?
   ORDER BY assignment_id
   FOR UPDATE                                     任务排他锁，固定升序
5. 基于已锁任务重新统计并核对expectedSummary
6. PENDING/DRAFT -> CLOSED_INCOMPLETE，统一写closed_time和update_time并递增任务lock_version
7. 项目ACTIVE -> COMPLETED，写completed_by/completed_time/completion_reason并递增项目lock_version
8. flush后复核状态恒等式
9. commit
```

P7不得先锁任务再锁项目，也不得分批提交任务关闭和项目完成。

### 9.2 与P6的竞争结果

P6固定顺序是项目`FOR SHARE` -> 单任务`FOR UPDATE` -> 答卷`FOR UPDATE`。兼容结果冻结如下：

- P6先取得项目共享锁：P7等待；P6提交成功后释放锁，P7再取得排他锁、重新统计，将该任务视为`SUBMITTED`而不是关闭。
- P7先取得项目排他锁：P6等待；P7提交完成后，P6取得共享锁并在锁内看到项目`COMPLETED`，所有暂存/提交请求返回409且不得写答案。
- P7取得项目锁后，任务必须按`assignment_id`升序锁定，避免多个维护操作使用不同任务顺序造成死锁。
- 锁等待、死锁、数据库断连或任何中途异常都走统一回滚；不得通过忽略锁异常继续完成。

## 10. 关闭未提交任务与草稿保留

- 只把`PENDING`和`DRAFT`任务转换为`CLOSED_INCOMPLETE`。
- `SUBMITTED`任务保持原状态、`submitted_time`、答卷和答案不变。
- 已经`CLOSED_INCOMPLETE`的任务保持终态，不重复改写`closed_time`。
- 首次关闭统一使用与项目`completed_time`相同的事务时间写`closed_time`，便于审计对账。
- 任务关闭时递增`fb_assignment.lock_version`；不修改`fb_answer_sheet.lock_version`。
- 已暂存答卷及草稿答案原样保留，不删除、不覆盖、不转成正式提交，也不进入P8报告输入。
- 项目完成后员工任务详情可以只读展示“已关闭未完成”和既有本人草稿，但编辑、暂存、提交按钮必须禁用；后端写接口仍须独立拒绝。

## 11. 重复完成、失败回滚与审计日志

### 11.1 重复完成

- 项目已经`COMPLETED`时，相同或后到的完成请求不得再次更新项目、任务、完成原因或完成时间。
- 在权限和数据范围仍合法的前提下，重复请求HTTP 200返回当前持久化完成结果，并设置`alreadyCompleted=true`。
- 已保存的`completed_by`、`completed_time`、`completion_reason`和最终统计是权威结果；重复请求中的不同原因不得覆盖。
- 两个并发完成请求由项目排他锁串行化：第一个执行状态转换，第二个锁内读取到`COMPLETED`并按幂等结果返回。

### 11.2 失败回滚

必须用故障注入证明以下任一点失败时项目和任务全部回到事务前状态：

- 任务锁定或统计失败；
- 关闭部分任务后异常；
- 写入项目完成字段前后异常；
- flush触发数据库约束异常；
- commit失败。

失败后不得存在“项目仍ACTIVE但部分任务已关闭”或“项目已COMPLETED但仍有PENDING/DRAFT任务”。重试必须能从完整旧状态重新执行。

### 11.3 审计日志

- 首次成功完成必须在同一数据库事务内追加一条`fb_project_completion_audit`不可变业务审计；该表只保存项目完成事实，不建设平行账号、人员或通用日志体系。
- 成功审计至少可追踪：项目ID、操作人ID/账号、请求时间、完成原因、完成前统计、关闭任务数、结果状态、请求追踪标识；审计写入失败必须回滚项目完成和任务关闭。
- 完成接口进入Controller后使用现有RuoYi`@Log`和操作日志设施，业务类型为`UPDATE`，标题固定为“评价项目完成”。重复完成和Controller内被拒绝/失败完成按稳定问题码、失败阶段及请求追踪标识进入结构化应用日志，并由现有异步设施尝试写入`sys_oper_log`；参数校验、认证或权限依赖在Controller前拒绝的请求不承诺写入`sys_oper_log`。所有失败或重复请求均不追加或改写首次成功业务审计。
- 进度读取只记录必要访问元数据；日志不得记录答案、题目附加原因、答卷快照、Token、传输密钥或完整人员目录响应。项目完成原因按完成审计契约记录。
- 重复完成记录为幂等重复操作，不改写首次完成审计事实。
- `fb_project_completion_audit`存在正式数据时，Alembic降级必须拒绝删除该表；空表才允许受保护降级。
- 失败/重复操作日志的跨Redis故障可靠落库和全链路追踪字段属于P9-06可观测性加固门禁，不把它伪装为P7已完成的数据库能力。

## 12. 前端集成契约

### 12.1 固定调用链

```text
/hr/projects
  -> 进行中/已完成项目的“回收进度”入口
  -> /hr/projects/:projectId/progress
  -> src/api/feedback/projects.js
  -> GET /feedback/projects/{id}/progress
  -> 页面渲染权威summary和分页rows

点击“完成项目”
  -> GET /feedback/projects/{id}/completion-precheck
  -> 按最新precheck展示不可逆二次确认
  -> POST /feedback/projects/{id}/complete
  -> 成功后重新GET progress和project detail
  -> 页面变为已完成只读状态
```

### 12.2 页面行为

- 新路由固定为`/hr/projects/:projectId/progress`，路由权限为`feedback:progress:view`；完成按钮另按`feedback:project:complete`显示。
- 只有完成权限、项目为`ACTIVE`、数据范围完整且预检`canComplete=true`时允许进入最终确认。
- 筛选、翻页和刷新都重新请求后端，不使用浏览器本地存储保存正式进度。
- 完成409且带`latestPrecheck`时，必须关闭旧确认、更新页面统计并明确要求HR重新阅读和确认；不得自动重发完成请求。
- 完成成功后清理进行中的确认状态，刷新项目和进度；已完成页面保留进度只读查看，不提供重开入口。
- 普通员工、只有`feedback:progress:view`但没有完成权限的HR、只有完成权限但没有进度权限的HR均按权限矩阵显示最小可用能力；后端每个接口独立鉴权。

## 13. P7端到端验收门禁

### 13.1 后端与PostgreSQL

- [x] 统计四状态逐条对账，验证恒等式、零分母和两位小数完成率。
- [x] 评价人、被评价人、关系、状态组合筛选和稳定分页排序通过。
- [x] 项目数据范围、目标快照数据范围、部分范围提示和完成全范围门禁通过。
- [x] 进度/预检/完成响应和日志中不存在答案、原因、分数或答卷快照。
- [x] 预检返回提交、暂存、未开始、关闭未完成数量及缺失关系影响。
- [x] 完成请求校验锁版本、原因和预期统计；统计变化返回`COMPLETION_PRECHECK_STALE`及最新预检。
- [x] 真实PostgreSQL验证P6提交与P7完成双会话竞争的两种先后顺序。
- [x] 两个并发完成请求只有一次状态写入，后到请求返回`alreadyCompleted=true`。
- [x] 故障注入覆盖部分关闭、项目更新、flush和commit失败，项目与任务整体回滚。
- [x] 完成后无`PENDING/DRAFT`任务；提交保持`SUBMITTED`，未提交全部为`CLOSED_INCOMPLETE`，草稿答卷原样保留。
- [x] P6所有写入接口在项目完成后返回409且数据库无新增或覆盖。
- [x] 首次成功完成拥有同事务不可变业务审计；重复和失败完成保留稳定问题码及追踪日志，且敏感内容脱敏。

### 13.2 前端与浏览器

- [x] API测试逐字段核对三个P7接口的路径、方法、查询、请求和响应信封。
- [x] 页面测试覆盖加载、空态、错误、筛选、分页、权限、完成加载态、防重入和409重新确认。
- [x] 路由守卫阻止普通员工进入HR进度页，直接调用后端同样返回权限错误。
- [x] 真实浏览器使用一个项目构造2项`SUBMITTED`、1项`DRAFT`、1项`PENDING`。
- [x] 局部部门范围HR只看到可见目标，无法看到完成入口，直接调用完成接口返回403。
- [x] 全数据范围HR进入进度页看到4项应完成、2项已提交、1项已暂存、1项未开始和`50.00%`。
- [x] HR点击完成后先看到实时预检；确认成功后项目为`COMPLETED`，两项未提交任务为`CLOSED_INCOMPLETE`。
- [x] 员工已提交历史仍只读可见；关闭任务不能继续暂存或提交，原草稿答案保持不变。
- [x] 浏览器控制台无错误，P7业务请求无非预期4xx/5xx；刷新后状态从PostgreSQL恢复。
- [x] 后端评价模块回归、共享日志回归、前端全量单测、既有E2E、真实P7 E2E、生产构建、Ruff和格式检查全部通过。

### 13.3 阶段退出判定

上述自动化与真实链路证据齐全，且回收统计可由明细复算、完成事务与P6锁协议已真实验证、完成后所有写接口已真实拒绝，因此P7-01至P7-07可以标记完成并允许进入P8。

## 14. 阶段验收结果

2026-09-03最终门禁结果：

- 后端评价模块全量测试：`159 passed`，包含真实PostgreSQL事务、双会话竞争、回滚和大任务集合参数边界。
- P7迁移链：仓库唯一head为`20260902_07_feedback_audit`，真实PostgreSQL `downgrade 20260902_06_feedback_permissions -> upgrade head`通过；不可变完成审计非空时拒绝破坏性降级。
- 后端静态门禁：Ruff检查、Ruff格式、Python编译和`git diff --check`通过。
- 前端全量单测：`24 files / 134 tests passed`；生产构建通过；Mock Playwright：`16 passed`。
- 真实全流程：`1 passed`，覆盖发布、员工暂存与提交、真实角色/部门数据范围、局部范围完成403、全量HR完成、关闭未交任务、已提交答案及草稿逐字段保留、草稿所有者完成后真实暂存/提交均返回`409 PROJECT_CLOSED`，以及完成审计数据库对账。

P7-01至P7-07全部完成，允许在本地`main`基线上进入P8；P8计分和报告、P9整体交付门禁仍按原范围执行。