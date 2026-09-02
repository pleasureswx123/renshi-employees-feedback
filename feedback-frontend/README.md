# Feedback 评价平台端

本目录是员工反馈与 360° 评价业务平台的独立前端，同时承载 HR 工作台和员工工作台。

## 当前实现状态

截至 2026-09-02，P1“工程基线与登录权限”已经完成并通过阶段门禁：

- 已建立 Vue 3、Vite、Element Plus、Pinia、Vue Router、Axios 工程。
- 已接通现有 RuoYi 的登录、当前用户、退出、Token、权限和传输加密契约。
- 已建立 HR/员工双工作台、权限路由、无权限页及工作台切换。
- 已建立组件、Store、API 和真实浏览器 E2E 测试基线。

当前工作台中的业务页面是边界明确的占位页，只证明工程、登录和权限链路已经接通；评价项目、问卷、任务、答题、进度和报告等正式业务尚未实现。

## 本地命令

```powershell
npm install
npm run dev
npm test
npm run build
npm run test:e2e
```

开发服务默认把 `/dev-api` 代理到 `http://127.0.0.1:9099`。如需连接其他本地后端，可通过进程环境变量 `VITE_APP_PROXY_TARGET` 覆盖代理目标。

## 开发边界

1. 阅读[平台端开发规则](./AGENTS.md)和[项目文档索引](../docs/feedback/README.md)。
2. 复用后端的账号、组织、角色和权限体系，不在本工程重复建设。
3. 不直接导入 `ruoyi-fastapi-frontend/src` 源码；所需能力在本工程按兼容契约独立实现。
4. 业务表单使用 Element Plus 表单与校验，普通业务提交使用显式点击或回车处理器。
5. 首期只允许已登录用户从系统内待办参评，不提供公开链接、二维码、小程序、邮件或短信参评入口。

后续实现顺序和退出门禁以[分阶段实施路线图](../docs/feedback/09-implementation-roadmap.md)为准。
