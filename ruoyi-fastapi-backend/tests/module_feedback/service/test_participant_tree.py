import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import true

from exceptions.exception import ServiceException
from module_admin.entity.do.dept_do import SysDept
from module_admin.entity.do.user_do import SysUser
from module_feedback.dao.publication_dao import FeedbackPublicationDao
from module_feedback.entity.vo.publication_vo import ParticipantOptionQueryModel
from module_feedback.service.publication_service import FeedbackPublicationService
from tests.module_feedback.service.test_p5_publication_flow_postgresql import create_test_session_factory


@pytest.mark.asyncio
async def test_department_tree_keeps_only_accessible_branches_and_ancestors() -> None:
    departments = [
        SimpleNamespace(dept_id=1, parent_id=0, dept_name='公司'),
        SimpleNamespace(dept_id=2, parent_id=1, dept_name='研发部'),
        SimpleNamespace(dept_id=3, parent_id=1, dept_name='其他部门'),
    ]
    scope = true()
    with (
        patch(
            'module_feedback.service.publication_service.FeedbackProjectDao.get_project_by_id_scoped',
            new=AsyncMock(return_value=object()),
        ),
        patch(
            'module_feedback.service.publication_service.FeedbackPublicationDao.participant_department_counts',
            new=AsyncMock(return_value=({2: 3, None: 1}, departments)),
        ) as query,
    ):
        result = await FeedbackPublicationService.list_participant_departments(None, 7, true(), scope)
    assert result == [
        {'deptId': 1, 'parentId': 0, 'label': '公司', 'directCount': 0},
        {'deptId': 2, 'parentId': 1, 'label': '研发部', 'directCount': 3},
        {'deptId': 0, 'parentId': None, 'label': '未分配部门', 'directCount': 1},
    ]
    query.assert_awaited_once_with(None, scope)


@pytest.mark.asyncio
async def test_inaccessible_project_cannot_read_departments() -> None:
    with (
        patch(
            'module_feedback.service.publication_service.FeedbackProjectDao.get_project_by_id_scoped',
            new=AsyncMock(return_value=None),
        ),
        pytest.raises(ServiceException),
    ):
        await FeedbackPublicationService.list_participant_departments(None, 7, true(), true())


@pytest.mark.skipif(os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') != '1', reason='需要隔离PostgreSQL测试库')
@pytest.mark.asyncio
async def test_postgresql_department_counts_and_people_share_data_scope() -> None:
    engine, factory = create_test_session_factory()
    marker = uuid.uuid4().hex[:12]
    try:
        async with factory() as db:
            root = SysDept(dept_name=f'组织树{marker}', parent_id=0, status='0', del_flag='0')
            db.add(root)
            await db.flush()
            visible = SysDept(dept_name='可见部门', parent_id=root.dept_id, status='0', del_flag='0')
            hidden = SysDept(dept_name='不可见部门', parent_id=root.dept_id, status='0', del_flag='0')
            db.add_all([visible, hidden])
            await db.flush()
            users = [
                SysUser(
                    user_name=f'tree-{marker}-{index}',
                    nick_name=f'员工{index}',
                    dept_id=dept,
                    status=status,
                    del_flag='0',
                )
                for index, (dept, status) in enumerate(
                    [(visible.dept_id, '0'), (visible.dept_id, '1'), (hidden.dept_id, '0'), (None, '0')]
                )
            ]
            db.add_all(users)
            await db.flush()
            scope = SysUser.user_id.in_([users[0].user_id, users[1].user_id, users[3].user_id])
            counts, _ = await FeedbackPublicationDao.participant_department_counts(db, scope)
            assert counts == {visible.dept_id: 1, None: 1}
            with patch(
                'module_feedback.service.publication_service.FeedbackProjectDao.get_project_by_id_scoped',
                new=AsyncMock(return_value=object()),
            ):
                tree = await FeedbackPublicationService.list_participant_departments(db, 7, true(), scope)
            assert {node['deptId'] for node in tree} == {root.dept_id, visible.dept_id, 0}
            rows, total = await FeedbackPublicationDao.list_participant_options(
                db, ParticipantOptionQueryModel(deptId=visible.dept_id), scope
            )
            assert total == 1 and rows[0][0].user_id == users[0].user_id
            rows, total = await FeedbackPublicationDao.list_participant_options(
                db, ParticipantOptionQueryModel(unassigned=True), scope
            )
            assert total == 1 and rows[0][0].user_id == users[3].user_id
            _, total = await FeedbackPublicationDao.list_participant_options(
                db, ParticipantOptionQueryModel(deptId=hidden.dept_id), scope
            )
            assert total == 0
            await db.rollback()
    finally:
        await engine.dispose()
