# ruff: noqa: PLR2004

import os
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import HTTPException, Request
from sqlalchemy import select

from common.aspect.data_scope import GetDataScope
from common.context import RequestContext
from module_admin.entity.do.dept_do import SysDept
from module_admin.entity.do.role_do import SysRole, SysRoleDept
from module_admin.entity.do.user_do import SysUser
from module_feedback.service.schema_service import FEEDBACK_SCHEMA_REVISION, FeedbackSchemaService
from tests.module_feedback.service.test_p5_publication_flow_postgresql import create_test_session_factory


def user_scope(user: Any, roles: list[Any], *, admin: bool = False, dept_id: int | None = None) -> Any:
    principal = SimpleNamespace(user=SimpleNamespace(user_id=user.user_id, dept_id=dept_id, role=roles, admin=admin))
    token = RequestContext.set_current_user(principal)
    patterns = RequestContext.set_current_exclude_patterns([])
    try:
        return GetDataScope(SysUser)(
            Request({'type': 'http', 'path': '/feedback/projects', 'method': 'GET', 'headers': []})
        )
    finally:
        RequestContext.reset_current_user(token)
        RequestContext.reset_current_exclude_patterns(patterns)


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') != '1', reason='需要显式启用隔离PostgreSQL')
async def test_real_five_data_scopes_role_union_empty_roles_and_admin() -> None:
    engine, factory = create_test_session_factory()
    marker = uuid.uuid4().hex[:10]
    try:
        async with factory() as db:
            # 全部夹具只在本事务可见，结束回滚，不改变已有组织或用户。
            parent = SysDept(dept_name=f'P9父部门{marker}', ancestors='0', status='0', del_flag='0')
            external = SysDept(dept_name=f'P9外部门{marker}', ancestors='0', status='0', del_flag='0')
            db.add_all([parent, external])
            await db.flush()
            child = SysDept(
                parent_id=parent.dept_id,
                ancestors=f'0,{parent.dept_id}',
                dept_name=f'P9子部门{marker}',
                status='0',
                del_flag='0',
            )
            db.add(child)
            await db.flush()
            users = [
                SysUser(
                    dept_id=dept.dept_id,
                    user_name=f'p9_scope_{marker}_{i}',
                    nick_name='范围验收',
                    status='0',
                    del_flag='0',
                )
                for i, dept in enumerate((parent, child, external))
            ]
            custom = SysRole(
                role_name='P9自定义范围', role_key=f'p9_scope_{marker}', role_sort=1, data_scope='2', status='0'
            )
            db.add_all([*users, custom])
            await db.flush()
            db.add(SysRoleDept(role_id=custom.role_id, dept_id=child.dept_id))
            await db.flush()
            ids = [user.user_id for user in users]

            def role(value: str) -> SimpleNamespace:
                return SimpleNamespace(role_id=custom.role_id, data_scope=value)

            cases = [
                ([role('1')], parent.dept_id, False, ids),
                ([role('2')], parent.dept_id, False, ids[1:2]),
                ([role('3')], parent.dept_id, False, ids[:1]),
                ([role('4')], parent.dept_id, False, ids[:2]),
                ([role('5')], parent.dept_id, False, ids[:1]),
                ([role('2'), role('5')], parent.dept_id, False, ids[:2]),
                ([], parent.dept_id, False, []),
                ([role('unknown')], parent.dept_id, False, []),
                ([role('3')], None, False, []),
                ([role('4')], None, False, []),
                ([], None, True, ids),
            ]
            for roles, dept_id, admin, expected in cases:
                scope = user_scope(users[0], roles, dept_id=dept_id, admin=admin)
                visible = list(await db.scalars(select(SysUser.user_id).where(SysUser.user_id.in_(ids), scope)))
                assert sorted(visible) == sorted(expected), (roles, dept_id, admin)
            await db.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') != '1', reason='需要显式启用隔离PostgreSQL')
async def test_health_verifies_real_migration_head_and_result_precision() -> None:
    engine, factory = create_test_session_factory()
    try:
        async with factory() as db:
            assert (await FeedbackSchemaService.health(db))['schemaRevision'] == FEEDBACK_SCHEMA_REVISION
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('revisions', [None, [], ['unknown-revision']])
async def test_health_rejects_missing_or_unknown_migration_history(revisions: list[str] | None) -> None:
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=revisions is not None), scalars=AsyncMock(return_value=revisions)
    )
    with pytest.raises(HTTPException) as error:
        await FeedbackSchemaService.health(db)
    assert error.value.status_code == 503
    assert error.value.detail['code'] == 'FEEDBACK_SCHEMA_NOT_READY'


def test_health_revision_matches_repository_head() -> None:
    assert ScriptDirectory.from_config(Config('alembic.ini')).get_current_head() == FEEDBACK_SCHEMA_REVISION
