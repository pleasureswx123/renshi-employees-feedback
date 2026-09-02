# Feedback 评价平台端

本目录用于实现员工反馈与 360° 评价业务平台，同时承载 HR 工作台和员工工作台。

当前仍处于编码前设计阶段，尚未初始化前端工程。开始实现前请阅读：

1. [平台端开发规则](./AGENTS.md)
2. [项目文档索引](../docs/feedback/README.md)
3. [架构与工程边界](../docs/feedback/02-architecture-and-boundaries.md)
4. [首期范围与验收标准](../docs/feedback/06-mvp-scope-and-acceptance.md)
5. [分阶段实施路线图](../docs/feedback/09-implementation-roadmap.md)

平台端计划采用 Vue 3、Vite、Element Plus、Pinia、Vue Router 和 Axios，登录与权限契约复用 `ruoyi-fastapi-backend`，但不直接导入 `ruoyi-fastapi-frontend/src` 源码。

首期只允许已登录员工从系统内待办参评，不提供公开链接、二维码、小程序、邮件或短信参评入口。
