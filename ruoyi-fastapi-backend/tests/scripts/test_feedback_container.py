"""验证部署入口的密钥、数据源和旧库保护边界。"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from config.env import GetConfig
from scripts.feedback_container import check_migration_source, production_environment
from scripts.feedback_deploy_init import initialize


def test_file_secrets_build_postgres_without_exposing_or_breaking_password(tmp_path: Path) -> None:
    initialize(tmp_path / 'secrets')
    mapping = {
        'FEEDBACK_DB_PASSWORD': 'db_password',
        'REDIS_PASSWORD': 'redis_password',
        'JWT_SECRET_KEY': 'jwt_secret',
        'TRANSPORT_CRYPTO_PUBLIC_KEY': 'transport_public_key.pem',
        'TRANSPORT_CRYPTO_PRIVATE_KEY': 'transport_private_key.pem',
    }
    environment = {f'{key}_FILE': str(tmp_path / 'secrets' / name) for key, name in mapping.items()}
    password = '带引号"和反斜杠\\的数据库密码'
    (tmp_path / 'secrets/db_password').write_text(password, encoding='utf-8')
    environment.update(DB_SOURCES='旧MySQL配置', APP_RELOAD='true')
    result = production_environment(environment)
    source = json.loads(result['DB_SOURCES'])['primary']
    assert source['db_type'] == 'postgresql'
    assert source['db_password'] == password
    assert source['db_echo'] is False
    assert result['APP_ENV'] == 'prod'
    assert result['APP_RELOAD'] == 'false'
    assert 'BEGIN PRIVATE KEY' in result['TRANSPORT_CRYPTO_PRIVATE_KEY']
    assert production_environment(environment)['JWT_SECRET_KEY'] == result['JWT_SECRET_KEY']
    with pytest.raises(FileExistsError):
        initialize(tmp_path / 'secrets')


def test_missing_production_secrets_rejected() -> None:
    with pytest.raises(ValueError, match='FEEDBACK_DB_PASSWORD'):
        production_environment({})


@pytest.mark.parametrize(
    ('system', 'version', 'tables', 'revisions', 'error'),
    [
        (None, None, 0, [], '系统基线'),
        ('sys_user', None, 15, [], '旧评价库'),
        ('sys_user', 'alembic_version', 15, [], '旧评价库'),
        ('sys_user', None, 0, [], None),
        ('sys_user', 'alembic_version', 15, [('20260903_08_feedback_scoring',)], None),
    ],
)
def test_migration_does_not_adopt_unversioned_business_tables(
    system: str | None, version: str | None, tables: int, revisions: list[tuple[str]], error: str | None
) -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(system, version), (tables,)]
    cursor.fetchall.return_value = revisions
    if error:
        with pytest.raises(ValueError, match=error):
            check_migration_source(connection)
    else:
        check_migration_source(connection)


def test_alembic_explicit_environment_precedes_development_ini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['alembic', 'current'])
    monkeypatch.setenv('APP_ENV', 'prod')
    monkeypatch.delenv('FEEDBACK_ENV_PROBE', raising=False)
    (tmp_path / 'alembic.ini').write_text('[settings]\nenv = dev\n', encoding='utf-8')
    (tmp_path / '.env.prod').write_text('FEEDBACK_ENV_PROBE=production\n', encoding='utf-8')
    (tmp_path / '.env.dev').write_text('FEEDBACK_ENV_PROBE=development\n', encoding='utf-8')
    assert GetConfig.parse_cli_args() == 'prod'
    assert os.environ['FEEDBACK_ENV_PROBE'] == 'production'


def test_host_production_requires_persistent_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APP_ENV', 'prod')
    monkeypatch.setenv('JWT_SECRET_KEY', '')
    with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
        GetConfig.get_jwt_config(None)
    monkeypatch.setenv('JWT_SECRET_KEY', 'a' * 64)
    assert GetConfig.get_jwt_config(None).jwt_secret_key == 'a' * 64
