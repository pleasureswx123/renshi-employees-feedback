# ruff: noqa: PLR2004

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from common.annotation.log_annotation import Log
from common.aspect.pre_auth import PreAuth
from common.context import RequestContext
from exceptions.handle import handle_exception
from middlewares.trace_middleware.middle import TraceASGIMiddleware
from module_admin.service.log_service import LogQueueService
from module_feedback.service.employee_service import FeedbackEmployeeService
from module_feedback.service.report_service import FeedbackReportService
from scripts.feedback_p9_api_audit import CONTROLLERS, audit_routes, feedback_routes
from tests.module_feedback.controller.test_project_controller import EXPECTED_ROUTES

HR_ROUTES = [row for row in audit_routes() if not row['currentEmployee'] and row['path'] != '/feedback/health']


def build_security_app(monkeypatch: pytest.MonkeyPatch, *, authenticated: bool = True) -> FastAPI:
    app = FastAPI()
    handle_exception(app)
    app.add_middleware(TraceASGIMiddleware)
    user = SimpleNamespace(
        user=SimpleNamespace(user_id=9, user_name='p9-test', dept_id=100, dept=None, admin=False, role=[]),
        permissions=['feedback:task:view', 'feedback:task:answer', 'feedback:task:submit', 'feedback:history:view'],
    )

    async def current() -> Any:
        return user

    async def database() -> Any:
        return object()

    @app.middleware('http')
    async def user_context(request: Any, call_next: Any) -> Any:
        token = RequestContext.set_current_user(user)
        try:
            return await call_next(request)
        finally:
            RequestContext.reset_current_user(token)

    for controller in CONTROLLERS:
        app.include_router(controller)
    for route in feedback_routes():
        for dependency in route.dependant.dependencies:
            if dependency.name in {'db', 'query_db'}:
                app.dependency_overrides[dependency.call] = database
            elif authenticated and (
                isinstance(dependency.call, PreAuth) or dependency.name in {'user', 'current_user'}
            ):
                app.dependency_overrides[dependency.call] = current
            # 未登录分支仍使用真实PreAuth；只替换其数据库，不替换登录判断。
            if isinstance(dependency.call, PreAuth):
                for nested in dependency.dependencies:
                    if nested.name == 'db':
                        app.dependency_overrides[nested.call] = database
    monkeypatch.setattr(LogQueueService, 'enqueue_operation_log', AsyncMock())
    monkeypatch.setattr(Log, '_get_oper_location', AsyncMock(return_value=''))
    return app


def concrete_path(path: str) -> str:
    import re  # noqa: PLC0415

    return re.sub(r'\{[^}]+\}', '1', path)


def test_all_feedback_routes_have_explicit_security_contract() -> None:
    rows = audit_routes()
    expected = {
        **{key: [value] for key, value in EXPECTED_ROUTES.items()},
        ('GET', '/feedback/health'): [],
        ('GET', '/feedback/employee/projects'): ['feedback:task:view'],
        ('GET', '/feedback/employee/projects/{project_id}'): ['feedback:task:view'],
        ('GET', '/feedback/employee/tasks/{assignment_id}'): ['feedback:task:view'],
        ('PUT', '/feedback/employee/tasks/{assignment_id}/draft'): ['feedback:task:answer'],
        ('POST', '/feedback/employee/tasks/{assignment_id}/submit'): ['feedback:task:submit'],
        ('GET', '/feedback/employee/history'): ['feedback:history:view'],
        ('GET', '/feedback/employee/history/{assignment_id}'): ['feedback:history:view'],
        ('GET', '/feedback/answers/projects'): ['feedback:answer:view'],
        ('GET', '/feedback/reports/projects'): ['feedback:report:view'],
        ('POST', '/feedback/projects/{project_id}/reports/calculate'): ['feedback:report:view'],
        ('GET', '/feedback/projects/{project_id}/reports'): ['feedback:report:view'],
        ('GET', '/feedback/projects/{project_id}/reports/{target_user_id}'): ['feedback:report:view'],
        ('GET', '/feedback/projects/{project_id}/reports/{target_user_id}/source'): ['feedback:report:view'],
        ('GET', '/feedback/projects/{project_id}/reports/{target_user_id}/source/sheets'): ['feedback:report:view', 'feedback:answer:view'],
        ('GET', '/feedback/projects/{project_id}/answers'): ['feedback:answer:view'],
        ('GET', '/feedback/projects/{project_id}/answers/{assignment_id}'): ['feedback:answer:view'],
    }
    assert {(row['method'], row['path']): row['permissions'] for row in rows} == expected
    for row in rows:
        if (
            row['currentEmployee']
            or row['path'] in {'/feedback/health', '/feedback/projects/system-templates'}
            or (row['method'], row['path']) == ('POST', '/feedback/projects')
        ):
            continue
        assert any(scope['table'] == 'fb_project' for scope in row['scope'])
        if '/reports' in row['path'] or '/answers' in row['path']:
            assert any(scope['table'] == 'fb_project_target' for scope in row['scope'])


@pytest.mark.asyncio
@pytest.mark.parametrize('row', audit_routes(), ids=lambda row: f'{row["method"]} {row["path"]}')
async def test_every_route_rejects_no_login_before_body_validation(monkeypatch: pytest.MonkeyPatch, row: dict) -> None:
    app = build_security_app(monkeypatch, authenticated=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.request(row['method'], concrete_path(row['path']), json={})
    assert response.json()['code'] == 401


@pytest.mark.asyncio
@pytest.mark.parametrize('row', HR_ROUTES, ids=lambda row: f'{row["method"]} {row["path"]}')
async def test_employee_is_denied_at_all_hr_interfaces(monkeypatch: pytest.MonkeyPatch, row: dict) -> None:
    app = build_security_app(monkeypatch)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.request(row['method'], concrete_path(row['path']), json={})
    assert response.json()['code'] == 403


@pytest.mark.asyncio
async def test_invalid_answer_never_echoes_raw_input_and_preserves_request_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = build_security_app(monkeypatch)
    secret = '不得回传的员工原始答案和Token'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(
            '/feedback/employee/tasks/1/submit', json={'answers': [{'numericValue': secret}], 'evaluatorUserId': 1}
        )
    assert response.status_code == 422
    assert response.json()['data']['code'] == 'VALIDATION_ERROR'
    assert secret not in response.text
    assert response.headers['request-id'] and response.headers['trace-id']
    assert all(set(error) == {'type', 'loc', 'msg'} for error in response.json()['data']['validationErrors'])


@pytest.mark.asyncio
async def test_unlogged_endpoint_exception_hides_sql_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = '不得输出的完整答案与数据库连接字符串'
    logger = MagicMock()
    monkeypatch.setattr('exceptions.handle.logger', logger)
    monkeypatch.setattr(FeedbackEmployeeService, 'get_task', AsyncMock(side_effect=RuntimeError(secret)))
    app = build_security_app(monkeypatch)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url='http://test'
    ) as client:
        response = await client.get('/feedback/employee/tasks/1')
    assert response.status_code == 500
    assert secret not in response.text and secret not in str(logger.mock_calls)


@pytest.mark.asyncio
async def test_logged_raw_answer_failure_hides_sql_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.module_feedback.controller.test_p8_http_contract import app_for  # noqa: PLC0415

    secret = '不得进入异常响应和操作日志的原始文本'
    logger = MagicMock()
    monkeypatch.setattr('common.annotation.log_annotation.logger', logger)
    monkeypatch.setattr(FeedbackReportService, 'answer', AsyncMock(side_effect=RuntimeError(secret)))
    app = app_for(monkeypatch, ['feedback:answer:view'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/feedback/projects/1/answers/2')
    assert response.status_code == 500
    assert secret not in response.text and secret not in str(logger.mock_calls)
    assert secret not in str(LogQueueService.enqueue_operation_log.call_args_list)
