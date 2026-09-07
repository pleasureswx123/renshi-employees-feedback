#!/bin/sh
set -eu
# 密码写入私有运行配置，不进入 redis-server 的进程参数。
password="$(cat /run/secrets/redis_password)"
case "$password" in
  ''|*[!a-zA-Z0-9_-]*) echo 'Redis 密码必须使用初始化工具生成的安全字符' >&2; exit 1 ;;
esac
umask 077
printf 'appendonly yes\ndir /data\nrequirepass %s\n' "$password" > /tmp/tongjian-redis.conf
exec redis-server /tmp/tongjian-redis.conf
