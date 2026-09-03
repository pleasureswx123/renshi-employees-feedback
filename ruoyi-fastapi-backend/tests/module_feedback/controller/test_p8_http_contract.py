# ruff: noqa: PLR2004

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
from module_feedback.entity.vo.report_vo import ReportCalculationModel
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
