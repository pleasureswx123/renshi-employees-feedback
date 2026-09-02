import json

import pytest

from scripts.feedback_p0_database_precheck import (
    build_command_env,
    build_source_payload,
    sanitize_text,
    validate_database_name,
)


def test_validate_database_name_accepts_scoped_names() -> None:
    assert (
        validate_database_name('ruoyi_feedback_dev', suffix='_dev', source_database='ruoyi-fastapi')
        == 'ruoyi_feedback_dev'
    )
    assert (
        validate_database_name('ruoyi_feedback_test', suffix='_test', source_database='ruoyi-fastapi')
        == 'ruoyi_feedback_test'
    )


@pytest.mark.parametrize(
    ('name', 'suffix'),
    [
        ('ruoyi-fastapi', '_dev'),
        ('ruoyi_feedback_test', '_dev'),
        ('postgres', '_test'),
        ('RUOYI_FEEDBACK_DEV', '_dev'),
    ],
)
def test_validate_database_name_rejects_unscoped_names(name: str, suffix: str) -> None:
    with pytest.raises(ValueError):
        validate_database_name(name, suffix=suffix, source_database='ruoyi-fastapi')


def test_build_source_payload_only_changes_database_name() -> None:
    payload = build_source_payload('ruoyi_feedback_test')

    assert payload['db_database'] == 'ruoyi_feedback_test'
    assert payload['db_type'] == 'postgresql'
    assert payload['db_required'] is True
    assert json.dumps(payload)


def test_build_command_env_overrides_database_and_redis_without_changing_global_environment() -> None:
    command_env = build_command_env('ruoyi_feedback_test', redis_database=3)
    sources = json.loads(command_env['DB_SOURCES'])

    assert sources[command_env['DB_DEFAULT_SOURCE']]['db_database'] == 'ruoyi_feedback_test'
    assert command_env['REDIS_DATABASE'] == '3'


def test_sanitize_text_masks_database_password() -> None:
    payload = build_source_payload('ruoyi_feedback_test')
    password = payload['db_password']

    if password:
        assert password not in sanitize_text(f'postgresql://postgres:{password}@localhost/db')
        assert '******' in sanitize_text(f'postgresql://postgres:{password}@localhost/db')
    else:
        assert sanitize_text('无密码配置') == '无密码配置'
