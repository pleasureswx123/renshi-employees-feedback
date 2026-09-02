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
11. [P4完整问卷设计器与指标技术预检](./11-p4-questionnaire-designer-precheck.md)

## 文档维护规则

- 产品范围发生变化时，更新产品基线、MVP范围和决策记录。
- 状态、提交规则或计分公式发生变化时，更新领域模型与数据库文档。
- 新增或调整工程文件时，更新计划文件清单。
- 任务开始、完成、阻塞或取消时，更新实施路线图中的任务状态和阶段验收记录。
- 开始实现后，用实际文件路径替换计划文件清单中的“计划”标记。
- 页面原型只作为交互参考，业务规则以本目录文档和后端约束为准。

## 当前阶段

截至2026-09-02，P0至P4已经完成并通过阶段门禁；下一步是P5“人员关系、发布冻结与任务生成”的决策收口与技术预检：

- 工程边界、首期范围、计分、权限和数据模型关键决策已经书面收口。
- `feedback-frontend` 已接通RuoYi登录、当前用户、退出、权限和传输加密契约，并建立HR/员工双工作台。
- 后端 `module_feedback` 已建立13张评价领域表、SQLAlchemy实体、异步DAO和状态机服务。
- P3已完成准备阶段项目CRUD和单选题垂直切片；P4在同一聚合草稿协议上扩展为五题型、多页、排序/跨页/复制、受限富文本、指标与绑定。
- P4新增`20260902_03_feedback_designer`迁移，已完成带既有页面的P3→P4→P3→P4往返；13张表、184个字段中文注释和SQLAlchemy模型契约通过真实PostgreSQL核验。
- 后端真实PostgreSQL全量63项、前端9个文件32项和Playwright 4项测试全部通过；生产构建、Ruff检查和格式检查通过。
- 真实浏览器已验证登录、创建项目、配置两页五题型/富文本/指标、保存PostgreSQL、刷新恢复、键盘滑动、电脑/手机预览和删除项目闭环；预览未生成答卷或答案。
- P4只完成准备阶段问卷和指标草稿；人员关系、发布冻结与任务生成仍未实现，属于P5，员工答题仍属于P6。
- P0至P4执行证据见[实施路线图阶段验收记录](./09-implementation-roadmap.md)，P4技术协议及实现复核见[技术预检](./11-p4-questionnaire-designer-precheck.md)。
