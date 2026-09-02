# Feedback 平台端开发规则

本文件适用于 `feedback-frontend` 目录，并继承仓库根目录 `AGENTS.md`。

## 平台边界

`feedback-frontend` 是员工反馈与 360° 评价业务平台，同时包含：

- HR 工作台：评价项目、问卷编辑、指标、评价关系、发布、回收进度、手动完成和基础报告。
- 员工工作台：我的待办、逐人答题、暂存、提交和我评价的。

用户、部门、岗位、角色、菜单配置和系统运维仍在 `ruoyi-fastapi-frontend` 中完成。

## 技术栈

初始化时参考管理端当前核心版本：

- Vue 3
- Vite
- Element Plus
- Pinia
- Vue Router
- Axios
- `vuedraggable`，用于页面和题目排序
- Quill 或项目既有富文本组件，用于问卷说明

必须复用后端现有 `/login`、`/getInfo`、`/logout`、Token 和传输加密契约，但平台端代码独立维护。

## 推荐目录

```text
src/
├─ api/
│  ├─ auth.js
│  └─ feedback/
├─ assets/
├─ components/
│  └─ feedback/
├─ layouts/
├─ router/
├─ stores/
├─ utils/
├─ views/
│  ├─ auth/
│  ├─ employee/
│  └─ hr/
└─ main.js
```

## 路由与权限

- 平台路由使用固定业务路由，并根据 `/getInfo` 返回的角色和权限码控制可见性。
- 后端权限是最终安全边界，前端隐藏按钮不能替代接口鉴权。
- 员工接口不得接收一个可随意替换的“当前员工ID”；后端必须从登录上下文取得评价人身份。
- 同时具有 HR 和员工权限的用户可以切换工作台。

建议首期路由：

```text
/login
/employee/todos
/employee/reviews
/hr/projects
/hr/projects/:projectId/editor
/hr/projects/:projectId/participants
/hr/projects/:projectId/progress
/hr/projects/:projectId/reports
```

## 页面与交互

- HR 页面以桌面端效率为主；员工答题页面必须支持窄屏和手机浏览器。
- 使用 Element Plus 组件族的真实交互语义，不用自制 DOM 替代选择器、评分、滑块、数字输入、对话框和表单校验。
- 提交、发布、完成项目等不可逆操作必须二次确认。
- 异步操作必须有加载态、防重复提交和明确失败提示。
- 草稿保存与正式提交必须是两个不同接口和不同按钮。
- 已提交页面只读，不允许通过前端状态恢复编辑。
- 问卷总分可在前端实时预览，但后端保存和校验结果为准。

## 状态管理

- 用户、Token、权限和工作台上下文放入 Pinia。
- 问卷编辑草稿可以使用独立 Store，但持久化必须经过后端草稿接口。
- 不在浏览器本地长期保存正式答案、报告结果或完整员工目录。

## 测试要求

- 组件测试覆盖题型渲染、必答校验、分页和只读答案。
- Store/API 测试覆盖草稿、提交、防重复提交和权限错误。
- 端到端测试至少覆盖 HR 发布项目、员工逐人提交、HR 手动完成和报告查看。
