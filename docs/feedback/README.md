# Feedback 项目文档索引

本目录保存员工反馈与 360° 评价平台的产品、架构和实现基线。开始编码前，应按以下顺序阅读：

1. [产品基线](./01-product-baseline.md)
2. [架构与工程边界](./02-architecture-and-boundaries.md)
3. [领域模型与状态机](./03-domain-model-and-state-machine.md)
4. [PostgreSQL 数据设计](./04-postgresql-data-design.md)
5. [计划文件清单](./05-implementation-file-map.md)
6. [首期范围与验收标准](./06-mvp-scope-and-acceptance.md)
7. [代码生成器使用说明](./07-code-generator-usage.md)
8. [决策记录与待确认事项](./08-decisions-and-open-questions.md)
9. [分阶段实施路线图与可执行任务清单](./09-implementation-roadmap.md)
10. [P2领域表与字段字典](./10-p2-field-dictionary.md)

## 文档维护规则

- 产品范围发生变化时，更新产品基线、MVP范围和决策记录。
- 状态、提交规则或计分公式发生变化时，更新领域模型与数据库文档。
- 新增或调整工程文件时，更新计划文件清单。
- 任务开始、完成、阻塞或取消时，更新实施路线图中的任务状态和阶段验收记录。
- 开始实现后，用实际文件路径替换计划文件清单中的“计划”标记。
- 页面原型只作为交互参考，业务规则以本目录文档和后端约束为准。

## 当前阶段

P0“决策收口与技术预检”、P1“工程基线与登录权限”和 P2“领域骨架与PostgreSQL迁移”已经于 2026-09-02 完成并通过阶段门禁，下一执行阶段为 P3：

- 工程边界、首期范围、计分与权限关键决策已经书面收口。
- PostgreSQL、Redis、Alembic、传输加密、基础登录和代码生成真实链路已经完成预检。
- `feedback-frontend` 已建立独立 Vue 3 工程，并接通 RuoYi 登录、当前用户、退出、权限和传输加密契约。
- HR/员工双工作台、权限路由、无权限页和测试基线已经建立；当前业务页仍是边界明确的占位页。
- 后端 `module_feedback` 已注册受登录保护的 `/feedback/health` 只读入口，并建立13张评价领域表、SQLAlchemy实体、最小异步DAO和状态机服务。
- P2迁移在独立开发库和测试库升级成功；测试库完成降到P0基线再升回P2的可逆迁移验证。
- 13张表、182个字段及其中文注释、`NUMERIC(12,4)`字段、关键约束、索引和模型一致性已经由真实PostgreSQL检查。
- 前后端状态、题型、答案值、关系和结果类型枚举已经对齐。
- 项目、问卷、发布、答题、计分和报告业务API及页面仍未实现；P2只完成领域持久化骨架。
- P0至P2完整执行证据见[实施路线图阶段验收记录](./09-implementation-roadmap.md)；P2字段契约见[字段字典](./10-p2-field-dictionary.md)。
