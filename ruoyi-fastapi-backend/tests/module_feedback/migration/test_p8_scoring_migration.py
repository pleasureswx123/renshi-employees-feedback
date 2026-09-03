"""在真实PostgreSQL事务内验证计分精度迁移及降级保护，不改动外部数据。"""

import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from tests.module_feedback.service.test_p5_publication_flow_postgresql import create_test_session_factory


def migration_module() -> ModuleType:
    path = Path(__file__).parents[3] / 'alembic/versions/2026_09_03_1000-20260903_08_feedback_scoring.py'
    spec = importlib.util.spec_from_file_location('p8_scoring_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') != '1', reason='需要显式启用隔离PostgreSQL')
async def test_migration_preserves_exact_numeric_and_rejects_lossy_downgrade() -> None:
    engine, _ = create_test_session_factory()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                # 临时表同名遮蔽正式表，执行实际迁移函数与PostgreSQL DDL。
                await connection.execute(
                    text('CREATE TEMP TABLE fb_score_result (score numeric(12,4), effective_weight numeric(12,4))')
                )
                await connection.execute(text('INSERT INTO fb_score_result VALUES (83.1234, 62.5000)'))

                def run_upgrade(sync_connection: Any) -> None:
                    migration = migration_module()
                    migration.op = Operations(MigrationContext.configure(sync_connection))
                    migration.upgrade()

                def run_downgrade(sync_connection: Any) -> None:
                    migration = migration_module()
                    migration.op = Operations(MigrationContext.configure(sync_connection))
                    migration.downgrade()

                await connection.run_sync(run_upgrade)
                await connection.run_sync(run_downgrade)
                await connection.run_sync(run_upgrade)
                exact = '33.333333333333333333333333333333333333333333333333'
                await connection.execute(
                    text('INSERT INTO fb_score_result VALUES (CAST(:score AS numeric), 100)'), {'score': exact}
                )
                value = await connection.scalar(text('SELECT score::text FROM fb_score_result ORDER BY score LIMIT 1'))
                assert value == exact
                with pytest.raises(RuntimeError, match='拒绝损失精度'):
                    await connection.run_sync(run_downgrade)
                assert (
                    await connection.scalar(text('SELECT score::text FROM fb_score_result ORDER BY score LIMIT 1'))
                    == exact
                )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
