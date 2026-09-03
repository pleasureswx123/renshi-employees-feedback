# ruff: noqa: PLC0415, PLR2004

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import false, func, select, text, true

from exceptions.exception import ConflictException
from module_feedback.dao.employee_dao import FeedbackEmployeeDao
from module_feedback.dao.progress_dao import FeedbackProgressDao
from module_feedback.entity.do import (
    FbAnswer,
    FbAnswerSheet,
    FbAssignment,
    FbProject,
    FbProjectCompletionAudit,
    FbProjectTarget,
)
from module_feedback.entity.vo.progress_vo import ProgressQueryModel, ProjectCompleteRequestModel
from module_feedback.service.answer_service import FeedbackAnswerService
from module_feedback.service.progress_service import FeedbackProgressService, ProjectCompletionExecutionError
from tests.module_feedback.service.p6_helpers import answer_request, cleanup_p6_project, create_p6_project
from tests.module_feedback.service.test_p5_publication_flow_postgresql import create_test_session_factory

pytestmark = pytest.mark.skipif(
    os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') != '1', reason='仅显式启用隔离PostgreSQL时运行'
)


@pytest_asyncio.fixture
async def p7_context() -> Any:
    engine, factory = create_test_session_factory()
    state = None
    try:
        state = await create_p6_project(factory, extra_relation=True)
        yield factory, state
    finally:
        if state:
            await cleanup_p6_project(factory, state)
        await engine.dispose()


async def prepare_three_states(factory: Any, state: dict) -> Any:
    async with factory() as db:
        first = await FeedbackProgressService.get_precheck(db, state['project_id'], true(), true())
        assert first.summary.total_count == 5
        from module_feedback.service.employee_service import FeedbackEmployeeService

        draft_detail = await FeedbackEmployeeService.get_task(db, state['task_ids'][0], state['evaluator_id'])
        await FeedbackAnswerService.save_draft(
            db, state['task_ids'][0], state['evaluator_id'], answer_request(draft_detail, complete=False)
        )
        submitted_detail = await FeedbackEmployeeService.get_task(db, state['task_ids'][1], state['evaluator_id'])
        await FeedbackAnswerService.submit(
            db, state['task_ids'][1], state['evaluator_id'], answer_request(submitted_detail, submit=True)
        )
        return await FeedbackProgressService.get_precheck(db, state['project_id'], true(), true())


def complete_request(precheck: Any, reason: str = 'P7测试完成') -> ProjectCompleteRequestModel:
    summary = precheck.summary.model_dump(by_alias=True)
    return ProjectCompleteRequestModel.model_validate(
        {
            'projectLockVersion': precheck.project_lock_version,
            'completionReason': reason,
            'expectedSummary': {
                key: summary[key]
                for key in ('totalCount', 'submittedCount', 'draftCount', 'pendingCount', 'closedIncompleteCount')
            },
        }
    )


def model_snapshot(item: Any) -> dict[str, Any]:
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


async def wait_until_postgresql_blocked(factory: Any, backend_pid: int) -> None:
    async with asyncio.timeout(3):
        while True:
            async with factory() as monitor:
                blockers = await monitor.scalar(
                    text('SELECT cardinality(pg_blocking_pids(:backend_pid))').bindparams(backend_pid=backend_pid)
                )
            if blockers:
                return
            await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_p7_progress_real_postgresql_has_stable_pages_and_applies_target_scope(p7_context: tuple) -> None:
    factory, state = p7_context
    async with factory() as db:
        full = await FeedbackProgressService.get_progress(
            db, state['project_id'], ProgressQueryModel(pageNum=1, pageSize=100), true(), true()
        )
        page_ids: list[int] = []
        for page_num in range(1, 4):
            page = await FeedbackProgressService.get_progress(
                db,
                state['project_id'],
                ProgressQueryModel(pageNum=page_num, pageSize=2),
                true(),
                true(),
            )
            assert page.total == full.total
            page_ids.extend(row.assignment_id for row in page.rows)
        assert page_ids == [row.assignment_id for row in full.rows]
        assert len(page_ids) == len(set(page_ids)) == 5

        selected = next(
            row
            for row in full.rows
            if row.evaluator_user_id == state['evaluator_id'] and row.relation_code == 'REL_PEER'
        )
        combined = await FeedbackProgressService.get_progress(
            db,
            state['project_id'],
            ProgressQueryModel(
                evaluatorUserId=selected.evaluator_user_id,
                targetUserId=selected.target_user_id,
                relationId=selected.relation_id,
                status='PENDING',
                evaluatorKeyword=selected.evaluator_name,
                targetKeyword=selected.target_name,
                pageNum=1,
                pageSize=100,
            ),
            true(),
            true(),
        )
        assert combined.total == 1
        assert [row.assignment_id for row in combined.rows] == [selected.assignment_id]

        for query in (
            ProgressQueryModel(evaluatorKeyword='%', pageNum=1, pageSize=100),
            ProgressQueryModel(evaluatorKeyword='_', pageNum=1, pageSize=100),
            ProgressQueryModel(targetKeyword='%', pageNum=1, pageSize=100),
            ProgressQueryModel(targetKeyword='_', pageNum=1, pageSize=100),
        ):
            literal_wildcard = await FeedbackProgressService.get_progress(
                db,
                state['project_id'],
                query,
                true(),
                true(),
            )
            assert literal_wildcard.total == 0

        scoped = await FeedbackProgressService.get_progress(
            db,
            state['project_id'],
            ProgressQueryModel(pageNum=1, pageSize=100),
            true(),
            FbProjectTarget.target_user_id == state['user_ids'][0],
        )
        assert not scoped.data_scope_complete
        assert scoped.rows
        assert {row.target_user_id for row in scoped.rows} == {state['user_ids'][0]}
        precheck = await FeedbackProgressService.get_precheck(
            db,
            state['project_id'],
            true(),
            FbProjectTarget.target_user_id == state['user_ids'][0],
        )
        assert not precheck.data_scope_complete
        assert not precheck.can_complete

        with pytest.raises(HTTPException) as project_scope_error:
            await FeedbackProgressService.get_progress(
                db,
                state['project_id'],
                ProgressQueryModel(pageNum=1, pageSize=100),
                false(),
                true(),
            )
        assert project_scope_error.value.status_code == 404
        assert project_scope_error.value.detail['code'] == 'PROJECT_NOT_FOUND'

        with pytest.raises(HTTPException) as target_scope_error:
            await FeedbackProgressService.get_progress(
                db,
                state['project_id'],
                ProgressQueryModel(pageNum=1, pageSize=100),
                true(),
                false(),
            )
        assert target_scope_error.value.status_code == 404
        assert target_scope_error.value.detail['code'] == 'PROJECT_NOT_FOUND'

        full_precheck = await FeedbackProgressService.get_precheck(db, state['project_id'], true(), true())
        with pytest.raises(HTTPException) as partial_complete_error:
            await FeedbackProgressService.complete_project(
                db,
                state['project_id'],
                complete_request(full_precheck),
                state['user_ids'][0],
                'p7-user',
                true(),
                FbProjectTarget.target_user_id == state['user_ids'][0],
            )
        assert partial_complete_error.value.status_code == 403
        assert partial_complete_error.value.detail['code'] == 'PROJECT_COMPLETION_SCOPE_FORBIDDEN'


@pytest.mark.asyncio
async def test_p7_progress_read_holds_one_consistent_postgresql_snapshot_against_submit(
    p7_context: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, state = p7_context
    from module_feedback.service.employee_service import FeedbackEmployeeService

    async with factory() as db:
        detail = await FeedbackEmployeeService.get_task(db, state['task_ids'][0], state['evaluator_id'])
    submit_request = answer_request(detail, submit=True)
    read_locked = asyncio.Event()
    release_read = asyncio.Event()
    writer_started = asyncio.Event()
    writer_pid: int | None = None
    original_summarize = FeedbackProgressDao.summarize_assignments

    async def pause_after_read_locks(*args: Any, **kwargs: Any) -> dict[str, int]:
        read_locked.set()
        await release_read.wait()
        return await original_summarize(*args, **kwargs)

    monkeypatch.setattr(FeedbackProgressDao, 'summarize_assignments', pause_after_read_locks)

    async def read_progress() -> Any:
        async with factory() as db:
            return await FeedbackProgressService.get_progress(
                db,
                state['project_id'],
                ProgressQueryModel(pageNum=1, pageSize=100),
                true(),
                true(),
            )

    async def submit_answer() -> Any:
        nonlocal writer_pid
        async with factory() as db:
            writer_pid = int(await db.scalar(text('SELECT pg_backend_pid()')))
            writer_started.set()
            return await FeedbackAnswerService.submit(
                db,
                state['task_ids'][0],
                state['evaluator_id'],
                submit_request,
            )

    reader = asyncio.create_task(read_progress())
    await asyncio.wait_for(read_locked.wait(), timeout=3)
    writer = asyncio.create_task(submit_answer())
    await asyncio.wait_for(writer_started.wait(), timeout=3)
    assert writer_pid is not None
    try:
        await wait_until_postgresql_blocked(factory, writer_pid)
        assert not writer.done()
    finally:
        release_read.set()

    snapshot = await asyncio.wait_for(reader, timeout=3)
    submitted = await asyncio.wait_for(writer, timeout=3)
    assert snapshot.summary.pending_count == 5
    assert {item.status.value for item in snapshot.rows} == {'PENDING'}
    assert submitted.task.status.value == 'SUBMITTED'


@pytest.mark.asyncio
async def test_p7_precheck_read_holds_one_consistent_postgresql_snapshot_against_completion(
    p7_context: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, state = p7_context
    async with factory() as db:
        request = complete_request(await FeedbackProgressService.get_precheck(db, state['project_id'], true(), true()))
    read_locked = asyncio.Event()
    release_read = asyncio.Event()
    writer_started = asyncio.Event()
    writer_pid: int | None = None
    original_list_all = FeedbackProgressDao.list_all_assignments

    async def pause_after_read_locks(*args: Any, **kwargs: Any) -> list[Any]:
        read_locked.set()
        await release_read.wait()
        return await original_list_all(*args, **kwargs)

    monkeypatch.setattr(FeedbackProgressDao, 'list_all_assignments', pause_after_read_locks)

    async def read_precheck() -> Any:
        async with factory() as db:
            return await FeedbackProgressService.get_precheck(db, state['project_id'], true(), true())

    async def complete_project() -> Any:
        nonlocal writer_pid
        async with factory() as db:
            writer_pid = int(await db.scalar(text('SELECT pg_backend_pid()')))
            writer_started.set()
            return await FeedbackProgressService.complete_project(
                db,
                state['project_id'],
                request,
                state['user_ids'][0],
                'p7-user',
                true(),
                true(),
            )

    reader = asyncio.create_task(read_precheck())
    await asyncio.wait_for(read_locked.wait(), timeout=3)
    writer = asyncio.create_task(complete_project())
    await asyncio.wait_for(writer_started.wait(), timeout=3)
    assert writer_pid is not None
    try:
        await wait_until_postgresql_blocked(factory, writer_pid)
        assert not writer.done()
    finally:
        release_read.set()

    snapshot = await asyncio.wait_for(reader, timeout=3)
    completed = await asyncio.wait_for(writer, timeout=3)
    assert snapshot.project_status.value == 'ACTIVE'
    assert snapshot.summary.pending_count == 5
    assert snapshot.can_complete
    assert completed.project_status.value == 'COMPLETED'
    assert completed.summary.closed_incomplete_count == 5


@pytest.mark.asyncio
async def test_p7_slice_5_complete_success_closes_only_incomplete_with_one_time_and_versions(p7_context: tuple) -> None:
    factory, state = p7_context
    precheck = await prepare_three_states(factory, state)
    async with factory() as db:
        before_sheets = list(
            (
                await db.scalars(
                    select(FbAnswerSheet)
                    .where(FbAnswerSheet.project_id == state['project_id'])
                    .order_by(FbAnswerSheet.sheet_id)
                )
            ).all()
        )
        sheet_ids = [item.sheet_id for item in before_sheets]
        before_answers = list(
            (
                await db.scalars(select(FbAnswer).where(FbAnswer.sheet_id.in_(sheet_ids)).order_by(FbAnswer.answer_id))
            ).all()
        )
        sheet_snapshots = {item.sheet_id: model_snapshot(item) for item in before_sheets}
        answer_snapshots = {item.answer_id: model_snapshot(item) for item in before_answers}
        task_locks = dict(
            (
                await db.execute(
                    select(FbAssignment.assignment_id, FbAssignment.lock_version).where(
                        FbAssignment.project_id == state['project_id']
                    )
                )
            ).all()
        )
        result = await FeedbackProgressService.complete_project(
            db,
            state['project_id'],
            complete_request(precheck),
            state['user_ids'][0],
            'p7-user',
            true(),
            true(),
            request_id='p7-request-id',
            trace_id='p7-trace-id',
        )
        assert result.project_status.value == 'COMPLETED' and not result.already_completed
        assert result.summary.submitted_count == 1 and result.summary.closed_incomplete_count == 4
    async with factory() as db:
        project = await db.get(FbProject, state['project_id'])
        tasks = list(
            (
                await db.scalars(
                    select(FbAssignment)
                    .where(FbAssignment.project_id == state['project_id'])
                    .order_by(FbAssignment.assignment_id)
                )
            ).all()
        )
        assert [item.status for item in tasks].count('CLOSED_INCOMPLETE') == 4
        assert [item.status for item in tasks].count('SUBMITTED') == 1
        assert {item.closed_time for item in tasks if item.status == 'CLOSED_INCOMPLETE'} == {project.completed_time}
        assert all(
            item.lock_version == task_locks[item.assignment_id] + 1
            for item in tasks
            if item.status == 'CLOSED_INCOMPLETE'
        )
        sheets = list(
            (
                await db.scalars(
                    select(FbAnswerSheet)
                    .where(FbAnswerSheet.project_id == state['project_id'])
                    .order_by(FbAnswerSheet.sheet_id)
                )
            ).all()
        )
        answers = list(
            (
                await db.scalars(select(FbAnswer).where(FbAnswer.sheet_id.in_(sheet_ids)).order_by(FbAnswer.answer_id))
            ).all()
        )
        assert {item.sheet_id: model_snapshot(item) for item in sheets} == sheet_snapshots
        assert {item.answer_id: model_snapshot(item) for item in answers} == answer_snapshots

        audits = list(
            (
                await db.scalars(
                    select(FbProjectCompletionAudit).where(FbProjectCompletionAudit.project_id == state['project_id'])
                )
            ).all()
        )
        assert len(audits) == 1
        audit = audits[0]
        assert audit.version_id == state['version_id']
        assert audit.result == 'SUCCESS'
        assert audit.operator_user_id == state['user_ids'][0]
        assert audit.operator_name == 'p7-user'
        assert audit.request_id == 'p7-request-id'
        assert audit.trace_id == 'p7-trace-id'
        assert (
            audit.before_total_count,
            audit.before_submitted_count,
            audit.before_draft_count,
            audit.before_pending_count,
            audit.before_closed_incomplete_count,
            audit.closed_assignment_count,
        ) == (5, 1, 1, 3, 0, 4)
        assert audit.completion_reason == 'P7测试完成'
        assert audit.completed_time == project.completed_time

        repeated = await FeedbackProgressService.complete_project(
            db,
            state['project_id'],
            complete_request(precheck, '重复请求不得覆盖原因'),
            state['user_ids'][0],
            'another-user',
            true(),
            true(),
            request_id='another-request',
            trace_id='another-trace',
        )
        assert repeated.already_completed
        assert (
            await db.scalar(
                select(func.count())
                .select_from(FbProjectCompletionAudit)
                .where(FbProjectCompletionAudit.project_id == state['project_id'])
            )
            == 1
        )


@pytest.mark.asyncio
async def test_p7_completion_closes_all_p6_writes_and_keeps_every_answer_field_immutable(
    p7_context: tuple,
) -> None:
    factory, state = p7_context
    from module_feedback.service.employee_service import FeedbackEmployeeService

    async with factory() as db:
        draft_detail = await FeedbackEmployeeService.get_task(db, state['task_ids'][0], state['evaluator_id'])
        draft_request = answer_request(draft_detail, complete=False)
        closed_submit_request = answer_request(draft_detail, submit=True)
        await FeedbackAnswerService.save_draft(
            db,
            state['task_ids'][0],
            state['evaluator_id'],
            draft_request,
        )
        submitted_detail = await FeedbackEmployeeService.get_task(
            db,
            state['task_ids'][1],
            state['evaluator_id'],
        )
        submitted_draft_request = answer_request(submitted_detail, complete=False)
        repeated_submit_request = answer_request(submitted_detail, submit=True)
        await FeedbackAnswerService.submit(
            db,
            state['task_ids'][1],
            state['evaluator_id'],
            repeated_submit_request,
        )
        precheck = await FeedbackProgressService.get_precheck(db, state['project_id'], true(), true())
        await FeedbackProgressService.complete_project(
            db,
            state['project_id'],
            complete_request(precheck),
            state['user_ids'][0],
            'p7-user',
            true(),
            true(),
        )

    async with factory() as db:
        sheets = list(
            (
                await db.scalars(
                    select(FbAnswerSheet)
                    .where(FbAnswerSheet.project_id == state['project_id'])
                    .order_by(FbAnswerSheet.sheet_id)
                )
            ).all()
        )
        sheet_ids = [item.sheet_id for item in sheets]
        answers = list(
            (
                await db.scalars(select(FbAnswer).where(FbAnswer.sheet_id.in_(sheet_ids)).order_by(FbAnswer.answer_id))
            ).all()
        )
        sheet_snapshots = {item.sheet_id: model_snapshot(item) for item in sheets}
        answer_snapshots = {item.answer_id: model_snapshot(item) for item in answers}

    attempts = (
        (FeedbackAnswerService.save_draft, state['task_ids'][0], draft_request),
        (FeedbackAnswerService.submit, state['task_ids'][0], closed_submit_request),
        (FeedbackAnswerService.save_draft, state['task_ids'][1], submitted_draft_request),
        (FeedbackAnswerService.submit, state['task_ids'][1], repeated_submit_request),
    )
    for write_method, assignment_id, request in attempts:
        async with factory() as db:
            with pytest.raises(ConflictException) as exc_info:
                await write_method(db, assignment_id, state['evaluator_id'], request)
            assert exc_info.value.data['code'] == 'PROJECT_CLOSED'

    async with factory() as db:
        sheets = list(
            (
                await db.scalars(
                    select(FbAnswerSheet)
                    .where(FbAnswerSheet.project_id == state['project_id'])
                    .order_by(FbAnswerSheet.sheet_id)
                )
            ).all()
        )
        answers = list(
            (
                await db.scalars(select(FbAnswer).where(FbAnswer.sheet_id.in_(sheet_ids)).order_by(FbAnswer.answer_id))
            ).all()
        )
        assert {item.sheet_id: model_snapshot(item) for item in sheets} == sheet_snapshots
        assert {item.answer_id: model_snapshot(item) for item in answers} == answer_snapshots


@pytest.mark.asyncio
async def test_p7_slice_7_p6_p7_bidirectional_races_and_double_complete(p7_context: tuple) -> None:
    factory, state = p7_context
    precheck = await prepare_three_states(factory, state)

    async def complete(reason: str) -> Any:
        async with factory() as db:
            return await FeedbackProgressService.complete_project(
                db,
                state['project_id'],
                complete_request(precheck, reason),
                state['user_ids'][0],
                'p7-user',
                true(),
                true(),
            )

    first, second = await asyncio.gather(complete('first'), complete('second'))
    assert sorted([first.already_completed, second.already_completed]) == [False, True]
    assert first.completed_time == second.completed_time and first.completion_reason == second.completion_reason


@pytest.mark.asyncio
async def test_p7_slice_7_p7_lock_wins_and_blocks_late_p6_submit(
    p7_context: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, state = p7_context
    precheck = await prepare_three_states(factory, state)
    from module_feedback.service.employee_service import FeedbackEmployeeService

    async with factory() as db:
        detail = await FeedbackEmployeeService.get_task(db, state['task_ids'][2], state['evaluator_id'])
    submit_request = answer_request(detail, submit=True)
    lock_acquired = asyncio.Event()
    release_lock = asyncio.Event()
    original_get_project = FeedbackProgressDao.get_project_scoped

    async def hold_p7_project_lock(db: Any, project_id: int, scope: Any, *, for_update: bool = False) -> Any:
        project = await original_get_project(db, project_id, scope, for_update=for_update)
        if for_update:
            lock_acquired.set()
            await release_lock.wait()
        return project

    monkeypatch.setattr(FeedbackProgressDao, 'get_project_scoped', hold_p7_project_lock)

    async def complete() -> Any:
        async with factory() as db:
            return await FeedbackProgressService.complete_project(
                db, state['project_id'], complete_request(precheck), state['user_ids'][0], 'p7-user', true(), true()
            )

    async def submit() -> Any:
        async with factory() as db:
            return await FeedbackAnswerService.submit(db, state['task_ids'][2], state['evaluator_id'], submit_request)

    completion = asyncio.create_task(complete())
    await asyncio.wait_for(lock_acquired.wait(), timeout=2)
    submission = asyncio.create_task(submit())
    await asyncio.sleep(0.1)
    assert not submission.done()
    release_lock.set()
    assert (await completion).project_status.value == 'COMPLETED'
    with pytest.raises(ConflictException, match='已关闭'):
        await submission


@pytest.mark.asyncio
async def test_p7_slice_7_p6_lock_wins_and_makes_p7_precheck_stale(
    p7_context: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, state = p7_context
    precheck = await prepare_three_states(factory, state)
    from module_feedback.service.employee_service import FeedbackEmployeeService

    async with factory() as db:
        detail = await FeedbackEmployeeService.get_task(db, state['task_ids'][2], state['evaluator_id'])
    submit_request = answer_request(detail, submit=True)
    lock_acquired = asyncio.Event()
    release_lock = asyncio.Event()
    original_lock_context = FeedbackEmployeeDao.lock_context

    async def hold_p6_project_lock(db: Any, assignment_id: int, evaluator_id: int) -> Any:
        context = await original_lock_context(db, assignment_id, evaluator_id)
        lock_acquired.set()
        await release_lock.wait()
        return context

    monkeypatch.setattr(FeedbackEmployeeDao, 'lock_context', hold_p6_project_lock)

    async def submit() -> Any:
        async with factory() as db:
            return await FeedbackAnswerService.submit(db, state['task_ids'][2], state['evaluator_id'], submit_request)

    async def complete() -> Any:
        async with factory() as db:
            return await FeedbackProgressService.complete_project(
                db, state['project_id'], complete_request(precheck), state['user_ids'][0], 'p7-user', true(), true()
            )

    submission = asyncio.create_task(submit())
    await asyncio.wait_for(lock_acquired.wait(), timeout=2)
    completion = asyncio.create_task(complete())
    await asyncio.sleep(0.1)
    assert not completion.done()
    release_lock.set()
    assert (await submission).task.status.value == 'SUBMITTED'
    with pytest.raises(HTTPException) as exc:
        await completion
    assert exc.value.status_code == 409
    assert exc.value.detail['code'] == 'COMPLETION_PRECHECK_STALE'


@pytest.mark.asyncio
async def test_p7_slice_8_real_lock_summary_flush_and_commit_failures_roll_back_everything(
    p7_context: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, state = p7_context
    precheck = await prepare_three_states(factory, state)
    original_lock_assignments = FeedbackProgressDao.lock_assignments

    async def fail_after_real_lock(db: Any, project_id: int, version_id: int) -> Any:
        await original_lock_assignments(db, project_id, version_id)
        raise RuntimeError('lock failed')

    def fail_summary(rows: list[Any]) -> Any:
        raise RuntimeError('summary failed')

    for stage in ('assignment_lock', 'summary_before_completion', 'flush', 'commit'):
        with monkeypatch.context() as scoped_patch:
            async with factory() as db:
                if stage == 'assignment_lock':
                    scoped_patch.setattr(FeedbackProgressDao, 'lock_assignments', fail_after_real_lock)
                elif stage == 'summary_before_completion':
                    scoped_patch.setattr(FeedbackProgressService, '_summary', staticmethod(fail_summary))
                elif stage == 'flush':
                    scoped_patch.setattr(db, 'flush', AsyncMock(side_effect=RuntimeError('flush failed')))
                else:
                    scoped_patch.setattr(db, 'commit', AsyncMock(side_effect=RuntimeError('commit failed')))
                with pytest.raises(ProjectCompletionExecutionError) as exc_info:
                    await FeedbackProgressService.complete_project(
                        db,
                        state['project_id'],
                        complete_request(precheck),
                        state['user_ids'][0],
                        'p7-user',
                        true(),
                        true(),
                    )
                assert exc_info.value.stage == stage
        async with factory() as verify:
            project = await verify.get(FbProject, state['project_id'])
            task_rows = list(
                (
                    await verify.execute(
                        select(
                            FbAssignment.status,
                            FbAssignment.closed_time,
                            FbAssignment.lock_version,
                        ).where(FbAssignment.project_id == state['project_id'])
                    )
                ).all()
            )
            assert project.status == 'ACTIVE'
            assert project.completed_by is None
            assert project.completed_time is None
            assert project.completion_reason is None
            assert project.lock_version == precheck.project_lock_version
            assert sorted(item.status for item in task_rows) == [
                'DRAFT',
                'PENDING',
                'PENDING',
                'PENDING',
                'SUBMITTED',
            ]
            assert all(item.closed_time is None for item in task_rows)
            assert (
                await verify.scalar(
                    select(func.count())
                    .select_from(FbProjectCompletionAudit)
                    .where(FbProjectCompletionAudit.project_id == state['project_id'])
                )
                == 0
            )
