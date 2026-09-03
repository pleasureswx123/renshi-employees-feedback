# P9 实际接口权限矩阵

2026-09-03 由 `scripts/feedback_p9_api_audit.py` 从实际注册路由导出，共 28 个方法/路径。全部使用 RuoYi 登录保护，无排除路径。接口权限与数据范围分别校验；员工身份仅来自当前登录用户。

| 方法 | 路径 | 权限码 | 范围入口 |
|---|---|---|---|
| GET | `/feedback/employee/history` | `feedback:history:view` | 当前用户 + 服务层任务归属 |
| GET | `/feedback/employee/history/{assignment_id}` | `feedback:history:view` | 当前用户 + 服务层任务归属 |
| GET | `/feedback/employee/projects` | `feedback:task:view` | 当前用户 + 服务层任务归属 |
| GET | `/feedback/employee/projects/{project_id}` | `feedback:task:view` | 当前用户 + 服务层任务归属 |
| GET | `/feedback/employee/tasks/{assignment_id}` | `feedback:task:view` | 当前用户 + 服务层任务归属 |
| PUT | `/feedback/employee/tasks/{assignment_id}/draft` | `feedback:task:answer` | 当前用户 + 服务层任务归属 |
| POST | `/feedback/employee/tasks/{assignment_id}/submit` | `feedback:task:submit` | 当前用户 + 服务层任务归属 |
| GET | `/feedback/health` | `已登录` | 只读迁移就绪检查 |
| GET | `/feedback/projects` | `feedback:project:list` | fb_project(owner_user_id/owner_dept_id) |
| POST | `/feedback/projects` | `feedback:project:add` | 当前用户为项目所有人 |
| DELETE | `/feedback/projects/{project_id}` | `feedback:project:remove` | fb_project(owner_user_id/owner_dept_id) |
| GET | `/feedback/projects/{project_id}` | `feedback:project:list` | fb_project(owner_user_id/owner_dept_id) |
| PUT | `/feedback/projects/{project_id}` | `feedback:project:edit` | fb_project(owner_user_id/owner_dept_id) |
| GET | `/feedback/projects/{project_id}/answers` | `feedback:answer:view` | fb_project(owner_user_id/owner_dept_id) + fb_project_target(target_user_id/target_dept_id) |
| GET | `/feedback/projects/{project_id}/answers/{assignment_id}` | `feedback:answer:view` | fb_project(owner_user_id/owner_dept_id) + fb_project_target(target_user_id/target_dept_id) |
| POST | `/feedback/projects/{project_id}/complete` | `feedback:project:complete` | fb_project(owner_user_id/owner_dept_id) + fb_project_target(target_user_id/target_dept_id) |
| GET | `/feedback/projects/{project_id}/completion-precheck` | `feedback:project:complete` | fb_project(owner_user_id/owner_dept_id) + fb_project_target(target_user_id/target_dept_id) |
| GET | `/feedback/projects/{project_id}/participant-options` | `feedback:participant:manage` | fb_project(owner_user_id/owner_dept_id) + sys_user(user_id/dept_id) |
| GET | `/feedback/projects/{project_id}/progress` | `feedback:progress:view` | fb_project(owner_user_id/owner_dept_id) + fb_project_target(target_user_id/target_dept_id) |
| GET | `/feedback/projects/{project_id}/publication-config` | `feedback:participant:manage 或 feedback:project:publish` | fb_project(owner_user_id/owner_dept_id) |
| PUT | `/feedback/projects/{project_id}/publication-config` | `feedback:participant:manage` | fb_project(owner_user_id/owner_dept_id) + sys_user(user_id/dept_id) |
| POST | `/feedback/projects/{project_id}/publish` | `feedback:project:publish` | fb_project(owner_user_id/owner_dept_id) + sys_user(user_id/dept_id) |
| GET | `/feedback/projects/{project_id}/questionnaire-draft` | `feedback:questionnaire:edit` | fb_project(owner_user_id/owner_dept_id) |
| PUT | `/feedback/projects/{project_id}/questionnaire-draft` | `feedback:questionnaire:edit` | fb_project(owner_user_id/owner_dept_id) |
| GET | `/feedback/projects/{project_id}/reports` | `feedback:report:view` | fb_project(owner_user_id/owner_dept_id) + fb_project_target(target_user_id/target_dept_id) |
| POST | `/feedback/projects/{project_id}/reports/calculate` | `feedback:report:view` | fb_project(owner_user_id/owner_dept_id) + fb_project_target(target_user_id/target_dept_id) |
| GET | `/feedback/projects/{project_id}/reports/{target_user_id}` | `feedback:report:view` | fb_project(owner_user_id/owner_dept_id) + fb_project_target(target_user_id/target_dept_id) |
| GET | `/feedback/reports/projects` | `feedback:report:view` | fb_project(owner_user_id/owner_dept_id) + fb_project_target(target_user_id/target_dept_id) |

创建项目的所有人和部门来自登录上下文。HR 项目接口按 owner 范围过滤；人员候选按系统用户范围过滤；进度/报告/原始答案同时检查项目及被评价人快照范围。发布要求全部人员范围可见，完成要求整个项目范围完整。详情/版本/题目/选项/答卷仍由服务层核对所属关系，见 P9 验收文档的负向用例矩阵。
