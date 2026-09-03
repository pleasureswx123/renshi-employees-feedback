"""新建独立数据库验证完整迁移、备份恢复和接管失败的事务回滚。"""

import json
import os
import uuid
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from psycopg2 import sql
from sqlalchemy import text

from scripts import feedback_p9_migration as migration
from scripts.feedback_p0_database_precheck import connect_database, database_exists, verify_database
from scripts.feedback_p2_schema_verify import (
    insert_designer_migration_fixture,
    run_migration_cycle,
    verify_schema,
)


@pytest.mark.skipif(os.getenv('RUN_FEEDBACK_MIGRATION_TESTS') != '1', reason='需要显式允许创建并清理本次独立迁移演练库')
def test_backup_restore_adoption_and_failure_rollback(tmp_path: Path) -> None:  # noqa: PLR0915
    pg_bin = Path(os.getenv('FEEDBACK_PG_BIN', 'C:/Program Files/PostgreSQL/17/bin'))
    assert (pg_bin / ('pg_dump.exe' if os.name == 'nt' else 'pg_dump')).is_file()
    marker = uuid.uuid4().hex[:12]
    reference, legacy, restored = (f'ruoyi_feedback_p9_{marker}_{kind}_test' for kind in ('ref', 'old', 'copy'))
    assert not any(database_exists(name) for name in (reference, legacy, restored))
    owned = []
    try:
        owned.append(reference)
        assert verify_database(reference, allow_initialize=True)['created']
        assert run_migration_cycle(reference)['upgradeRevision'] == migration.P8
        verify_schema(reference)
        empty_backup = tmp_path / 'empty.dump'
        migration.backup(reference, empty_backup, pg_bin)
        owned.append(legacy)
        migration.restore(legacy, empty_backup, pg_bin)
        engine = migration.database_engine(legacy)
        try:
            with engine.begin() as connection:
                scripts = ScriptDirectory.from_config(Config(str(migration.BACKEND_DIR / 'alembic.ini')))
                # 只在刚创建且无业务数据的库里构造已知的早期混合结构。
                with Operations.context(MigrationContext.configure(connection)):
                    scripts.get_revision(migration.P4).module.downgrade()
                    scripts.get_revision(migration.P6).module.downgrade()
                    scripts.get_revision(migration.P8).module.downgrade()
                connection.execute(text('DROP TABLE alembic_version'))
        finally:
            engine.dispose()
        insert_designer_migration_fixture(legacy, f'P9迁移保留-{marker}')
        before = migration.load_snapshot(legacy)
        assert migration.audit(legacy, reference)['canAdopt']
        backup_path = tmp_path / 'existing.dump'
        metadata = migration.backup(legacy, backup_path, pg_bin)
        with pytest.raises(RuntimeError, match='拒绝覆盖'):
            migration.backup(legacy, backup_path, pg_bin)
        owned.append(restored)
        assert migration.restore(restored, backup_path, pg_bin)['restored']
        with pytest.raises(RuntimeError, match='拒绝覆盖'):
            migration.restore(restored, backup_path, pg_bin)

        real_fingerprints = migration.row_fingerprints
        calls = 0

        def fail_final_comparison(*args: object, **kwargs: object) -> tuple:
            nonlocal calls
            calls += 1
            fingerprints, identities = real_fingerprints(*args, **kwargs)
            if calls == 2:  # noqa: PLR2004
                fingerprints['fb_project']['sha256'] = '模拟迁移后数据核验失败'
            return fingerprints, identities

        with (
            patch.object(migration, 'row_fingerprints', side_effect=fail_final_comparison),
            pytest.raises(RuntimeError, match='既有行内容发生变化'),
        ):
            migration.adopt(restored, reference, metadata['schemaSha256'], backup_path)
        assert migration.load_snapshot(restored) == before
        result = migration.adopt(restored, reference, metadata['schemaSha256'], backup_path)
        assert result['preservedRows'] == metadata['dataFingerprints']
        assert result['preservedRows']['fb_project']['count'] == 1
        assert result['revision'] == migration.P8
        verify_schema(restored)
        receipt = migration.BACKEND_DIR.parent / '.tmp/p9/migration-regression.json'
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps({'rollbackVerified': True, **result}, ensure_ascii=False, indent=2), encoding='utf-8'
        )
    finally:
        # 仅清理本用例生成并确认原先不存在的数据库，不断开其他会话，也不操作配置库。
        with closing(connect_database('postgres', autocommit=True)) as connection, connection.cursor() as cursor:
            for name in reversed(owned):
                if database_exists(name):
                    cursor.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
