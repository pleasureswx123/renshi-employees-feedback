#!/usr/bin/env bash
# 仅操作同见项目；不重启宿主服务，不删除旧版本或数据卷。
set -Eeuo pipefail
umask 077
ROOT=/opt/tongjian
PROJECT=tongjian-prod
RELEASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ "$RELEASE" == "$ROOT/releases/"* && -f "$RELEASE/release-manifest.json" ]] || { echo '发布目录不合法'; exit 1; }
TAG=$(basename "$RELEASE")
[[ "$TAG" =~ ^[a-f0-9]{12}-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{10}$ ]] || exit 1
install -d -m 700 "$ROOT/shared" "$ROOT/backups" "$ROOT/logs"
exec 9>"$ROOT/shared/deploy.lock"
flock -n 9 || { echo '已有发布正在执行'; exit 1; }
exec > >(tee -a "$ROOT/logs/$TAG.log") 2>&1
trap 'echo "发布失败：保留日志、备份与旧版本；不自动降级数据库。日志：/opt/tongjian/logs/$TAG.log"' ERR
cd "$RELEASE"
export COMPOSE_PARALLEL_LIMIT=1 RELEASE_TAG="$TAG"
if [[ ! -f "$ROOT/shared/.env.deploy" ]]; then
    cat > "$ROOT/shared/.env.deploy" <<'ENV'
WEB_BIND_ADDRESS=192.168.10.122
ADMIN_PORT=12680
FEEDBACK_PORT=12681
FEEDBACK_APP_URL=http://192.168.10.122:12681
POSTGRES_DB=ruoyi_feedback_prod
FEEDBACK_SECRETS_DIR=/opt/tongjian/shared/secrets
APP_WORKERS=1
IMAGE_PREFIX=docker.m.daocloud.io/library/
DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
NPM_REGISTRY=https://registry.npmmirror.com
ENV
fi
if [[ ! -d "$ROOT/shared/secrets" ]]; then
    python3 ruoyi-fastapi-backend/scripts/feedback_deploy_init.py --directory "$ROOT/shared/secrets"
fi
cp "$ROOT/shared/.env.deploy" .env.deploy
printf '\nRELEASE_TAG=%s\n' "$TAG" >> .env.deploy
compose() { docker compose -p "$PROJECT" --env-file .env.deploy -f docker-compose.pg.yml -f docker-compose.intranet.yml "$@"; }
compose config --quiet
python3 deploy/server_guard.py capture "$ROOT/logs/$TAG-before.json"
python3 deploy/server_guard.py ports "$PROJECT" 12680 12681
echo '构建三个镜像；此时不停止正在运行的应用。'
compose build ruoyi-backend-pg
compose build ruoyi-frontend
compose build feedback-frontend
compose pull ruoyi-pg ruoyi-redis
OLD=$(readlink -f "$ROOT/current" || true)
EXISTING_DB=$(compose ps -aq ruoyi-pg)
if [[ -n "$EXISTING_DB" ]]; then
    BACKUP="$ROOT/backups/$TAG"
    install -d -m 700 "$BACKUP"
    compose stop ruoyi-frontend feedback-frontend ruoyi-backend-pg
    compose up -d --wait --wait-timeout 180 ruoyi-pg ruoyi-redis
    compose exec -T ruoyi-pg sh -c 'pg_dump -U postgres -Fc "$POSTGRES_DB"' > "$BACKUP/database.dump"
    test -s "$BACKUP/database.dump"
    compose exec -T ruoyi-pg pg_restore -l < "$BACKUP/database.dump" > "$BACKUP/database-toc.txt"
    docker run --rm --network none -v "${PROJECT}_backend_files:/data:ro" \
        --entrypoint tar "tongjian-backend:$TAG" -C /data -czf - . > "$BACKUP/files.tar.gz"
    cp -a "$ROOT/shared/secrets" "$BACKUP/secrets"
    if [[ -n "$OLD" && -d "$OLD" ]]; then
        cp "$OLD/.env.deploy" "$BACKUP/previous.env.deploy"
        printf '%s\n' "$OLD" > "$BACKUP/previous-release"
    fi
fi
compose up -d --wait --wait-timeout 180 ruoyi-pg ruoyi-redis
compose run --rm --no-deps feedback-migrate migrate
# 首次初始化在开放前执行；不会在普通升级时重置密码。
if [[ ! -f "$ROOT/shared/bootstrap-complete" ]]; then
    compose run --rm --no-deps -v "$ROOT/shared:/bootstrap" feedback-migrate exec python -m scripts.feedback_bootstrap_admin
fi
# 已显式执行本次迁移，启动时不复用旧迁移容器的完成状态。
compose up -d --no-deps --wait --wait-timeout 180 ruoyi-backend-pg
compose up -d --no-deps ruoyi-frontend feedback-frontend
python3 deploy/server_guard.py health 192.168.10.122 12680 12681
python3 deploy/server_guard.py compare "$ROOT/logs/$TAG-before.json"
ln -sfn "$RELEASE" "$ROOT/current"
compose ps -a
echo "发布验证通过：$TAG"
echo '管理端：http://192.168.10.122:12680/；评价端：http://192.168.10.122:12681/'
