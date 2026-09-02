# PostgreSQL 数据设计

## 1. 数据库决定

项目统一使用 PostgreSQL。后端已有以下支持：

- `postgresql+asyncpg` 异步驱动。
- `postgresql+psycopg2` 同步工具驱动。
- PostgreSQL字段类型映射。
- PostgreSQL代码生成元数据适配。
- PostgreSQL初始化SQL。

## 2. 命名和字段规范

- 评价业务表统一使用 `fb_` 前缀。
- 表名、字段名和索引名使用小写下划线。
- 主键使用 `BIGINT` 自增。
- 用户和部门引用使用 `BIGINT`。
- 状态使用短字符串，并在代码中定义枚举。
- 排序使用 `INTEGER`。
- 分数、权重使用 `NUMERIC(12,4)`。
- 时间沿用现有项目的 `TIMESTAMP WITHOUT TIME ZONE` 约定。
- 所有表和字段添加中文注释。

配置类表参考RuoYi审计字段：

```text
create_by   VARCHAR(64)
create_time TIMESTAMP
update_by   VARCHAR(64)
update_time TIMESTAMP
remark      VARCHAR(500)
```

答卷、答案和计算依据不使用软删除。

## 3. 计划表

| 表 | 职责 |
|---|---|
| `fb_project` | 项目状态、标题、创建、发布和完成信息 |
| `fb_questionnaire_version` | 发布冻结版本及全局问卷设置 |
| `fb_questionnaire_page` | 问卷页面和顺序 |
| `fb_question` | 题型、标题、说明、必答、分值配置和顺序 |
| `fb_question_option` | 单选选项、选项分值和附加原因设置 |
| `fb_indicator` | 指标名称、权重和顺序 |
| `fb_indicator_question` | 指标与题目的绑定关系 |
| `fb_relation` | 项目内评价关系、启停和权重 |
| `fb_project_target` | 项目被评价人快照 |
| `fb_assignment` | 评价人、被评价人、评价关系和任务状态 |
| `fb_answer_sheet` | 任务答卷、暂存、提交和原始总分 |
| `fb_answer` | 单题答案、选项、文本、附加原因和原始得分 |
| `fb_score_result` | 指标、关系和个人计算结果及计算依据 |

首期不建立模板、Excel导入、强制分布和复杂图表专用表。

## 4. PostgreSQL类型建议

- 问卷设置、题型特有配置和异构答案可使用 `JSONB`，但核心关联、状态、顺序和正式分数必须使用独立字段。
- 文本说明使用 `TEXT`。
- 简短状态和题型使用 `VARCHAR`，不使用数据库原生ENUM，便于迁移和兼容。
- 分数和权重使用 `NUMERIC`，禁止`REAL`和`DOUBLE PRECISION`作为正式结果字段。

## 5. 约束建议

至少建立：

- `fb_assignment` 的项目、评价人、被评价人、关系唯一约束。
- `fb_answer` 的答卷、题目唯一约束。
- 页面在问卷版本内的顺序唯一约束。
- 题目在页面内的顺序唯一约束。
- 指标名称在问卷版本内的适当唯一约束。
- 权重范围 `0 <= weight <= 100` 检查约束。
- 分数范围和最高分大于最低分的服务层及数据库约束。

## 6. 索引建议

围绕实际查询建立组合索引：

- 项目状态、创建时间。
- 项目创建人、部门。
- 任务评价人、任务状态。
- 任务被评价人、任务状态。
- 项目、任务状态。
- 答卷任务ID和提交时间。
- 报告项目ID、被评价人ID。

不为每一个外键字段机械创建重复索引，应根据查询计划复核。

## 7. 快照策略

发布时保存人员展示快照，包括姓名和部门名称，避免后续员工调岗或改名导致历史报告语义变化。账号引用仍保留`sys_user.user_id`。

问卷版本、任务关系和提交答案共同形成报告的可追溯输入，不依赖当前可编辑配置重新解释历史答卷。

## 8. 迁移与初始化

- 新增表通过 Alembic 迁移交付。
- PostgreSQL基础库需要包含代码生成器依赖的 `list_table` 和 `list_column` 视图。
- 初始化SQL用于全新环境；功能迭代不能只修改初始化SQL而不提供迁移。
- 开发验证使用独立数据库，不在已有数据环境中直接试验破坏性迁移。

### 8.1 开发库和测试库约定

以下是首期实施必须采用的设计约定。2026-09-02已在当前开发机完成对应数据库创建和隔离验证：

| 用途 | PostgreSQL数据库 | Redis | 生命周期 |
|---|---|---|---|
| 本地开发 | `ruoyi_feedback_dev` | 独立实例，或固定使用逻辑库2 | 保留开发数据，不由自动化测试清空 |
| 本地自动化测试 | `ruoyi_feedback_test` | 独立实例，或固定使用逻辑库3 | 允许测试前重建，只保存测试数据 |
| CI迁移测试 | 每次运行创建唯一临时数据库 | 每次运行使用独立实例或唯一命名空间 | 运行结束后清理 |

约束：

- 开发、测试和CI不得共用同一个PostgreSQL数据库。
- 测试不得连接或清空开发库；测试启动时必须校验目标库名包含明确的测试标识。
- 开发库和测试库都先执行完整RuoYi PostgreSQL基线初始化，再执行Alembic迁移。
- `.env.dev`只用于开发配置；自动化测试使用独立环境配置或进程环境变量覆盖，不修改开发配置文件。
- 密码、Token和私钥不得写入本目录文档或测试证据。

环境变量职责：

- `DB_DEFAULT_SOURCE`：指定默认数据源名称，首期继续使用`primary`。
- `DB_SOURCES`：JSON形式的数据源集合；至少配置数据库类型、主机、端口、用户名、密码、数据库名和是否必需。开发与测试必须覆盖为不同数据库名。
- `REDIS_HOST`、`REDIS_PORT`、`REDIS_USERNAME`、`REDIS_PASSWORD`：Redis连接信息。
- `REDIS_DATABASE`：Redis逻辑库；本地开发约定为2，本地自动化测试约定为3。若使用独立Redis实例，也必须保持配置显式且不能指向开发实例。
- 自动化测试覆盖配置时只输出脱敏后的主机、端口、库名和“是否已配置密码”，不得把凭据写入日志或验收记录。

实际配置入口：

- `docker-compose.pg.yml`固定使用`ruoyi_feedback_dev`。
- `ruoyi-fastapi-test/docker-compose.test.pg.yml`固定使用`ruoyi_feedback_test`和Redis逻辑库3。
- 主机模式使用`scripts/feedback_p0_database_precheck.py`通过进程环境覆盖目标库，不修改或输出`.env.dev`中的凭据。

首次创建和验证：

```powershell
cd ruoyi-fastapi-backend
python scripts\feedback_p0_database_precheck.py --env=dev --create --yes
```

后续只读复核配置和版本；该模式不会重新执行基线SQL：

```powershell
python scripts\feedback_p0_database_precheck.py --env=dev
```

脚本只允许`_dev`和`_test`后缀的目标数据库，不删除数据库，不覆盖包含未知对象的非空数据库，并对命令输出中的数据库密码做脱敏。

### 8.2 Alembic基线门禁

- 已采用“基线SQL创建完整RuoYi结构，空操作Alembic revision接管版本历史”的策略。
- 基线revision为`20260902_01_feedback_baseline`，文件位于`alembic/versions/2026_09_02_1100-20260902_01_feedback_baseline.py`。
- 该revision不重复创建或删除RuoYi系统表；`downgrade`只影响版本登记，不删除基线结构。
- 2026-09-02已在独立的`ruoyi_feedback_dev`和`ruoyi_feedback_test`执行完整基线初始化、`upgrade head`、`current`和`history`，两个库均处于唯一head。
- 后续首个`fb_`迁移必须以该revision作为`down_revision`。
- 不得只对已有数据库执行`stamp`后就宣称迁移链路可用；新环境仍必须先执行完整RuoYi PostgreSQL基线，再执行`alembic upgrade head`。
