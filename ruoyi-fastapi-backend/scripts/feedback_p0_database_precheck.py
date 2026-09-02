"""员工反馈平台P0数据库与Redis隔离预检。

脚本使用当前开发配置中的连接凭据，但不会输出凭据，也不会修改
``.env.dev``。它只允许操作明确带有 ``_dev`` 或 ``_test`` 后缀的目标库，
不会删除数据库，也不会覆盖包含未知对象的数据库。
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import subprocess
import sys
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

import psycopg2
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg2 import sql
from redis import Redis

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

config_env = importlib.import_module('config.env')
DataBaseConfig = config_env.DataBaseConfig
RedisConfig = config_env.RedisConfig

BASELINE_SQL_PATH = BACKEND_DIR / 'sql' / 'ruoyi-fastapi-pg.sql'
ALEMBIC_INI_PATH = BACKEND_DIR / 'alembic.ini'
DATABASE_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]{2,62}$')
BASELINE_OBJECTS = ('sys_user', 'sys_dept', 'list_table', 'list_column')
REDIS_MAX_DATABASE = 15


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description='员工反馈平台P0数据库与Redis隔离预检')
    parser.add_argument('--env', default='dev', help='读取的后端环境配置名称')
    parser.add_argument('--dev-database', default='ruoyi_feedback_dev', help='独立开发数据库名')
    parser.add_argument('--test-database', default='ruoyi_feedback_test', help='独立测试数据库名')
    parser.add_argument('--test-redis-database', type=int, default=3, help='测试使用的Redis逻辑库')
    parser.add_argument('--create', action='store_true', help='目标库不存在时创建，并初始化空目标库')
    parser.add_argument('--yes', action='store_true', help='确认允许创建和初始化目标库')
    return parser.parse_args()


def validate_database_name(name: str, *, suffix: str, source_database: str) -> str:
    """校验目标数据库名，防止误操作现有基础库。"""

    normalized = name.strip()
    if not DATABASE_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(f'数据库名不符合安全命名规则：{normalized!r}')
    if not normalized.endswith(suffix):
        raise ValueError(f'数据库名必须以{suffix}结尾：{normalized}')
    if normalized == source_database:
        raise ValueError(f'目标数据库不能与当前配置库相同：{normalized}')
    return normalized


def sanitize_text(value: str) -> str:
    """移除命令输出中可能出现的数据库密码。"""

    password = DataBaseConfig.default_source.db_password.get_secret_value()
    return value.replace(password, '******') if password else value


def build_source_payload(database_name: str) -> dict[str, Any]:
    """构建只供子进程使用的数据源配置。"""

    source = DataBaseConfig.default_source
    return {
        'db_type': source.db_type,
        'db_host': source.db_host,
        'db_port': source.db_port,
        'db_username': source.db_username,
        'db_password': source.db_password.get_secret_value(),
        'db_database': database_name,
        'db_echo': False,
        'db_connect_timeout': source.db_connect_timeout,
        'db_max_overflow': source.db_max_overflow,
        'db_pool_size': source.db_pool_size,
        'db_pool_recycle': source.db_pool_recycle,
        'db_pool_timeout': source.db_pool_timeout,
        'db_required': True,
    }


def build_command_env(database_name: str, *, redis_database: int | None = None) -> dict[str, str]:
    """构建数据库和Redis均隔离的子进程环境。"""

    source_name = DataBaseConfig.db_default_source
    command_env = {
        **os.environ,
        'APP_ENV': 'dev',
        'DB_DEFAULT_SOURCE': source_name,
        'DB_SOURCES': json.dumps({source_name: build_source_payload(database_name)}, ensure_ascii=False),
    }
    if redis_database is not None:
        command_env['REDIS_DATABASE'] = str(redis_database)
    return command_env


def connect_database(database_name: str, *, autocommit: bool = False) -> Any:
    """使用当前默认数据源凭据连接指定PostgreSQL数据库。"""

    source = DataBaseConfig.default_source
    connection = psycopg2.connect(
        host=source.db_host,
        port=source.db_port,
        user=source.db_username,
        password=source.db_password.get_secret_value(),
        dbname=database_name,
        connect_timeout=source.db_connect_timeout,
    )
    connection.autocommit = autocommit
    return connection


def database_exists(database_name: str) -> bool:
    """检查目标数据库是否存在。"""

    with closing(connect_database('postgres')) as connection, connection.cursor() as cursor:
        cursor.execute('SELECT 1 FROM pg_database WHERE datname = %s', (database_name,))
        return cursor.fetchone() is not None


def create_database(database_name: str) -> None:
    """创建UTF-8目标数据库，不复制当前开发库数据。"""

    connection = connect_database('postgres', autocommit=True)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL('CREATE DATABASE {} TEMPLATE template0 ENCODING %s').format(sql.Identifier(database_name)),
                ('UTF8',),
            )
    finally:
        connection.close()


def get_public_objects(database_name: str) -> set[str]:
    """读取public schema中的表和视图名称。"""

    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r', 'p', 'v', 'm')
                """
        )
        return {str(row[0]) for row in cursor.fetchall()}


def initialize_baseline(database_name: str) -> bool:
    """仅在目标库public schema为空时执行完整RuoYi基线SQL。"""

    existing_objects = get_public_objects(database_name)
    if all(name in existing_objects for name in BASELINE_OBJECTS):
        return False
    if existing_objects:
        unexpected = ', '.join(sorted(existing_objects)[:10])
        raise RuntimeError(f'目标库包含对象但不是完整RuoYi基线，拒绝覆盖：{database_name}；对象：{unexpected}')

    sql_text = BASELINE_SQL_PATH.read_text(encoding='utf-8')
    connection = connect_database(database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql_text)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return True


def get_repository_head() -> str:
    """读取仓库唯一Alembic head。"""

    config = Config(str(ALEMBIC_INI_PATH))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f'仓库必须只有一个Alembic head，当前为：{heads}')
    return str(heads[0])


def run_alembic(database_name: str, *arguments: str) -> str:
    """使用进程级数据库覆盖执行Alembic命令。"""

    completed = subprocess.run(
        [sys.executable, '-m', 'alembic', '-c', str(ALEMBIC_INI_PATH), *arguments],
        cwd=BACKEND_DIR,
        env=build_command_env(database_name),
        capture_output=True,
        text=True,
        check=False,
    )
    output = sanitize_text('\n'.join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part))
    if completed.returncode != 0:
        raise RuntimeError(f'Alembic命令失败（{database_name}，{" ".join(arguments)}）：{output}')
    return output


def run_app_doctor(database_name: str, *, redis_database: int) -> dict[str, Any]:
    """使用隔离配置运行项目自带的应用诊断。"""

    completed = subprocess.run(
        [sys.executable, '-m', 'cli.main', 'app', 'doctor', '--env=dev', '--output=json'],
        cwd=BACKEND_DIR,
        env=build_command_env(database_name, redis_database=redis_database),
        capture_output=True,
        text=True,
        check=False,
    )
    output = sanitize_text('\n'.join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part))
    if completed.returncode != 0:
        raise RuntimeError(f'应用诊断失败（{database_name}，Redis {redis_database}）：{output}')
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'应用诊断未返回合法JSON（{database_name}）：{output}') from exc
    if not payload.get('ok'):
        raise RuntimeError(f'应用诊断未通过（{database_name}）：{output}')
    return {
        'database': database_name,
        'redisDatabase': redis_database,
        'databaseOk': bool(payload.get('database', {}).get('ok')),
        'redisOk': bool(payload.get('redis', {}).get('ok')),
        'cryptoOk': bool(payload.get('crypto', {}).get('ok')),
    }


def get_current_revision(database_name: str) -> str | None:
    """读取目标数据库当前Alembic revision。"""

    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute('SELECT version_num FROM alembic_version')
        row = cursor.fetchone()
        return str(row[0]) if row else None


def verify_database(database_name: str, *, allow_initialize: bool) -> dict[str, Any]:
    """创建或复用目标库，执行基线初始化和Alembic验证。"""

    created = False
    if not database_exists(database_name):
        if not allow_initialize:
            raise RuntimeError(f'目标数据库不存在；如需创建请显式传入--create --yes：{database_name}')
        create_database(database_name)
        created = True

    objects_before = get_public_objects(database_name)
    initialized = False
    if not all(name in objects_before for name in BASELINE_OBJECTS):
        if not allow_initialize:
            raise RuntimeError(f'目标数据库尚未初始化RuoYi基线：{database_name}')
        initialized = initialize_baseline(database_name)

    run_alembic(database_name, 'upgrade', 'head')
    current_output = run_alembic(database_name, 'current')
    history_output = run_alembic(database_name, 'history')
    current_revision = get_current_revision(database_name)
    repository_head = get_repository_head()
    objects_after = get_public_objects(database_name)
    missing_objects = sorted(set(BASELINE_OBJECTS) - objects_after)
    if missing_objects:
        raise RuntimeError(f'目标数据库缺少基线对象：{database_name} -> {missing_objects}')
    if current_revision != repository_head:
        raise RuntimeError(
            f'目标数据库revision与仓库head不一致：{database_name} -> {current_revision} != {repository_head}'
        )

    return {
        'database': database_name,
        'created': created,
        'baselineInitialized': initialized,
        'baselineObjectsVerified': list(BASELINE_OBJECTS),
        'alembicRevision': current_revision,
        'alembicCurrentVerified': repository_head in current_output,
        'alembicHistoryVerified': repository_head in history_output,
    }


def verify_redis_isolation(test_database: int) -> dict[str, Any]:
    """验证开发与测试Redis逻辑库可连接且键空间隔离。"""

    dev_database = RedisConfig.redis_database
    if test_database == dev_database:
        raise ValueError('测试Redis逻辑库不能与开发逻辑库相同')
    if not 0 <= test_database <= REDIS_MAX_DATABASE:
        raise ValueError(f'测试Redis逻辑库必须位于0到{REDIS_MAX_DATABASE}之间')

    connection_options = {
        'host': RedisConfig.redis_host,
        'port': RedisConfig.redis_port,
        'username': RedisConfig.redis_username or None,
        'password': RedisConfig.redis_password or None,
        'decode_responses': True,
    }
    dev_client = Redis(db=dev_database, **connection_options)
    test_client = Redis(db=test_database, **connection_options)
    probe_key = f'feedback:p0:isolation:{uuid.uuid4()}'
    try:
        dev_ping = bool(dev_client.ping())
        test_ping = bool(test_client.ping())
        test_client.set(probe_key, 'test-only', ex=30)
        isolated = dev_client.get(probe_key) is None and test_client.get(probe_key) == 'test-only'
    finally:
        test_client.delete(probe_key)
        dev_client.close()
        test_client.close()
    if not isolated:
        raise RuntimeError('Redis开发与测试逻辑库隔离验证失败')
    return {
        'devDatabase': dev_database,
        'testDatabase': test_database,
        'devPing': dev_ping,
        'testPing': test_ping,
        'keyspaceIsolated': isolated,
    }


def main() -> int:
    """执行P0数据库和Redis预检。"""

    args = parse_args()
    source_database = DataBaseConfig.default_source.db_database
    allow_initialize = bool(args.create and args.yes)
    if args.create and not args.yes:
        raise ValueError('创建或初始化数据库必须同时传入--yes')

    dev_database = validate_database_name(args.dev_database, suffix='_dev', source_database=source_database)
    test_database = validate_database_name(args.test_database, suffix='_test', source_database=source_database)
    if dev_database == test_database:
        raise ValueError('开发数据库和测试数据库不能相同')

    database_results = [
        verify_database(dev_database, allow_initialize=allow_initialize),
        verify_database(test_database, allow_initialize=allow_initialize),
    ]
    redis_result = verify_redis_isolation(args.test_redis_database)
    payload = {
        'ok': True,
        'sourceDatabaseChanged': False,
        'sourceDatabase': source_database,
        'databases': database_results,
        'databaseIsolated': dev_database != test_database,
        'redis': redis_result,
        'appDoctor': [
            run_app_doctor(dev_database, redis_database=RedisConfig.redis_database),
            run_app_doctor(test_database, redis_database=args.test_redis_database),
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': sanitize_text(str(exc))}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from None
