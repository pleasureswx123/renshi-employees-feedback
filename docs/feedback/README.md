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
12. [P5人员关系、发布冻结与任务生成决策收口与技术预检](./12-p5-publication-precheck.md)

## 文档维护规则

- 产品范围发生变化时，更新产品基线、MVP范围和决策记录。
- 状态、提交规则或计分公式发生变化时，更新领域模型与数据库文档。
- 新增或调整工程文件时，更新计划文件清单。
- 任务开始、完成、阻塞或取消时，更新实施路线图中的任务状态和阶段验收记录。
- 开始实现后，用实际文件路径替换计划文件清单中的“计划”标记。
- 页面原型只作为交互参考，业务规则以本目录文档和后端约束为准。

## 当前阶段

截至2026-09-02，P0至P5已经完成并通过阶段门禁；下一实施起点是`P6-01`“我的待办和项目详情API”：

- 工程边界、首期范围、计分、权限和数据模型关键决策已经书面收口。
- `feedback-frontend` 已接通RuoYi登录、当前用户、退出、权限和传输加密契约，并建立HR/员工双工作台。
- 后端 `module_feedback` 已建立14张评价领域表、SQLAlchemy实体、异步DAO和状态机服务。
- P3完成项目草稿与单选题垂直切片，P4扩展为五题型、多页、受限富文本、指标和稳定绑定的完整问卷设计器。
- P5新增`20260902_04_feedback_publication`和`fb_evaluator_selection`，完成候选人员、目标/关系/评价人聚合保存、自评派生、权威预览、组合校验、二次确认和冻结只读页面。
- 发布由后端单事务完成人员快照刷新、计分规则快照、问卷冻结、唯一任务生成和项目状态切换；幂等、双会话并发和故障回滚已由真实PostgreSQL测试覆盖。
- P4→P5→P4→P5有数据迁移往返通过；14张表、196个中文注释/模型字段、11个`NUMERIC`字段、12项关键约束和11项关键索引通过核验。
- 后端真实PostgreSQL全量78项、前端12个文件41项和Playwright 7项全部通过；生产构建、Ruff检查和格式检查通过。
- 真实浏览器与`ruoyi_feedback_test`已验证：登录→创建项目/P4问卷→配置1名目标、2名评价人和2项任务→保存刷新恢复→发布→`ACTIVE/FROZEN`→2条唯一`PENDING`任务→新标签冻结只读。
- P5不把员工占位页当作待办或答题已交付；P6将在真实`fb_assignment`基础上实现员工待办、逐人答题、暂存和提交。
- P0至P5执行证据见[实施路线图阶段验收记录](./09-implementation-roadmap.md)，P4技术协议见[P4技术预检](./11-p4-questionnaire-designer-precheck.md)，P5协议及完整验收证据见[P5技术预检](./12-p5-publication-precheck.md)。
