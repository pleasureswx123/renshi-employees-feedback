# 架构与工程边界

## 1. 总体结构

```text
ruoyi-fastapi-frontend          feedback-frontend
系统管理端                       评价业务平台
├─ 用户/部门/岗位                ├─ HR工作台
├─ 角色/菜单/字典                └─ 员工工作台
└─ 日志/参数/运维                       │
              │                        │
              └──────────┬─────────────┘
                         ▼
              ruoyi-fastapi-backend
              ├─ 现有RuoYi模块
              └─ module_feedback
                         │
                         ▼
              PostgreSQL + Redis
```

## 2. 后端边界

`ruoyi-fastapi-backend` 是唯一后端：

- 复用 `/login`、`/getInfo`、`/logout` 和现有 Token 机制。
- 复用 `sys_user`、`sys_dept`、岗位、角色、菜单、日志和通知基础设施。
- 新增 `module_feedback`，不新增平行账号或员工模块。
- API统一放在 `/feedback` 下。
- 领域状态变更由服务层完成，Controller只负责协议适配、鉴权和响应。
- DAO只负责数据库访问，不承载业务状态判断。

建议后端模块结构：

```text
module_feedback/
├─ controller/
├─ dao/
├─ entity/
│  ├─ do/
│  └─ vo/
├─ service/
├─ enums/
├─ calculators/
└─ validators/
```

## 3. 管理端边界

`ruoyi-fastapi-frontend` 仅负责系统管理：

- 用户、部门和岗位维护。
- HR和员工角色授权。
- 权限码和菜单配置。
- 字典、参数、通知、日志和运维页面。

问卷编辑、人员配置、发布、员工答题和报告不放入管理端。

## 4. 平台端边界

`feedback-frontend` 是独立业务前端：

- 采用固定业务路由和专用布局。
- 根据当前用户角色和权限展示 HR 或员工工作台。
- 与管理端共享后端契约，不共享构建产物或直接源码引用。
- 首期HR与员工均通过PC浏览器使用评价平台；手机浏览、作答和预览不在首期范围内，已有基础响应式样式不代表手机端功能交付。

工作台显示偏好约定：顶部提供浏览器全屏及浅色/深色模式切换，HR与员工工作台共用。主题由平台端Pinia管理，以`feedback-theme`保存在当前浏览器，刷新及工作台切换后恢复，并同步同源标签页；默认浅色。不向后端写入账号或业务配置。暗色样式复用Element Plus主题变量，业务卡片、问卷、表格和弹窗使用同一组语义颜色；管理端实现独立维护。全屏使用浏览器原生能力，按实际全屏事件同步按钮状态，不支持时禁用并提示。

## 5. 权限边界

首期固定权限码：

```text
feedback:project:list
feedback:project:add
feedback:project:edit
feedback:project:publish
feedback:project:complete
feedback:project:remove
feedback:questionnaire:edit
feedback:participant:manage
feedback:progress:view
feedback:report:view
feedback:answer:view
feedback:task:view
feedback:task:answer
feedback:task:submit
feedback:history:view
```

员工任务接口必须从登录上下文取得评价人，不能仅使用前端传入的用户ID过滤。

HR查询项目和人员时应复用RuoYi数据范围能力；是否允许跨部门管理由角色数据范围决定。

### 5.1 首期角色与权限码映射

| 能力 | HR基础角色 | 员工角色 | 同时具有HR和员工角色 |
|---|---|---|---|
| 项目列表、新增、编辑、删除、发布、完成 | `feedback:project:list`、`feedback:project:add`、`feedback:project:edit`、`feedback:project:remove`、`feedback:project:publish`、`feedback:project:complete` | 无 | 继承HR权限 |
| 问卷与人员配置 | `feedback:questionnaire:edit`、`feedback:participant:manage` | 无 | 继承HR权限 |
| 回收进度 | `feedback:progress:view` | 无 | 继承HR权限 |
| 基础报告 | `feedback:report:view` | 无 | 继承HR权限 |
| 已提交原始答案 | 默认无；必须额外显式授予`feedback:answer:view` | 不能使用该权限读取他人答案 | 只有额外显式授权时可用 |
| 我的待办、答题、提交、历史 | 无 | `feedback:task:view`、`feedback:task:answer`、`feedback:task:submit`、`feedback:history:view` | 继承员工权限 |

说明：

- “同时具有HR和员工角色”采用权限并集，不创建第三套身份或账号体系。
- `feedback:answer:view`是敏感权限，不包含在HR基础角色中；是否授予由系统管理端角色配置决定。
- 前端工作台切换只影响入口和布局，不改变后端权限判断。
- 权限码只解决“是否具备能力”，数据范围和资源归属继续解决“可以操作哪些数据”。

### 5.2 进度、答案和报告的数据边界

| 资源 | 必需权限 | 可见内容 | 数据范围依据 |
|---|---|---|---|
| 回收进度 | `feedback:progress:view` | 评价人、被评价人、关系、任务状态、数量和完成率；不含答案内容 | 项目归属部门与被评价人发布快照部门 |
| 原始答案 | `feedback:answer:view` | 只读的已提交答案及评价人身份；不允许查看草稿内容 | 被评价人发布快照部门，并校验项目归属 |
| 基础报告 | `feedback:report:view` | 已完成项目的关系、指标、题目汇总和个人/团队基础报告；不自动包含原始答案 | 被评价人发布快照部门，并校验项目归属 |
| 员工任务和历史 | 员工任务类权限 | 当前登录评价人自己的任务、草稿、已提交答案和历史 | 后端从Token取得评价人，不接受前端替换身份 |

评价人当前所在部门不作为HR查看某份答卷的主要数据范围依据，否则跨部门评价会造成报告被错误拆分。历史报告统一使用发布时保存的被评价人部门快照。

## 6. 版本与不可变性

- 准备阶段编辑的是项目草稿。
- 准备阶段的评价人选择保存到`fb_evaluator_selection`，不提前创建员工正式任务。
- 发布时在同一数据库事务中冻结问卷、关系、目标和评价人选择，刷新人员快照并物化`fb_assignment`正式任务。
- 已发布配置不得原地覆盖。
- 提交答案只追加或完成状态迁移，不允许覆盖历史提交。
- 报告结果必须能追溯到问卷版本、计算规则和答卷集合。

## 7. 部署建议

可以使用同一反向代理暴露：

```text
/admin/     → ruoyi-fastapi-frontend
/feedback/  → feedback-frontend
/api/       → ruoyi-fastapi-backend
```

也可以使用不同域名，但必须显式配置CORS、Token和传输加密策略。首期不要求管理端与平台端共享浏览器登录态，只要求使用同一账号体系。
