from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from module_feedback.dao.answer_dao import FeedbackAnswerDao
from module_feedback.dao.assignment_dao import FeedbackAssignmentDao
from module_feedback.dao.project_dao import FeedbackProjectDao
from module_feedback.entity.do import FbAnswerSheet, FbProject

EXPECTED_PROJECT_LOADER_OPTIONS = 4


def build_async_session() -> MagicMock:
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_add_project_flushes_but_does_not_commit_transaction() -> None:
    db = build_async_session()
    project = FbProject(project_name='P2事务边界', owner_user_id=1)

    result = await FeedbackProjectDao.add_project(db, project)

    assert result is project
    db.add.assert_called_once_with(project)
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_project_query_explicitly_configures_relationship_loading() -> None:
    db = build_async_session()
    scalar_result = MagicMock()
    unique_result = MagicMock()
    unique_result.first.return_value = None
    scalar_result.unique.return_value = unique_result
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalar_result
    db.execute.return_value = execute_result

    assert await FeedbackProjectDao.get_project_by_id(db, 10) is None

    statement = db.execute.await_args.args[0]
    assert len(statement._with_options) == EXPECTED_PROJECT_LOADER_OPTIONS
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_for_update_queries_keep_lock_inside_service_transaction() -> None:
    db = build_async_session()
    execute_result = MagicMock()
    execute_result.scalars.return_value.first.return_value = None
    db.execute.return_value = execute_result

    assert await FeedbackProjectDao.get_project_for_update(db, 10) is None
    project_statement = db.execute.await_args.args[0]
    assert project_statement._for_update_arg is not None

    db.execute.reset_mock()
    assert await FeedbackAnswerDao.get_by_assignment_id_for_update(db, 20) is None
    sheet_statement = db.execute.await_args.args[0]
    assert sheet_statement._for_update_arg is not None
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_assignment_list_uses_async_execute_and_identity_filter() -> None:
    db = build_async_session()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []
    db.execute.return_value = execute_result

    result = await FeedbackAssignmentDao.list_evaluator_assignments(db, 7, statuses=['PENDING', 'DRAFT'])

    assert result == []
    statement = db.execute.await_args.args[0]
    compiled = str(statement.compile(compile_kwargs={'literal_binds': True}))
    assert 'fb_assignment.evaluator_user_id = 7' in compiled
    assert 'fb_assignment.status IN' in compiled
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_answer_sheet_flushes_without_committing() -> None:
    db = build_async_session()
    answer_sheet = FbAnswerSheet(assignment_id=1, project_id=1, version_id=1)

    assert await FeedbackAnswerDao.add_answer_sheet(db, answer_sheet) is answer_sheet
    db.add.assert_called_once_with(answer_sheet)
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()
