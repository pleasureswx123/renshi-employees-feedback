# PostgreSQL 生产部署

## 交付结构

`docker-compose.pg.yml` 部署管理前端、评价前端、唯一业务后端、PostgreSQL 17、Redis 7.4，以及一次性 `feedback-migrate` 任务。

启动顺序为数据库/Redis健康 → Alembic升级及完整评价结构核验成功 → 后端启动并健康 → 两个前端启动。迁移任务失败会阻止后端启动；后端每次启动也只读核验结构，避免跳过迁移运行。依赖条件采用 Docker 官方的 [Compose启动顺序](https://docs.docker.com/compose/how-tos/startup-order/) 契约。

后端配置复用 `DB_DEFAULT_SOURCE` / `DB_SOURCES`。容器入口仅负责把文件密钥组装到既有配置，不建立平行数据库或认证体系。生产默认关闭重载、SQL echo、可选 AI 插件和外部 IP 地理位置查询。

## 首次部署

在仓库根目录执行。以下命令用于 Linux 容器；需要 Docker Engine 和支持依赖完成条件的 Docker Compose v2。执行位置可以是 Linux 服务器或 Docker Desktop 的 Linux 容器环境。

1. 按后端 PostgreSQL 依赖准备 Python 环境，生成部署专用密钥：

```bash
python ruoyi-fastapi-backend/scripts/feedback_deploy_init.py
```

Windows 本地已有虚拟环境时改用：

```powershell
.\ruoyi-fastapi-backend\.venv\Scripts\python.exe ruoyi-fastapi-backend/scripts/feedback_deploy_init.py
```

工具生成 `deploy/secrets/` 下的数据库密码、Redis密码、持久JWT密钥、RSA公私钥。若目录已存在则拒绝覆盖，避免重启时意外轮换密钥。目录及 `.env.deploy` 已被 Git 忽略；密钥不得提交、复制进镜像或打印到日志。Linux 默认目录权限700、文件600；Windows需由部署管理员限制目录ACL。密钥目录需独立安全备份。

2. 复制根目录 `.env.deploy.example` 为 `.env.deploy`，填写 `FEEDBACK_APP_URL`。

| 变量 | 说明 |
|---|---|
| `FEEDBACK_APP_URL` | 用户实际访问评价平台的完整HTTP(S)地址，必填；写入管理端构建产物。当前静态路由按域名根路径部署，推荐独立域名 |
| `WEB_BIND_ADDRESS` | 默认127.0.0.1，供宿主TLS代理访问；仅在明确内网访问边界后调整 |
| `ADMIN_PORT` / `FEEDBACK_PORT` | 默认12580 / 12581 |
| `POSTGRES_DB` | 默认 `ruoyi_feedback_prod`；首次初始化后不要通过改名切换现有数据库 |
| `FEEDBACK_SECRETS_DIR` | 默认 `./deploy/secrets`，相对于Compose文件所在目录 |
| `APP_WORKERS` | 默认1；多进程共享同一JWT及传输密钥 |
| `RELEASE_TAG` | 镜像标签，正式部署建议填写本次提交号，便于回退与追踪 |

密码通过 [Compose secrets文件挂载](https://docs.docker.com/compose/how-tos/use-secrets/) 授予相应服务；`.env.deploy` 仅包含非敏感部署参数。该方式是本机文件挂载，并非加密保管服务，仍需保护宿主密钥文件。

3. 校验、构建并启动：

```bash
docker compose --env-file .env.deploy -f docker-compose.pg.yml config --quiet
docker compose --env-file .env.deploy -f docker-compose.pg.yml up -d --build
docker compose --env-file .env.deploy -f docker-compose.pg.yml ps -a
docker compose --env-file .env.deploy -f docker-compose.pg.yml logs feedback-migrate
```

全新PostgreSQL数据卷由官方镜像自动执行系统基线SQL。该SQL包含删表语句，**只能用于新库初始化，禁止手动对已有库重放**。评价表由迁移任务升级至仓库head，并检查表、字段、注释、精度、约束和索引。

若存在无Alembic版本的旧评价表，入口拒绝自动接管；必须先按[运维手册](./17-operations-runbook.md)备份、恢复演练和严格接管。不会自动删除旧表或 `stamp head`。

4. 配置宿主TLS代理，将管理域名转发到 `127.0.0.1:12580`，评价域名转发到 `127.0.0.1:12581`。两个容器内Nginx都将 `/prod-api/` 去前缀转发到同一后端，并支持history路由刷新。

数据库、Redis和后端不映射宿主端口。只读API健康检查不替代真实登录验收。首次对正式用户开放前，应通过受控入口修改系统初始化管理员密码，配置正式HR与员工角色，再完成登录、刷新、发布、暂存、提交、完成、报告及原始答案权限验收。客户端来源地址若用于审计，需结合宿主代理地址另行配置可信代理链，不能盲信任任意转发头。

系统基线还包含演示账号，正式开放前应停用不使用的演示账号。后端Docker构建支持 `DEBIAN_MIRROR` 和 `PIP_INDEX_URL` 参数；包源连接异常时可选择部署环境允许的源，保持APT签名验证。公共依赖层单独缓存，业务代码更新不重复安装依赖。

## 已有部署升级

进入维护窗口，停止业务写入并完成备份。保持Compose项目名、`POSTGRES_DB`和密钥目录稳定。

```bash
docker compose --env-file .env.deploy -f docker-compose.pg.yml stop ruoyi-frontend feedback-frontend ruoyi-backend-pg
docker compose --env-file .env.deploy -f docker-compose.pg.yml build
docker compose --env-file .env.deploy -f docker-compose.pg.yml up -d ruoyi-pg ruoyi-redis
docker compose --env-file .env.deploy -f docker-compose.pg.yml up --no-deps --force-recreate --exit-code-from feedback-migrate feedback-migrate
docker compose --env-file .env.deploy -f docker-compose.pg.yml up -d ruoyi-backend-pg ruoyi-frontend feedback-frontend
```

只有迁移命令退出码为0才执行最后一行。升级时显式重建迁移任务，不能把上一次已完成的容器当成本次迁移成功证据。后端入口还会再次核验结构。

本次Compose从旧示例的PostgreSQL14改为17，并使用新的显式命名卷。**已有PostgreSQL14数据目录不能直接挂给17**；已有服务器应先保留原数据卷，用原版本导出并在新17库恢复验证后切换。不要为了初始化而删除已有卷。

## 持久化、备份与回退

命名卷分别保存PostgreSQL数据、Redis AOF、后端文件目录和后端日志。默认项目名 `tongjian`，卷名带项目名前缀；不要随意改变项目名。禁止把 `docker compose down -v` 当作日常更新命令。

数据库备份示例（先创建本地 `backups` 目录，每次使用不同文件名）：

```bash
docker compose --env-file .env.deploy -f docker-compose.pg.yml exec -T ruoyi-pg sh -c 'pg_dump -U postgres -Fc "$POSTGRES_DB" > /tmp/pre-upgrade.dump'
docker compose --env-file .env.deploy -f docker-compose.pg.yml cp ruoyi-pg:/tmp/pre-upgrade.dump ./backups/pre-upgrade.dump
```

正式备份文件名应带时间戳，设置受限权限和保留期，并另行备份后端文件卷与密钥。恢复到新库验证，禁止直接覆盖运行库。应用回退使用兼容当前数据库结构的镜像，不自动执行Alembic降级；已提交答卷和正式得分必须保留。

## 不使用Docker时

`.env.prod` 现为 PostgreSQL 模板、`db_echo=false`，JWT和传输密钥留空。启动前通过受控环境变量注入实际 `DB_SOURCES`、Redis凭据、持久JWT密钥和配对RSA公私钥。生产JWT缺失或不足32字符会拒绝启动，不再自动生成临时值。`.env.dev` 保持用户原有配置。

Alembic现优先采用显式 `APP_ENV`，未设置才回退到 `alembic.ini` 的配置；生产命令必须先设置 `APP_ENV=prod`。备份后运行 `python -m alembic upgrade head`，然后执行结构核验，最后 `python app.py --env prod`。前端单独构建，管理端构建前需设置 `VITE_FEEDBACK_APP_URL`。

## 验证记录

本次本地已通过部署入口与配置测试、相关CLI/代码生成测试、28项模拟接口浏览器测试及2项真实业务浏览器测试。Docker镜像和容器运行结果以本次最终回执及部署前检查报告的追加记录为准；不将配置校验描述为容器运行或服务器上线成功。

本次评价前端镜像构建及容器内Nginx校验通过；独立PostgreSQL17/Redis容器健康，系统基线与认证验证通过。后端APT包源下载出现超时重试，管理端依赖下载也未完成，已停止剩余构建并清理隔离容器和数据卷。因此完整后端/管理端镜像构建、迁移容器及整套启动验收仍须在网络可用环境执行，不能将本次修改直接标为生产已就绪。
