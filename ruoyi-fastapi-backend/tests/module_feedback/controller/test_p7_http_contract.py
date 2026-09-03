# ruff: noqa: PLC0415, PLR2004

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.routing import APIRoute

from common.annotation.log_annotation import Log
from common.aspect.data_scope import GetDataScope
from common.aspect.pre_auth import PreAuth
from common.context import RequestContext
from exceptions.handle import handle_exception
from middlewares.trace_middleware.ctx import TraceCtx
from module_admin.service.log_service import LogQueueService
from module_feedback.controller.project_controller import project_controller
from module_feedback.service.progress_service import FeedbackProgressService

USER_ID = 7


def p7_routes() -> list[APIRoute]:
    suffixes = ('/progress', '/completion-precheck', '/complete')
    return [
        route for route in project_controller.routes if isinstance(route, APIRoute) and route.path.endswith(suffixes)
    ]


def build_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    app = FastAPI()
    handle_exception(app)
    app.include_router(project_controller)
    user = SimpleNamespace(
        user=SimpleNamespace(user_id=USER_ID, user_name='p7-user', dept=None),
        permissions=['feedback:progress:view', 'feedback:project:complete'],
    )

    async def current_user() -> Any:
        return user

    async def database() -> Any:
        return object()

    async def all_scope() -> Any:
        from sqlalchemy import true

        return true()

    @app.middleware('http')
    async def login_context(request: Any, call_next: Any) -> Any:
        token = RequestContext.set_current_user(user)
        try:
            return await call_next(request)
        finally:
            RequestContext.reset_current_user(token)

    for route in p7_routes():
        for dependency in route.dependant.dependencies:
            if isinstance(dependency.call, PreAuth) or dependency.name == 'current_user':
                app.dependency_overrides[dependency.call] = current_user
            elif dependency.name == 'query_db':
                app.dependency_overrides[dependency.call] = database
            elif isinstance(dependency.call, GetDataScope):
                app.dependency_overrides[dependency.call] = all_scope
    monkeypatch.setattr(LogQueueService, 'enqueue_operation_log', AsyncMock())
    monkeypatch.setattr(Log, '_get_oper_location', AsyncMock(return_value=''))
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('problem_code', 'http_status'),
    [
        ('PROJECT_COMPLETION_SCOPE_FORBIDDEN', 403),
        ('PROJECT_NOT_FOUND', 404),
        ('PROJECT_NOT_ACTIVE', 409),
        ('PROJECT_VERSION_CONFLICT', 409),
        ('COMPLETION_PRECHECK_STALE', 409),
        ('PROJECT_COMPLETION_FAILED', 500),
    ],
)
async def test_p7_slice_6_real_http_preserves_stable_problem_code(
    monkeypatch: pytest.MonkeyPatch, problem_code: str, http_status: int
) -> None:
    detail: dict[str, Any] = {'code': problem_code, 'message': 'P7失败'}
    if problem_code == 'COMPLETION_PRECHECK_STALE':
        detail['latestPrecheck'] = {'projectId': 9}
    monkeypatch.setattr(
        FeedbackProgressService,
        'complete_project',
        AsyncMock(side_effect=HTTPException(status_code=http_status, detail=detail)),
    )
    app = build_app(monkeypatch)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(
            '/feedback/projects/9/complete',
            json={
                'projectLockVersion': 3,
                'completionReason': '截止完成',
                'expectedSummary': {
                    'totalCount': 1,
                    'submittedCount': 0,
                    'draftCount': 0,
                    'pendingCount': 1,
                    'closedIncompleteCount': 0,
                },
            },
        )
    assert response.status_code == http_status
    assert response.json()['data']['code'] == problem_code
    if problem_code == 'COMPLETION_PRECHECK_STALE':
        assert response.json()['data']['latestPrecheck']['projectId'] == 9


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('http_status', 'header_name', 'header_value'),
    [
        (status.HTTP_429_TOO_MANY_REQUESTS, 'Retry-After', '30'),
        (status.HTTP_401_UNAUTHORIZED, 'WWW-Authenticate', 'Bearer'),
    ],
)
async def test_p7_structured_http_exception_preserves_protocol_headers(
    monkeypatch: pytest.MonkeyPatch,
    http_status: int,
    header_name: str,
    header_value: str,
) -> None:
    del monkeypatch
    app = FastAPI()
    handle_exception(app)

    @app.get('/structured-error')
    async def structured_error() -> None:
        raise HTTPException(
            status_code=http_status,
            detail={'code': 'P7_PROTOCOL_ERROR', 'message': '请求失败'},
            headers={header_name: header_value},
        )

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/structured-error')

    assert response.status_code == http_status
    assert response.headers[header_name] == header_value


@pytest.mark.asyncio
async def test_p7_slice_6_validation_error_has_stable_problem_code(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    handle_module = importlib.import_module('exceptions.handle')
    monkeypatch.setattr(TraceCtx, 'get_request_id', lambda: 'request-validation-9')
    monkeypatch.setattr(TraceCtx, 'get_trace_id', lambda: 'trace-validation-9')
    bound_logger = MagicMock()
    bind = MagicMock(return_value=bound_logger)
    monkeypatch.setattr(handle_module.logger, 'bind', bind)
    app = build_app(monkeypatch)
    secret = '不得回显的原始答案'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(
            '/feedback/projects/9/complete',
            json={
                'projectLockVersion': -1,
                'completionReason': ' ',
                'expectedSummary': {
                    'totalCount': 2,
                    'submittedCount': 1,
                    'draftCount': 0,
                    'pendingCount': 0,
                    'closedIncompleteCount': 0,
                },
                'answers': {'nested': secret},
            },
        )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    payload = response.json()
    assert payload['data']['code'] == 'VALIDATION_ERROR'
    assert payload['data']['validationErrors']
    assert all(set(item) == {'type', 'loc', 'msg'} for item in payload['data']['validationErrors'])
    response_text = response.text
    assert secret not in response_text
    bind.assert_called_with(
        event='feedback_project_completion_failed',
        project_id=9,
        operator_user_id=USER_ID,
        problem_code='VALIDATION_ERROR',
        failure_stage='request_validation',
        request_id='request-validation-9',
        trace_id='trace-validation-9',
    )
    bound_logger.warning.assert_called_once_with('评价项目完成请求校验失败')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('path', 'service_method', 'problem_code', 'safe_message'),
    [
        (
            '/feedback/projects/9/progress',
            'get_progress',
            'PROJECT_PROGRESS_FAILED',
            '项目进度读取失败，请稍后重试',
        ),
        (
            '/feedback/projects/9/completion-precheck',
            'get_precheck',
            'PROJECT_COMPLETION_PRECHECK_FAILED',
            '项目完成预检失败，请稍后重试',
        ),
    ],
)
async def test_p7_read_unknown_error_is_safe_real_http_500(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    service_method: str,
    problem_code: str,
    safe_message: str,
) -> None:
    secret = 'internal SQL fb_answer params=原始答案'
    monkeypatch.setattr(FeedbackProgressService, service_method, AsyncMock(side_effect=RuntimeError(secret)))
    app = build_app(monkeypatch)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get(path)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {
        'code': 500,
        'msg': safe_message,
        'success': False,
        'data': {'code': problem_code},
    }
    assert secret not in response.text


@pytest.mark.asyncio
async def test_p7_completion_unknown_failure_logs_stable_stage_and_safe_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    from module_feedback.service.progress_service import ProjectCompletionExecutionError

    controller_module = importlib.import_module('module_feedback.controller.project_controller')
    monkeypatch.setattr(
        FeedbackProgressService,
        'complete_project',
        AsyncMock(side_effect=ProjectCompletionExecutionError('commit')),
    )
    monkeypatch.setattr(TraceCtx, 'get_request_id', lambda: 'request-failed-9')
    monkeypatch.setattr(TraceCtx, 'get_trace_id', lambda: 'trace-failed-9')
    bound_logger = MagicMock()
    bound_logger.opt.return_value = bound_logger
    bind = MagicMock(return_value=bound_logger)
    monkeypatch.setattr(controller_module.logger, 'bind', bind)
    app = build_app(monkeypatch)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(
            '/feedback/projects/9/complete',
            json={
                'projectLockVersion': 3,
                'completionReason': '截止完成',
                'expectedSummary': {
                    'totalCount': 1,
                    'submittedCount': 0,
                    'draftCount': 0,
                    'pendingCount': 1,
                    'closedIncompleteCount': 0,
                },
            },
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()['data']['code'] == 'PROJECT_COMPLETION_FAILED'
    bind.assert_called_with(
        event='feedback_project_completion_failed',
        project_id=9,
        operator_user_id=USER_ID,
        problem_code='PROJECT_COMPLETION_FAILED',
        failure_stage='commit',
        request_id='request-failed-9',
        trace_id='trace-failed-9',
        exception_type='ProjectCompletionExecutionError',
    )
    bound_logger.error.assert_called_once_with('评价项目完成失败')
    bound_logger.opt.assert_not_called()


@pytest.mark.asyncio
async def test_p7_slice_9_audit_whitelist_and_queue_failure_do_not_mask_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime

    from module_feedback.entity.vo.progress_vo import ProgressSummaryModel, ProjectCompleteResultModel

    result = ProjectCompleteResultModel(
        projectId=9,
        projectStatus='COMPLETED',
        projectLockVersion=4,
        completedBy=USER_ID,
        completedTime=datetime(2026, 9, 2, 10, 6),
        completionReason='截止完成',
        alreadyCompleted=False,
        summary=ProgressSummaryModel.from_counts(PENDING=0, DRAFT=0, SUBMITTED=1, CLOSED_INCOMPLETE=1),
    )
    completion = AsyncMock(return_value=result)
    monkeypatch.setattr(FeedbackProgressService, 'complete_project', completion)
    monkeypatch.setattr(TraceCtx, 'get_request_id', lambda: 'request-http-9')
    monkeypatch.setattr(TraceCtx, 'get_trace_id', lambda: 'trace-http-9')
    app = build_app(monkeypatch)
    queue = AsyncMock(side_effect=RuntimeError('日志队列不可用'))
    monkeypatch.setattr(LogQueueService, 'enqueue_operation_log', queue)
    secret = '不得记录的原始答案'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(
            '/feedback/projects/9/complete',
            json={
                'projectLockVersion': 3,
                'completionReason': '截止完成',
                'expectedSummary': {
                    'totalCount': 2,
                    'submittedCount': 1,
                    'draftCount': 0,
                    'pendingCount': 1,
                    'closedIncompleteCount': 0,
                },
                'answers': secret,
            },
        )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # 合法请求成功提交后，即使日志队列失败，HTTP成功事实也不能被改写。
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(
            '/feedback/projects/9/complete',
            json={
                'projectLockVersion': 3,
                'completionReason': '截止完成',
                'expectedSummary': {
                    'totalCount': 2,
                    'submittedCount': 1,
                    'draftCount': 0,
                    'pendingCount': 1,
                    'closedIncompleteCount': 0,
                },
            },
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['data']['projectStatus'] == 'COMPLETED'
    assert completion.await_args.kwargs == {'request_id': 'request-http-9', 'trace_id': 'trace-http-9'}
    operation_log = queue.await_args.args[1]
    assert secret not in operation_log.oper_param
    assert 'answers' not in operation_log.oper_param
