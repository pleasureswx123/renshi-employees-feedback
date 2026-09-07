# ruff: noqa: PLR2004

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import true

from common.annotation.log_annotation import Log
from common.aspect.data_scope import GetDataScope
from common.aspect.pre_auth import PreAuth
from common.context import RequestContext
from common.vo import PageModel
from exceptions.handle import handle_exception
from module_admin.service.log_service import LogQueueService
from module_feedback.controller.report_controller import report_controller
from module_feedback.entity.vo.report_vo import ReportCalculationModel, ScoreSourceModel
from module_feedback.service.report_service import FeedbackReportService


def app_for(monkeypatch: pytest.MonkeyPatch, permissions: list[str]) -> FastAPI:
    app = FastAPI()
    handle_exception(app)
    app.include_router(report_controller)
    user = SimpleNamespace(user=SimpleNamespace(user_id=8, user_name='p8', dept=None), permissions=permissions)

    async def current() -> Any:
        return user

    async def database() -> Any:
        return object()

    async def scope() -> Any:
        return true()

    @app.middleware('http')
    async def context(request: Any, call_next: Any) -> Any:
        token = RequestContext.set_current_user(user)
        try:
            return await call_next(request)
        finally:
            RequestContext.reset_current_user(token)

    for route in report_controller.routes:
        for dependency in route.dependant.dependencies:
            if isinstance(dependency.call, PreAuth):
                app.dependency_overrides[dependency.call] = current
            elif dependency.name == 'db':
                app.dependency_overrides[dependency.call] = database
            elif isinstance(dependency.call, GetDataScope):
                app.dependency_overrides[dependency.call] = scope
    monkeypatch.setattr(LogQueueService, 'enqueue_operation_log', AsyncMock())
    monkeypatch.setattr(Log, '_get_oper_location', AsyncMock(return_value=''))
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('method', 'path'),
    [
        ('GET', '/feedback/reports/projects'),
        ('POST', '/feedback/projects/1/reports/calculate'),
        ('GET', '/feedback/projects/1/reports'),
        ('GET', '/feedback/projects/1/reports/2'),
        ('GET', '/feedback/projects/1/answers'),
        ('GET', '/feedback/projects/1/answers/2'),
    ],
)
async def test_employee_cannot_access_hr_report_or_answers(
    monkeypatch: pytest.MonkeyPatch, method: str, path: str
) -> None:
    app = app_for(monkeypatch, ['feedback:task:view', 'feedback:history:view'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.request(method, path)
    assert response.status_code == 200
    assert response.json()['code'] == 403


@pytest.mark.asyncio
async def test_report_permission_does_not_grant_answers_and_answer_permission_is_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing = AsyncMock(return_value=PageModel(rows=[], total=0, pageNum=1, pageSize=20, hasNext=False))
    monkeypatch.setattr(FeedbackReportService, 'answers', listing)
    for permission, expected in [('feedback:report:view', 403), ('feedback:answer:view', 200)]:
        app = app_for(monkeypatch, [permission])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.get('/feedback/projects/1/answers')
            assert response.status_code == 200
            assert response.json()['code'] == expected
            if expected == 200:
                assert response.headers['cache-control'] == 'no-store'
                denied = await client.get('/feedback/projects/1/reports')
                assert denied.json()['code'] == 403
    assert listing.await_count == 1


@pytest.mark.asyncio
async def test_calculate_contract_and_no_sensitive_log_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        FeedbackReportService,
        'calculate',
        AsyncMock(
            return_value=ReportCalculationModel(
                projectId=1,
                calculatedCount=2,
                existingCount=0,
                dataScopeComplete=True,
            )
        ),
    )
    app = app_for(monkeypatch, ['feedback:report:view'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/feedback/projects/1/reports/calculate')
    assert response.status_code == 200
    assert response.json()['data']['calculatedCount'] == 2
    assert response.headers['cache-control'] == 'no-store'
    assert 'calculatedCount' not in str(LogQueueService.enqueue_operation_log.call_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('code', 'http_status'),
    [('REPORT_PROJECT_NOT_COMPLETED', 409), ('REPORT_TARGET_NOT_FOUND', 404), ('REPORT_CALCULATION_FAILED', 500)],
)
async def test_stable_errors_preserved(monkeypatch: pytest.MonkeyPatch, code: str, http_status: int) -> None:
    monkeypatch.setattr(
        FeedbackReportService,
        'calculate',
        AsyncMock(
            side_effect=HTTPException(
                status_code=http_status,
                detail={'code': code, 'message': '测试错误'},
            )
        ),
    )
    app = app_for(monkeypatch, ['feedback:report:view'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/feedback/projects/1/reports/calculate')
    assert response.status_code == http_status
    assert response.json()['data']['code'] == code


@pytest.mark.asyncio
async def test_pagination_and_target_id_reject_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    app = app_for(monkeypatch, ['feedback:report:view', 'feedback:answer:view'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        for path in [
            '/feedback/projects/1/reports?pageSize=101',
            '/feedback/projects/1/answers?targetUserId=-1',
            '/feedback/projects/0/reports',
        ]:
            assert (await client.get(path)).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'permissions,path,allowed',
    [
        (['feedback:report:view'], '/feedback/projects/1/reports/2/source', True),
        (['feedback:report:view'], '/feedback/projects/1/reports/2/source/sheets?indicatorId=1&relationId=1', False),
        (['feedback:answer:view'], '/feedback/projects/1/reports/2/source/sheets?indicatorId=1&relationId=1', False),
        (
            ['feedback:report:view', 'feedback:answer:view'],
            '/feedback/projects/1/reports/2/source/sheets?indicatorId=1&relationId=1',
            True,
        ),
    ],
)
async def test_score_source_permission_boundary(
    monkeypatch: pytest.MonkeyPatch, permissions: list[str], path: str, allowed: bool
) -> None:
    handler = AsyncMock(
        return_value=ScoreSourceModel(
            targetName='甲', calculationVersion='feedback-score-v1', calculatedTime=datetime(2026, 9, 7), rows=[]
        )
    )
    monkeypatch.setattr(FeedbackReportService, 'source', handler)
    app = app_for(monkeypatch, permissions)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get(path)
    assert response.json()['code'] == (200 if allowed else 403)
    assert handler.called == allowed
    if allowed:
        assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.asyncio
async def test_answer_project_options_use_independent_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = AsyncMock(return_value=PageModel(rows=[], total=0, pageNum=1, pageSize=20, hasNext=False))
    monkeypatch.setattr(FeedbackReportService, 'answer_projects', handler)
    for permissions, expected in [(['feedback:answer:view'], 200), (['feedback:report:view'], 403)]:
        app = app_for(monkeypatch, permissions)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.get('/feedback/answers/projects?keyword=年度')
        assert response.json()['code'] == expected
    assert handler.call_count == 1


@pytest.mark.parametrize('score,expected', [(Decimal('0.0000'), '0.0000'), (Decimal('82.5000'), '82.5000'), (None, None)])
def test_submitted_answer_raw_score_preserves_precision(score: Decimal | None, expected: str | None) -> None:
    task = SimpleNamespace(assignment_id=1, target_user_id=2, target_snapshot=SimpleNamespace(target_user_name='甲', target_dept_name='研发'), evaluator_user_name='乙', evaluator_dept_name='研发', relation=SimpleNamespace(relation_name='同级'), submitted_time=datetime(2026, 9, 7), answer_sheet=SimpleNamespace(raw_total_score=score))
    assert FeedbackReportService._answer_row(task).raw_total_score == expected
