"""在本次独立创建的数据库上验证真实生产迁移入口。"""

import os
import subprocess
import sys
import uuid
from contextlib import closing
from pathlib import Path

import pytest
from psycopg2 import sql

from config.env import DataBaseConfig
from scripts.feedback_deploy_init import initialize
from scripts.feedback_p0_database_precheck import (
    BACKEND_DIR,
    connect_database,
    create_database,
    database_exists,
    get_current_revision,
    get_repository_head,
    initialize_baseline,
)


@pytest.mark.skipif(os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') != '1', reason='需要显式启用独立PostgreSQL测试')
def test_production_entrypoint_upgrades_new_database_and_rejects_unversioned_tables(tmp_path: Path) -> None:
    name = f'ruoyi_feedback_deploy_{uuid.uuid4().hex[:12]}_test'
    assert not database_exists(name)
    source = DataBaseConfig.default_source
    directory = tmp_path / 'secrets'
    initialize(directory)
    environment = dict(os.environ)
    # 不将本机开发凭据写入生成的部署密钥目录。
    environment.update(
        FEEDBACK_DB_HOST=source.db_host,
        FEEDBACK_DB_PORT=str(source.db_port),
        FEEDBACK_DB_USER=source.db_username,
        FEEDBACK_DB_NAME=name,
        FEEDBACK_DB_PASSWORD=source.db_password.get_secret_value(),
        REDIS_PASSWORD_FILE=str(directory / 'redis_password'),
        JWT_SECRET_KEY_FILE=str(directory / 'jwt_secret'),
        TRANSPORT_CRYPTO_PUBLIC_KEY_FILE=str(directory / 'transport_public_key.pem'),
        TRANSPORT_CRYPTO_PRIVATE_KEY_FILE=str(directory / 'transport_private_key.pem'),
        PYTHONUTF8='1',
    )
    environment.pop('FEEDBACK_DB_PASSWORD_FILE', None)
    create_database(name)
    try:
        initialize_baseline(name)
        for action in ('migrate', 'migrate', 'verify'):
            result = subprocess.run(
                [sys.executable, 'scripts/feedback_container.py', action],
                cwd=BACKEND_DIR,
                env=environment,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=90,
                check=False,
            )
            # 失败回执禁止意外暴露连接密码。
            assert result.returncode == 0, result.stderr.replace(source.db_password.get_secret_value(), '<已隐藏>')
            assert get_current_revision(name) == get_repository_head()
        with closing(connect_database(name)) as connection, connection.cursor() as cursor:
            cursor.execute('DROP TABLE alembic_version')
            connection.commit()
        rejected = subprocess.run(
            [sys.executable, 'scripts/feedback_container.py', 'migrate'],
            cwd=BACKEND_DIR,
            env=environment,
            capture_output=True,
            timeout=90,
            check=False,
        )
        assert rejected.returncode != 0
        with closing(connect_database(name)) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.alembic_version')")
            assert cursor.fetchone()[0] is None
            cursor.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND left(table_name,3)='fb_'"
            )
            assert cursor.fetchone()[0] == 15  # noqa: PLR2004
    finally:
        # 只删除本用例确认原先不存在并成功创建的隔离库，不操作业务配置库。
        with closing(connect_database('postgres', autocommit=True)) as connection, connection.cursor() as cursor:
            cursor.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
