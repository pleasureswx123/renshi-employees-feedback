# 代码生成器使用说明

## 1. 已确认能力

RuoYi现有代码生成器支持：

- PostgreSQL元数据读取。
- PostgreSQL字段类型映射。
- SQLAlchemy DO、Pydantic VO、DAO、Service和FastAPI Controller。
- 接口权限和操作日志。
- JavaScript API。
- Vue3 + Element Plus普通CRUD、树表和主子表页面。
- 代码预览、下载和生成到指定目录。

## 2. PostgreSQL前提

生成器的PostgreSQL元数据适配依赖：

- `list_table`
- `list_column`

这两个视图定义在：

```text
ruoyi-fastapi-backend/sql/ruoyi-fastapi-pg.sql
```

如果数据库不是通过完整PostgreSQL基线初始化，必须确认这两个视图存在。

## 3. 适合使用的场景

- 简单配置表的CRUD骨架。
- 基础列表、详情、增删改查。
- 字段到SQLAlchemy和Pydantic的初始映射。
- API权限码和菜单SQL参考。
- 指标、评价关系等简单维护页面的结构参考。

## 4. 不适合生成的场景

- 问卷设计器和拖拽排序。
- 发布与不可变版本。
- 批量生成评价任务。
- 暂存、逐人提交和并发幂等。
- 项目手动完成。
- 计分、权重和缺失关系归一化。
- 报告聚合和数据权限。

这些功能必须依据领域模型手写服务、DAO查询和前端交互。

## 5. 前端生成代码限制

生成的Vue页面依赖RuoYi管理端的全局能力，例如：

- `v-hasPermi`
- `right-toolbar`
- `pagination`
- `dict-tag`
- 全局日期和下载方法

因此不能未经适配直接放入空的 `feedback-frontend`。

## 6. 推荐流程

```text
先设计实体和迁移
→ 在独立PostgreSQL开发库执行迁移
→ 确认表和全部字段中文注释完整
→ 用生成器导入表
→ 完善模块名、业务名、包路径、Element Plus模板和菜单参数
→ 预览生成代码
→ 生成到临时目录
→ 逐文件审查
→ 选择性集成骨架
→ 手写领域逻辑和测试
```

禁止直接生成到正式源码目录并覆盖文件。

## 7. 当前验证边界

### 7.1 2026-09-02真实链路预检

已验证：

- 开发配置连接到PostgreSQL，`ruoyi gen db-list`能够通过`list_table`识别`sys_user`等现有表。
- 使用临时表`p0_codegen_probe_20260902`完成了表元数据导入，4个字段均通过`list_column`读取到类型和中文注释。
- 通过现有代码生成API补齐`module_feedback`、`feedback`模块名、`probe`业务名、Element Plus模板和菜单参数后，`ruoyi gen preview 1 --env=dev --output=json`成功预览9类模板。
- `ruoyi gen export p0_codegen_probe_20260902 --env=dev --mode=zip --output-file=build/p0-codegen/p0_codegen_probe_20260902.zip --output=json --yes`成功生成10,144字节ZIP。
- ZIP只写入`ruoyi-fastapi-backend/build/p0-codegen`临时目录，包含后端Controller、DAO、DO、Service、VO、菜单SQL及前端API、列表页、详情页共9个文件。
- 预检结束后已删除临时生成元数据、临时物理表和ZIP，并再次查询确认无同名残留。

补充验证：

- 当前Python环境已安装`pytest 9.1.1`和`pytest-asyncio 1.4.0`。
- P0数据库预检、数据库CLI、Alembic revision补全、代码生成运行时和CLI契约相关测试共52项通过。
- 生成结果没有集成到正式源码，也没有执行生成代码的业务运行测试；本次只证明生成链路可用和输出边界有效，不把生成骨架描述为正式功能。

### 7.2 发现的生成器边界

真实预检发现：`ruoyi gen create-table`会先提交物理建表，再执行生成元数据导入。临时表没有表注释时，元数据导入失败，但物理表仍然保留，命令返回的错误文本为空。这说明该命令当前不是原子流程。

因此首期固定规则为：

- 评价业务正式表只由Alembic迁移创建，不使用`gen create-table`代替迁移。
- 迁移必须先补齐中文表注释和字段注释，再执行生成器导入。
- 导入前后分别查询物理表和生成元数据，失败时检查是否发生部分写入。
- 生成器输出只进入临时目录；审查完成前不得写入`module_feedback`或`feedback-frontend`正式路径。

### 7.3 生成内容取舍

| 生成内容 | 处理结论 | 原因 |
|---|---|---|
| SQLAlchemy DO、Pydantic VO字段映射 | 可选择性保留 | 可减少基础类型和字段映射重复工作，但必须补充业务约束、审计和不可变规则 |
| DAO基础查询 | 可选择性保留 | 只适合简单配置表，必须按真实查询和数据范围重写 |
| Controller权限码、日志注解 | 仅作参考 | 可参考现有公共基础设施用法，接口前缀和权限码必须按本项目矩阵复核 |
| Service CRUD | 不直接保留 | 不能承载发布、冻结、任务生成、提交、完成、计分和并发控制 |
| 菜单SQL | 仅作权限码参考 | 系统管理端菜单和评价平台固定路由边界不同 |
| 管理端Vue页面 | 不集成到`feedback-frontend` | 依赖`v-hasPermi`、`right-toolbar`、`pagination`、全局下载等管理端能力，且不是评价业务交互 |
| 生成的Excel导出接口和按钮 | 删除 | 首期已经明确不提供报告或业务数据文件导出 |
