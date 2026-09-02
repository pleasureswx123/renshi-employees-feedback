"""在隔离测试库验证权限增量迁移，不删除既有菜单或隐式授权。"""

import os
import uuid

import pytest
from sqlalchemy import text

from scripts.feedback_p0_database_precheck import get_current_revision, get_repository_head, run_alembic
from tests.module_feedback.service.test_p5_publication_flow_postgresql import create_test_session_factory

pytestmark = pytest.mark.skipif(
    os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') != '1', reason='仅显式启用隔离PostgreSQL时运行'
)
P6_SCHEMA = '20260902_05_feedback_answering'


@pytest.mark.asyncio
async def test_permission_migration_preserves_existing_entries_never_grants_and_protects_assigned_permissions() -> None:
    engine, factory = create_test_session_factory()
    legacy_id = None
    role_id = None
    try:
        run_alembic('ruoyi_feedback_test', 'downgrade', P6_SCHEMA)
        async with factory() as db:
            existing = await db.scalar(text("SELECT menu_id FROM sys_menu WHERE perms='feedback:task:view' LIMIT 1"))
            if existing is None:
                legacy_id = await db.scalar(
                    text(
                        'INSERT INTO sys_menu(menu_name,parent_id,path,menu_type,status,perms,create_by) '
                        "VALUES('既有评价权限',0,'#','F','0','feedback:task:view','p6-legacy-test') RETURNING menu_id"
                    )
                )
                existing = legacy_id
            before = tuple(
                (
                    await db.execute(
                        text(
                            'SELECT (SELECT count(*) FROM sys_user),(SELECT count(*) FROM sys_role),(SELECT count(*) FROM sys_role_menu)'
                        )
                    )
                ).one()
            )
            await db.commit()
        run_alembic('ruoyi_feedback_test', 'upgrade', 'head')
        run_alembic('ruoyi_feedback_test', 'upgrade', 'head')
        async with factory() as db:
            rows = (
                (await db.execute(text("SELECT menu_id FROM sys_menu WHERE perms='feedback:task:view'")))
                .scalars()
                .all()
            )
            assert rows == [existing]
            after = tuple(
                (
                    await db.execute(
                        text(
                            'SELECT (SELECT count(*) FROM sys_user),(SELECT count(*) FROM sys_role),(SELECT count(*) FROM sys_role_menu)'
                        )
                    )
                ).one()
            )
            assert after == before
            menu_id = await db.scalar(
                text(
                    "SELECT menu_id FROM sys_menu WHERE create_by='feedback-p6-permissions' AND menu_type='F' ORDER BY menu_id LIMIT 1"
                )
            )
            assert menu_id is not None
            role_id = await db.scalar(
                text(
                    "INSERT INTO sys_role(role_name,role_key,role_sort,status) VALUES('P6迁移保护测试',:key,1,'0') RETURNING role_id"
                ),
                {'key': f'p6-migration-{uuid.uuid4().hex}'},
            )
            await db.execute(
                text('INSERT INTO sys_role_menu(role_id,menu_id) VALUES(:role,:menu)'),
                {'role': role_id, 'menu': menu_id},
            )
            await db.commit()
        with pytest.raises(RuntimeError, match='权限已授予角色'):
            run_alembic('ruoyi_feedback_test', 'downgrade', P6_SCHEMA)
        assert get_current_revision('ruoyi_feedback_test') == get_repository_head()
        async with factory() as db:
            assert (
                await db.scalar(text('SELECT count(*) FROM sys_role_menu WHERE role_id=:role'), {'role': role_id}) == 1
            )
            await db.execute(text('DELETE FROM sys_role_menu WHERE role_id=:role'), {'role': role_id})
            await db.execute(text('DELETE FROM sys_role WHERE role_id=:role'), {'role': role_id})
            await db.commit()
            role_id = None
        run_alembic('ruoyi_feedback_test', 'downgrade', P6_SCHEMA)
        async with factory() as db:
            assert await db.scalar(text('SELECT menu_id FROM sys_menu WHERE menu_id=:id'), {'id': existing}) == existing
            assert await db.scalar(text("SELECT count(*) FROM sys_menu WHERE create_by='feedback-p6-permissions'")) == 0
    finally:
        async with factory() as db:
            if role_id is not None:
                await db.execute(text('DELETE FROM sys_role_menu WHERE role_id=:role'), {'role': role_id})
                await db.execute(text('DELETE FROM sys_role WHERE role_id=:role'), {'role': role_id})
            if legacy_id is not None:
                await db.execute(
                    text("DELETE FROM sys_menu WHERE menu_id=:id AND create_by='p6-legacy-test'"), {'id': legacy_id}
                )
            await db.commit()
        run_alembic('ruoyi_feedback_test', 'upgrade', 'head')
        await engine.dispose()
