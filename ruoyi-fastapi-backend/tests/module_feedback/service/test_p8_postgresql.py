# ruff: noqa: PLR2004
import asyncio
import os
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, false, select, true

from module_feedback.calculators.report_score import calculate_report
from module_feedback.dao.report_dao import FeedbackReportDao
from module_feedback.entity.do import FbAssignment, FbProjectTarget, FbScoreResult
from module_feedback.entity.vo.report_vo import ReportQueryModel, SubmittedAnswerQueryModel
from module_feedback.service.answer_service import FeedbackAnswerService
from module_feedback.service.employee_service import FeedbackEmployeeService
from module_feedback.service.progress_service import FeedbackProgressService
from module_feedback.service.report_service import FeedbackReportService
from tests.module_feedback.service.p6_helpers import answer_request, cleanup_p6_project, create_p6_project
from tests.module_feedback.service.test_p5_publication_flow_postgresql import create_test_session_factory
from tests.module_feedback.service.test_p7_completion_postgresql import complete_request

pytestmark = pytest.mark.skipif(os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') != '1', reason='需要显式启用隔离PostgreSQL')


@pytest_asyncio.fixture
async def p8_context(request: Any) -> Any:
    engine, factory = create_test_session_factory()
    state = await create_p6_project(factory, extra_relation=True)
    try:
        async with factory() as db:
            scenario = getattr(request, 'param', 'all')
            task_ids = state['task_ids'] if scenario == 'all' else state['task_ids'][:1] if scenario == 'one' else []
            for task_id in task_ids:
                detail = await FeedbackEmployeeService.get_task(db, task_id, state['evaluator_id'])
                await FeedbackAnswerService.submit(
                    db, task_id, state['evaluator_id'], answer_request(detail, submit=True)
                )
            precheck = await FeedbackProgressService.get_precheck(db, state['project_id'], true(), true())
            await FeedbackProgressService.complete_project(
                db,
                state['project_id'],
                complete_request(precheck),
                state['user_ids'][0],
                'p8-test',
                true(),
                true(),
            )
        yield factory, state
    finally:
        async with factory() as db:
            await db.execute(delete(FbScoreResult).where(FbScoreResult.project_id == state['project_id']))
            await db.commit()
        await cleanup_p6_project(factory, state)
        await engine.dispose()


@pytest.mark.asyncio
async def test_generate_database_api_and_recalculation_match(p8_context: Any) -> None:
    factory, state = p8_context
    async with factory() as db:
        before = await FeedbackReportService.team(db, state['project_id'], ReportQueryModel(), true(), true())
        assert before.ready is False
        generated = await FeedbackReportService.calculate(db, state['project_id'], true(), true())
        assert generated.calculated_count == 2
        report = await FeedbackReportService.team(db, state['project_id'], ReportQueryModel(), true(), true())
        assert report.ready and len(report.rows) == 2
        assert [r.rank for r in report.rows] == [1, 1]
        assert all(r.score == '45.55' for r in report.rows)  # 53.75 / 118 × 100
        person = await FeedbackReportService.person(
            db, state['project_id'], report.rows[0].target_user_id, true(), true()
        )
        assert person.questions and person.self_score is None
        assert any(row.status == 'MISSING' for row in person.relations)
        all_rows = list(await db.scalars(select(FbScoreResult).where(FbScoreResult.project_id == state['project_id'])))
        original = [(r.result_id, r.calculated_time, r.calculation_basis) for r in all_rows]
        for row in all_rows:
            if row.result_type == 'PERSON_TOTAL':
                recalculated, _ = calculate_report(row.calculation_basis['inputs'])
                result = next(r for r in recalculated if r['result_type'] == 'PERSON_TOTAL')
                assert row.score == result['score']
                assert len(str(row.score)) > 20
        retry = await FeedbackReportService.calculate(db, state['project_id'], true(), true())
        assert retry.existing_count == 2 and retry.calculated_count == 0
        assert original == [(r.result_id, r.calculated_time, r.calculation_basis) for r in all_rows]
        data = person.model_dump(by_alias=True, mode='json')
        text = str(data)
        for forbidden in ('sheetId', 'evaluator', 'answerDigest', 'reason', 'textValue', 'calculationBasis'):
            assert forbidden not in text


@pytest.mark.asyncio
async def test_scope_isolation_and_raw_submitted_answers(p8_context: Any) -> None:
    factory, state = p8_context
    project_id = state['project_id']
    visible_id = state['user_ids'][0]
    scope = FbProjectTarget.target_user_id == visible_id
    async with factory() as db:
        generated = await FeedbackReportService.calculate(db, project_id, true(), scope)
        assert generated.calculated_count == 1 and not generated.data_scope_complete
        report = await FeedbackReportService.team(db, project_id, ReportQueryModel(), true(), scope)
        assert len(report.rows) == 1 and report.rows[0].target_user_id == visible_id
        assert report.rows[0].rank == 1 and not report.data_scope_complete
        with pytest.raises(HTTPException) as error:
            await FeedbackReportService.person(db, project_id, state['user_ids'][2], true(), scope)
        assert error.value.status_code == 404
        for project_scope, target_scope in [(false(), true()), (true(), false())]:
            with pytest.raises(HTTPException) as error:
                await FeedbackReportService.team(db, project_id, ReportQueryModel(), project_scope, target_scope)
            assert error.value.status_code == 404
        listing = await FeedbackReportService.answers(db, project_id, SubmittedAnswerQueryModel(), true(), scope)
        assert listing.total == 2
        answer = await FeedbackReportService.answer(db, project_id, listing.rows[0].assignment_id, true(), scope)
        assert answer.editable is False and any(a.text_value == '继续保持' for a in answer.answers)
        closed_id = await db.scalar(
            select(FbAssignment.assignment_id).where(
                FbAssignment.project_id == project_id, FbAssignment.status == 'CLOSED_INCOMPLETE'
            )
        )
        with pytest.raises(HTTPException) as error:
            await FeedbackReportService.answer(db, project_id, closed_id, true(), true())
        assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_concurrent_generation_is_idempotent(p8_context: Any) -> None:
    factory, state = p8_context

    async def run() -> Any:
        async with factory() as db:
            return await FeedbackReportService.calculate(db, state['project_id'], true(), true())

    results = await asyncio.gather(run(), run())
    assert sorted(r.calculated_count for r in results) == [0, 2]


@pytest.mark.asyncio
async def test_partial_write_failure_rolls_back_all_targets(p8_context: Any, monkeypatch: Any) -> None:
    factory, state = p8_context
    original = FeedbackReportDao.add_results
    calls = 0

    async def fail_second(db: Any, rows: Any) -> None:
        nonlocal calls
        calls += 1
        await original(db, rows)
        if calls == 2:
            raise RuntimeError('故障注入')

    monkeypatch.setattr(FeedbackReportDao, 'add_results', fail_second)
    async with factory() as db:
        with pytest.raises(HTTPException) as error:
            await FeedbackReportService.calculate(db, state['project_id'], true(), true())
        assert error.value.status_code == 500
        assert not list(await db.scalars(select(FbScoreResult).where(FbScoreResult.project_id == state['project_id'])))


@pytest.mark.asyncio
async def test_changed_raw_score_fails_closed(p8_context: Any) -> None:
    factory, state = p8_context
    async with factory() as db:
        sheets, answers = await FeedbackReportDao.submitted_inputs(
            db,
            state['project_id'],
            state['config'].version_id,
            {
                t.target_id
                for t in await FeedbackReportDao.targets(db, state['project_id'], state['config'].version_id, true())
            },
        )
        # 仅篡改查询副本，测试不改写已提交答案。
        corrupted = [
            SimpleNamespace(**{**a._mapping, 'raw_score': Decimal('99')}) if a.raw_score is not None else a
            for a in answers
        ]
        with (
            patch.object(FeedbackReportDao, 'submitted_inputs', AsyncMock(return_value=(sheets, corrupted))),
            pytest.raises(HTTPException) as error,
        ):
            await FeedbackReportService.calculate(db, state['project_id'], true(), true())
        assert error.value.detail['code'] == 'REPORT_INPUT_INVALID'


@pytest.mark.asyncio
@pytest.mark.parametrize('p8_context', ['one', 'none'], indirect=True)
async def test_insufficient_data_is_null_and_last_in_ranking(p8_context: Any) -> None:
    factory, state = p8_context
    async with factory() as db:
        await FeedbackReportService.calculate(db, state['project_id'], true(), true())
        report = await FeedbackReportService.team(db, state['project_id'], ReportQueryModel(), true(), true())
        assert report.rows[-1].score is None
        assert report.rows[-1].rank is None
        assert report.rows[-1].insufficient_data
        assert report.rows[-1].completion_rate == '0.00'
        if report.rows[0].score is not None:
            assert report.rows[0].rank == 1
            filtered = await FeedbackReportService.team(
                db,
                state['project_id'],
                ReportQueryModel(keyword=report.rows[0].target_name),
                true(),
                true(),
            )
            assert filtered.rows[0].rank == 1


@pytest.mark.asyncio
async def test_partial_results_cannot_be_overwritten(p8_context: Any) -> None:
    factory, state = p8_context
    async with factory() as db:
        await FeedbackReportService.calculate(db, state['project_id'], true(), true())
        keys = await FeedbackReportDao.result_keys(
            db,
            state['project_id'],
            state['config'].version_id,
            {
                t.target_id
                for t in await FeedbackReportDao.targets(db, state['project_id'], state['config'].version_id, true())
            },
        )
        # 故障注入只改变DAO返回值，不删除正式结果。
        with (
            patch.object(FeedbackReportDao, 'result_keys', AsyncMock(return_value=keys[:-1])),
            pytest.raises(HTTPException) as error,
        ):
            await FeedbackReportService.calculate(db, state['project_id'], true(), true())
        assert error.value.detail['code'] == 'REPORT_RESULT_INCONSISTENT'


@pytest.mark.asyncio
async def test_active_project_rejects_generation() -> None:
    engine, factory = create_test_session_factory()
    state = await create_p6_project(factory)
    try:
        async with factory() as db:
            with pytest.raises(HTTPException) as error:
                await FeedbackReportService.calculate(db, state['project_id'], true(), true())
            assert error.value.detail['code'] == 'REPORT_PROJECT_NOT_COMPLETED'
    finally:
        await cleanup_p6_project(factory, state)
        await engine.dispose()


@pytest.mark.asyncio
async def test_old_schema_refuses_to_truncate_formal_results(p8_context: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    factory, state = p8_context
    monkeypatch.setattr(FeedbackReportDao, 'scoring_precision_ready', AsyncMock(return_value=False))
    async with factory() as db:
        with pytest.raises(HTTPException) as error:
            await FeedbackReportService.calculate(db, state['project_id'], true(), true())
        assert error.value.detail['code'] == 'REPORT_SCHEMA_NOT_READY'
        assert not list(await db.scalars(select(FbScoreResult).where(FbScoreResult.project_id == state['project_id'])))
