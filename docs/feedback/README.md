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

## 文档维护规则

- 产品范围发生变化时，更新产品基线、MVP范围和决策记录。
- 状态、提交规则或计分公式发生变化时，更新领域模型与数据库文档。
- 新增或调整工程文件时，更新计划文件清单。
- 任务开始、完成、阻塞或取消时，更新实施路线图中的任务状态和阶段验收记录。
- 开始实现后，用实际文件路径替换计划文件清单中的“计划”标记。
- 页面原型只作为交互参考，业务规则以本目录文档和后端约束为准。

## 当前阶段

P0决策收口与技术预检已经于2026-09-02完成，当前可以进入P1，但P1尚未开始：

- 工程边界已经确定。
- 首期范围已经确定。
- 关系权重、缺失关系计分、HR原始答案权限和首期报告形式已经书面收口。
- PostgreSQL、Redis、传输加密、基础登录和代码生成真实链路已经完成预检。
- 独立开发库`ruoyi_feedback_dev`、测试库`ruoyi_feedback_test`及Redis逻辑库2/3隔离已经验证。
- Alembic基线revision已经建立，两个独立库的`upgrade/current/history`均验证通过。
- P0-P9实施路线图和可执行任务清单已经形成，P0完整执行证据见`09-implementation-roadmap.md`第5.4节。
- `feedback-frontend` 尚未初始化。
- `module_feedback` 尚未创建。
- 业务数据库迁移尚未生成。
