# 内网快速部署实施计划（2026-09-07）

目标：在不改变现有项目配置和运行状态的前提下，将同见部署到 192.168.10.122，并提供可重复执行的发布命令。

设计：沿用现有 PostgreSQL Compose，固定项目名 `tongjian-prod`，独立目录 `/opt/tongjian`。两个容器 Nginx 直接绑定内网 IP 的 12680/12681；不修改宿主宝塔 Nginx、不重启 Docker 或操作系统。源码按版本保存，密钥与数据库卷跨版本持久化。远程构建先于维护窗口；失败时不切换现有应用。

技术栈：Windows PowerShell、Python 标准库、SSH/SCP、Ubuntu Bash、Docker Compose、PostgreSQL、Nginx。

设计确认：用户明确选择公司内网 HTTP，并授权关闭应用层传输加密。`docker-compose.intranet.yml` 设置 `TRANSPORT_CRYPTO_ENABLED=false`、`TRANSPORT_CRYPTO_MODE=off`，避免 HTTP 上 Web Crypto 不可用导致登录失败。保留登录鉴权和角色权限；不安装证书、不修改宿主 Nginx。

## 执行清单

- [x] 只读核实资源、容器、网络、端口和现有网站基线。现有 12580/12581 属于 Shot Grid；已有 canvas gateway 重启异常单独记录。
- [x] `deploy/remote_deploy.py` / `remote-deploy.ps1`：默认只发布 HEAD；显式工作区快照支持首次发布尚未提交的部署脚本，排除开发配置、密钥和输出，保存内容摘要。
- [x] `deploy/release.sh`：限定目标目录和 Compose 项目；锁定部署；先构建，再停止本项目写入、备份、迁移、健康检查、切换 current。
- [x] `deploy/tests/test_release_package.py`：验证源码包排除敏感/本地文件、快照标签和非法目标拒绝；先运行失败测试，再实现。
- [x] 真实服务器构建、迁移、启动，检查登录和新系统 API，对比原有容器 ID/启动时间及网站响应。
- [x] README 记录实际环境、网址、端口、密钥位置、快速部署、备份、失败处理和验证边界。

约束：不复制本地开发数据库；初次使用独立空库。首次管理员密码随机化，凭据保存在服务器受限文件中；不输出到日志。升级失败不得自动降级数据库或删除数据卷。此任务不自动提交或推送。

## 已验证结果（2026-09-07）

- 实际当前版本：`e8869336db5f-20260907T074954Z-5f11f6a43d`，基于 HEAD `e8869336db5f` 的显式工作区快照；本轮新增部署脚本和文档尚未提交，不声称已推送。
- 三个应用镜像在服务器真实构建成功。首次构建约 13 分钟，主要是依赖下载；后续缓存发布约 1 分钟（以每次日志为准，不作为性能保证）。
- 首次系统基线初始化、评价 Alembic 升级、后续重复迁移及模型完整核验通过；版本为 `20260903_08_feedback_scoring`。
- 后端、PostgreSQL、Redis 健康；两个前端容器 Nginx 配置检查通过；HTTP 12680/12681 页面、history 刷新、反向代理及服务器返回的关闭加密策略均通过。
- Playwright 真实登录：评价端进入 `/hr/projects`，管理端进入 `/index`，两端刷新均保持登录。管理端组织概览实际加载，评价列表为 0 个项目，管理端“进入评价平台”指向正确的 12681 入口。
- 已登录 `/getInfo`、`/feedback/projects` 返回业务码 200；匿名读取评价项目返回业务码 401（框架 HTTP 状态仍为 200）。
- 只初始化服务器独立空库，未导入本地员工/评价数据。管理员已随机密码初始化，演示账号已停用，初始密码及密钥文件权限 600。
- 升级备份已生成数据库 dump、文件 tar、密钥及旧版本路径。数据库备份恢复到独立临时库成功：迁移版本一致、2 个系统基线账号、0 个评价项目；临时库已删除。此为首次空库恢复演练，不能代替以后真实业务数据的定期恢复演练。
- 发布前后核对原有 17 个容器；原有正常容器未被本任务重启或替换，Canvas 网关的既有不稳定状态单独记录。Shot Grid 两个网址复查均为 200，宿主宝塔 Nginx 检查通过，配置未修改。
- 最终脚本测试 30 项通过，后端容器入口测试 9 项通过，Ruff 和差异空白检查通过。未在本次服务器上新建正式评价项目来重复全业务 E2E，业务验收历史见既有阶段文档。

## 修复的实际部署问题

1. 管理端 `package-lock.json` 被旧忽略规则排除，导致服务器 `npm ci` 缺文件。现已纳入交付范围，并在打包前检查两个前端锁文件。
2. 普通内网 HTTP 不提供 Web Crypto。经用户明确选择，通过内网 Compose 覆盖配置关闭应用层传输加密，保留鉴权；未部署证书或修改终端信任库。
3. Canvas 网关的自动重启会短暂显示 running。部署前改为连续采样，把实际观察到的既有不稳定项记录下来；仍拒绝容器被替换、消失或正常服务被重启。

## 证据位置

本地忽略目录：`output/deploy-server-2.log`（首次完整构建）、`output/deploy-server-final.log`（升级及既有网关误判）、`output/deploy-server-verified.log`（最终成功发布）、`output/deployed-admin-ready.png`、`output/deployed-feedback-ready.png`。服务器日志位于 `/opt/tongjian/logs/`，备份位于 `/opt/tongjian/backups/`；源码版本与摘要见 `/opt/tongjian/current/release-manifest.json`。凭据未写入文档或发布日志。
