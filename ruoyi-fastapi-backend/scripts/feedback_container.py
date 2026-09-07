"""生产容器入口：读取文件密钥、串行迁移、只读核验后启动应用。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from urllib.request import urlopen

BACKEND_DIR = Path(__file__).resolve().parents[1]


class DeploymentConfigurationError(ValueError):
    """可以直接展示给运维的配置检查错误，不包含凭据。"""


def read_secret(environment: dict[str, str], key: str) -> str:
    """文件配置优先，缺少密钥时拒绝启动，不生成临时生产密钥。"""
    path = environment.get(f'{key}_FILE')
    value = Path(path).read_text(encoding='utf-8').strip() if path else environment.get(key, '').strip()
    if not value:
        raise DeploymentConfigurationError(f'必须配置 {key} 或 {key}_FILE')
    return value


def production_environment(environment: dict[str, str]) -> dict[str, str]:
    """密码通过 JSON 编码进入既有数据源契约，支持引号等特殊字符。"""
    result = dict(environment)
    password = read_secret(result, 'FEEDBACK_DB_PASSWORD')
    source = {
        'db_type': 'postgresql',
        'db_host': result.get('FEEDBACK_DB_HOST', 'ruoyi-pg'),
        'db_port': int(result.get('FEEDBACK_DB_PORT', '5432')),
        'db_username': result.get('FEEDBACK_DB_USER', 'postgres'),
        'db_password': password,
        'db_database': result.get('FEEDBACK_DB_NAME', 'ruoyi_feedback_prod'),
        'db_echo': False,
        'db_required': True,
    }
    result.update(APP_ENV='prod', APP_RELOAD='false', DB_DEFAULT_SOURCE='primary')
    result['DB_SOURCES'] = json.dumps({'primary': source}, ensure_ascii=False)
    for key in ('REDIS_PASSWORD', 'JWT_SECRET_KEY', 'TRANSPORT_CRYPTO_PUBLIC_KEY', 'TRANSPORT_CRYPTO_PRIVATE_KEY'):
        result[key] = read_secret(result, key)
    if len(result['JWT_SECRET_KEY']) < 32:  # noqa: PLR2004
        raise DeploymentConfigurationError('生产 JWT 密钥至少需要32个字符')
    result.setdefault('APP_DEFAULT_ENABLED_PLUGINS', '')
    result.setdefault('APP_ROOT_PATH', '/prod-api')
    return result


def check_migration_source(connection: object) -> None:
    """无版本的旧评价库必须走备份接管流程，禁止自动覆盖或 stamp。"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.sys_user'), to_regclass('public.alembic_version')")
        system_table, version_table = cursor.fetchone()
        if system_table is None:
            raise DeploymentConfigurationError('系统基线尚未初始化，请先初始化全新数据库')
        cursor.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND left(table_name,3)='fb_'"
        )
        table_count = cursor.fetchone()[0]
        if version_table is not None:
            cursor.execute('SELECT version_num FROM alembic_version')
            revisions = cursor.fetchall()
        else:
            revisions = []
        if table_count and not revisions:
            raise DeploymentConfigurationError('发现无迁移版本的旧评价库，请先按运维手册备份并接管')


def verify() -> None:
    # 密钥注入后才加载应用配置，禁止提前导入。
    from config.env import DataBaseConfig  # noqa: PLC0415
    from scripts.feedback_p2_schema_verify import verify_schema  # noqa: PLC0415

    verify_schema(DataBaseConfig.default_source.db_database)
    print('评价数据库结构核验通过', flush=True)


def migrate() -> None:
    from config.env import DataBaseConfig  # noqa: PLC0415
    from scripts.feedback_p0_database_precheck import connect_database  # noqa: PLC0415

    with closing(connect_database(DataBaseConfig.default_source.db_database)) as connection:
        check_migration_source(connection)
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], check=True)
    verify()


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else 'serve'
    if action == 'health':
        with urlopen('http://127.0.0.1:9099/transport/crypto/frontend-config', timeout=5) as response:
            payload = json.load(response)
            if payload.get('code') != 200:  # noqa: PLR2004
                raise ValueError('应用尚未就绪')
        return
    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))
    os.environ.update(production_environment(dict(os.environ)))
    if action == 'migrate':
        migrate()
    elif action == 'verify':
        verify()
    elif action == 'serve':
        verify()
        os.execv(sys.executable, [sys.executable, 'app.py', '--env', 'prod'])
    elif action == 'exec' and sys.argv[2:]:
        os.execvp(sys.argv[2], sys.argv[2:])
    else:
        raise ValueError('入口仅支持 migrate、verify、serve、health、exec')


if __name__ == '__main__':
    try:
        main()
    except DeploymentConfigurationError as exc:
        print(f'生产配置检查失败：{exc}', file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as exc:
        # 不输出连接字符串、密码或完整异常栈；子命令保留其已有脱敏日志。
        print(f'生产入口失败（{type(exc).__name__}），请检查密钥文件、数据库基线及迁移日志', file=sys.stderr)
        raise SystemExit(1) from None
