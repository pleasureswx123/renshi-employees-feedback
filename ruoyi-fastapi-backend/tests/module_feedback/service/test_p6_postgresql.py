import asyncio
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from fastapi import HTTPException, status
from sqlalchemy import func, select, update

from exceptions.exception import ConflictException
from module_feedback.dao.answer_dao import FeedbackAnswerDao
from module_feedback.entity.do import FbAnswerSheet, FbAssignment, FbProject
from module_feedback.entity.vo.employee_vo import AnswerDraftSaveModel, AnswerSubmitModel, EmployeePageQueryModel
from module_feedback.service.answer_service import FeedbackAnswerService
from module_feedback.service.employee_service import FeedbackEmployeeService
from scripts.feedback_p0_database_precheck import get_current_revision, get_repository_head, run_alembic
from tests.module_feedback.service import p6_helpers
from tests.module_feedback.service.p6_helpers import answer_request, cleanup_p6_project, create_p6_project
from tests.module_feedback.service.test_p5_publication_flow_postgresql import create_test_session_factory

pytestmark = pytest.mark.skipif(
    os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') != '1', reason='仅显式启用隔离PostgreSQL时运行'
)
TARGET_COUNT = 2
ANSWER_COUNT = 5


@pytest_asyncio.fixture
async def context() -> Any:
    engine, factory = create_test_session_factory()
    state = None
    try:
        state = await create_p6_project(factory)
        yield factory, state
    finally:
        if state:
            await cleanup_p6_project(factory, state)
        await engine.dispose()


async def detail_for(factory: Any, state: dict, index: int = 0) -> Any:
    async with factory() as db:
        return await FeedbackEmployeeService.get_task(db, state['task_ids'][index], state['evaluator_id'])


@pytest.mark.asyncio
async def test_employee_draft_restore_validate_submit_and_independent_second_person(context: tuple) -> None:
    factory, state = context
    user_id, task_id = state['evaluator_id'], state['task_ids'][0]
    detail = await detail_for(factory, state)
    assert detail.editable and not detail.answers
    async with factory() as db:
        projects = await FeedbackEmployeeService.list_projects(db, user_id, EmployeePageQueryModel())
        assert next(row for row in projects.rows if row.project_id == state['project_id']).total_count == TARGET_COUNT
        saved = await FeedbackAnswerService.save_draft(db, task_id, user_id, answer_request(detail, complete=False))
        assert saved.answered_count == 1 and saved.lock_version == 1
        assert saved.task.status.value == 'DRAFT'
    restored = await detail_for(factory, state)
    assert restored.answers == saved.answers
    assert restored.last_page_id == detail.questionnaire.pages[-1].page_id
    async with factory() as db:
        with pytest.raises(ConflictException, match='其他页面保存'):
            await FeedbackAnswerService.save_draft(db, task_id, user_id, answer_request(detail))
        with pytest.raises(ConflictException) as invalid:
            await FeedbackAnswerService.submit(
                db, task_id, user_id, answer_request(restored, submit=True, complete=False)
            )
        assert all(item['pageId'] for item in invalid.value.data['validationIssues'])
        submitted = await FeedbackAnswerService.submit(db, task_id, user_id, answer_request(restored, submit=True))
        assert submitted.editable is False and submitted.task.status.value == 'SUBMITTED'
    async with factory() as db:
        sheet = await FeedbackAnswerDao.get_by_assignment_id(db, task_id)
        assert sheet.raw_total_score == Decimal('53.7500')
        assert len(sheet.answers) == ANSWER_COUNT and sheet.submitted_time is not None
        assert sheet.submission_snapshot['versionId'] == detail.task.version_id
        assert sheet.submission_snapshot['scoringRule']
        assert any(answer.value_snapshot.get('optionLabel') == '很好' for answer in sheet.answers)
        assert next(answer for answer in sheet.answers if answer.answer_type == 'TEXT').raw_score is None
        history = await FeedbackEmployeeService.list_history(db, user_id, EmployeePageQueryModel())
        assert task_id in [row.assignment_id for row in history.rows]
        readonly = await FeedbackEmployeeService.get_task(db, task_id, user_id, history=True)
        assert readonly.answers == submitted.answers and not readonly.editable
        project = await FeedbackEmployeeService.get_project(db, state['project_id'], user_id)
        assert project.submitted_count == 1 and project.pending_count == 1
        with pytest.raises(ConflictException, match='不可修改'):
            await FeedbackAnswerService.save_draft(db, task_id, user_id, answer_request(submitted))
    second = await detail_for(factory, state, 1)
    assert second.editable and not second.answers
    async with factory() as db:
        await FeedbackAnswerService.submit(db, state['task_ids'][1], user_id, answer_request(second, submit=True))
        projects = await FeedbackEmployeeService.list_projects(db, user_id, EmployeePageQueryModel())
        assert state['project_id'] not in [row.project_id for row in projects.rows]


@pytest.mark.asyncio
async def test_cross_user_and_version_page_question_option_references_are_rejected(context: tuple) -> None:
    factory, state = context
    task_id, user_id = state['task_ids'][0], state['evaluator_id']
    detail = await detail_for(factory, state)
    async with factory() as db:
        for history in (True, False):
            with pytest.raises(HTTPException) as denied:
                await FeedbackEmployeeService.get_task(db, task_id, state['user_ids'][0], history=history)
            assert denied.value.status_code == status.HTTP_404_NOT_FOUND
        with pytest.raises(HTTPException):
            await FeedbackAnswerService.submit(db, task_id, state['user_ids'][0], answer_request(detail, submit=True))
        with pytest.raises(HTTPException):
            await FeedbackEmployeeService.get_task(db, task_id, user_id, history=True)
        base = answer_request(detail).model_dump(by_alias=True, mode='json')
        for patch in (
            {'versionId': detail.task.version_id + 100000},
            {'lastPageId': 999999999},
            {'answers': [{'questionId': 999999999, 'textValue': '越界'}]},
            {'answers': [{'questionId': base['answers'][0]['questionId'], 'optionId': 999999999}]},
        ):
            with pytest.raises(ConflictException):
                await FeedbackAnswerService.save_draft(
                    db, task_id, user_id, AnswerDraftSaveModel.model_validate({**base, **patch})
                )
        count = await db.scalar(
            select(func.count()).select_from(FbAnswerSheet).where(FbAnswerSheet.assignment_id == task_id)
        )
        assert count == 0


@pytest.mark.asyncio
async def test_duplicate_parallel_submit_is_idempotent_and_changed_payload_conflicts(context: tuple) -> None:
    factory, state = context
    detail = await detail_for(factory, state)
    task_id, user_id = state['task_ids'][0], state['evaluator_id']
    request = answer_request(detail, submit=True)

    async def submit() -> Any:
        async with factory() as db:
            return await FeedbackAnswerService.submit(db, task_id, user_id, request)

    results = await asyncio.gather(submit(), submit())
    assert sorted(item.already_submitted for item in results) == [False, True]
    assert results[0].sheet_id == results[1].sheet_id
    async with factory() as db:
        changed = request.model_dump(mode='json', by_alias=True)
        changed['answers'][0]['reason'] = '不可覆盖'
        with pytest.raises(ConflictException, match='不可修改'):
            await FeedbackAnswerService.submit(db, task_id, user_id, AnswerSubmitModel.model_validate(changed))
        with pytest.raises(ConflictException, match='不可修改'):
            await FeedbackAnswerService.submit(db, task_id, user_id, answer_request(detail, submit=True))
        count = await db.scalar(
            select(func.count()).select_from(FbAnswerSheet).where(FbAnswerSheet.assignment_id == task_id)
        )
        assert count == 1


@pytest.mark.asyncio
async def test_draft_and_submit_race_never_overwrites_or_half_submits(context: tuple) -> None:
    factory, state = context
    detail = await detail_for(factory, state)
    task_id, user_id = state['task_ids'][0], state['evaluator_id']

    async def write(submitting: bool) -> Any:
        async with factory() as db:
            method = FeedbackAnswerService.submit if submitting else FeedbackAnswerService.save_draft
            return await method(db, task_id, user_id, answer_request(detail, submit=submitting))

    results = await asyncio.gather(write(False), write(True), return_exceptions=True)
    assert sum(isinstance(item, ConflictException) for item in results) == 1
    async with factory() as db:
        task = await db.get(FbAssignment, task_id)
        sheet = await FeedbackAnswerDao.get_by_assignment_id(db, task_id)
        assert task.status == sheet.status
        assert len(sheet.answers) == ANSWER_COUNT
        assert (sheet.submitted_time is not None) == (task.status == 'SUBMITTED')


@pytest.mark.asyncio
async def test_failed_transaction_preserves_existing_draft_and_no_formal_score(
    context: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, state = context
    detail = await detail_for(factory, state)
    task_id, user_id = state['task_ids'][0], state['evaluator_id']
    async with factory() as db:
        saved = await FeedbackAnswerService.save_draft(db, task_id, user_id, answer_request(detail, complete=False))
    original = FeedbackAnswerDao.replace_draft_answers

    async def fail_after_write(db: Any, sheet_id: int, answers: list) -> None:
        await original(db, sheet_id, answers)
        raise RuntimeError('测试注入答案写入失败')

    monkeypatch.setattr(FeedbackAnswerDao, 'replace_draft_answers', fail_after_write)
    async with factory() as db:
        with pytest.raises(RuntimeError, match='测试注入'):
            await FeedbackAnswerService.submit(db, task_id, user_id, answer_request(saved, submit=True))
    restored = await detail_for(factory, state)
    assert restored.answers == saved.answers and restored.lock_version == saved.lock_version
    async with factory() as db:
        sheet = await FeedbackAnswerDao.get_by_assignment_id(db, task_id)
        assert sheet.raw_total_score is None and sheet.submission_snapshot == {}


@pytest.mark.asyncio
async def test_close_project_lock_blocks_late_submit_and_all_writes_after_completion(context: tuple) -> None:
    factory, state = context
    detail = await detail_for(factory, state)
    task_id, user_id = state['task_ids'][0], state['evaluator_id']
    close_locked = asyncio.Event()
    release_close = asyncio.Event()

    async def close_with_p7_lock_protocol() -> None:
        async with factory() as db:
            project = await db.scalar(
                select(FbProject).where(FbProject.project_id == state['project_id']).with_for_update()
            )
            close_locked.set()
            await release_close.wait()
            project.status = 'COMPLETED'
            project.completed_time = datetime.now()
            project.completed_by = state['user_ids'][0]
            await db.execute(
                update(FbAssignment)
                .where(FbAssignment.project_id == project.project_id)
                .values(status='CLOSED_INCOMPLETE', closed_time=datetime.now())
            )
            await db.commit()

    async def submit() -> Any:
        async with factory() as db:
            return await FeedbackAnswerService.submit(db, task_id, user_id, answer_request(detail, submit=True))

    closing = asyncio.create_task(close_with_p7_lock_protocol())
    await asyncio.wait_for(close_locked.wait(), timeout=5)
    pending = asyncio.create_task(submit())
    try:
        await asyncio.sleep(0.05)
        assert not pending.done()
    finally:
        release_close.set()
        await closing
    with pytest.raises(ConflictException, match='已结束'):
        await pending
    async with factory() as db:
        with pytest.raises(ConflictException, match='已结束'):
            await FeedbackAnswerService.save_draft(db, task_id, user_id, answer_request(detail))
        count = await db.scalar(
            select(func.count()).select_from(FbAnswerSheet).where(FbAnswerSheet.project_id == state['project_id'])
        )
        assert count == 0


@pytest.mark.asyncio
async def test_same_target_different_relations_remain_independent() -> None:
    engine, factory = create_test_session_factory()
    state = None
    try:
        state = await create_p6_project(factory, extra_relation=True)
        async with factory() as db:
            project = await FeedbackEmployeeService.get_project(db, state['project_id'], state['evaluator_id'])
            first, second = project.tasks[:2]
            assert first.target_user_id == second.target_user_id and first.relation_id != second.relation_id
            detail = await FeedbackEmployeeService.get_task(db, first.assignment_id, state['evaluator_id'])
            await FeedbackAnswerService.submit(
                db, first.assignment_id, state['evaluator_id'], answer_request(detail, submit=True)
            )
            other = await FeedbackEmployeeService.get_task(db, second.assignment_id, state['evaluator_id'])
            assert other.editable and not other.answers
    finally:
        if state:
            await cleanup_p6_project(factory, state)
        await engine.dispose()


@pytest.mark.asyncio
async def test_legal_large_answers_sum_without_overflow_and_preserve_decimal(monkeypatch: pytest.MonkeyPatch) -> None:
    original = p6_helpers.questionnaire

    def large_questionnaire(version_id: int, lock_version: int) -> Any:
        document = original(version_id, lock_version)
        for question in document.pages[1].questions[:2]:
            question.max_score = Decimal('99999999.9999')
            question.decimal_places = 4
        document.pages[1].questions[1].config.step = Decimal('0.0001')
        return document

    monkeypatch.setattr(p6_helpers, 'questionnaire', large_questionnaire)
    engine, factory = create_test_session_factory()
    state = None
    try:
        state = await create_p6_project(factory)
        detail = await detail_for(factory, state)
        request = answer_request(detail, submit=True)
        for answer in request.answers[2:4]:
            answer.numeric_value = Decimal('99999999.9999')
        async with factory() as db:
            result = await FeedbackAnswerService.submit(db, state['task_ids'][0], state['evaluator_id'], request)
            sheet = await db.get(FbAnswerSheet, result.sheet_id)
            assert sheet.raw_total_score == Decimal('200000006.9998')
    finally:
        if state:
            await cleanup_p6_project(factory, state)
        await engine.dispose()


@pytest.mark.asyncio
async def test_p6_migration_preserves_values_and_refuses_lossy_downgrade(context: tuple) -> None:
    factory, state = context
    detail = await detail_for(factory, state)
    async with factory() as db:
        saved = await FeedbackAnswerService.save_draft(
            db, state['task_ids'][0], state['evaluator_id'], answer_request(detail)
        )
        await db.execute(
            update(FbAnswerSheet)
            .where(FbAnswerSheet.sheet_id == saved.sheet_id)
            .values(raw_total_score=Decimal('99999999.9999'))
        )
        await db.commit()
    try:
        run_alembic('ruoyi_feedback_test', 'downgrade', '20260902_04_feedback_publication')
        run_alembic('ruoyi_feedback_test', 'upgrade', 'head')
        async with factory() as db:
            sheet = await db.get(FbAnswerSheet, saved.sheet_id)
            assert sheet.raw_total_score == Decimal('99999999.9999')
            sheet.raw_total_score = Decimal('100000000.0000')
            await db.commit()
        with pytest.raises(RuntimeError, match='拒绝降级'):
            run_alembic('ruoyi_feedback_test', 'downgrade', '20260902_04_feedback_publication')
        # Alembic逐revision事务：权限无授权可先退至P6容量revision，但正式总分仍阻止进一步降级。
        assert get_current_revision('ruoyi_feedback_test') == '20260902_05_feedback_answering'
    finally:
        run_alembic('ruoyi_feedback_test', 'upgrade', 'head')
        assert get_current_revision('ruoyi_feedback_test') == get_repository_head()
