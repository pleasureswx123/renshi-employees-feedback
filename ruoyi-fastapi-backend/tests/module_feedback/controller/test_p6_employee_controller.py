import inspect
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.routing import APIRoute

from common.aspect.interface_auth import CheckUserInterfaceAuth
from common.aspect.pre_auth import PreAuth
from common.context import RequestContext
from common.vo import PageModel
from exceptions.exception import ConflictException
from exceptions.handle import handle_exception
from module_admin.service.log_service import LogQueueService
from module_feedback.controller.employee_controller import employee_controller
from module_feedback.entity.vo.employee_vo import EmployeeProjectModel
from module_feedback.service.answer_service import FeedbackAnswerService
from module_feedback.service.employee_service import FeedbackEmployeeService

PERMISSIONS = {
    ('GET', '/feedback/employee/projects'): 'feedback:task:view',
    ('GET', '/feedback/employee/projects/{project_id}'): 'feedback:task:view',
    ('GET', '/feedback/employee/tasks/{assignment_id}'): 'feedback:task:view',
    ('PUT', '/feedback/employee/tasks/{assignment_id}/draft'): 'feedback:task:answer',
    ('POST', '/feedback/employee/tasks/{assignment_id}/submit'): 'feedback:task:submit',
    ('GET', '/feedback/employee/history'): 'feedback:history:view',
    ('GET', '/feedback/employee/history/{assignment_id}'): 'feedback:history:view',
}
USER_ID = 77
ERROR_QUESTION_ID = 2


def routes() -> list:
    return [route for route in employee_controller.routes if isinstance(route, APIRoute)]


def test_employee_routes_use_login_and_separate_permissions() -> None:
    actual = {(next(iter(route.methods)), route.path): route for route in routes()}
    assert set(actual) == set(PERMISSIONS)
    for key, route in actual.items():
        calls = [dependency.call for dependency in route.dependant.dependencies]
        assert any(isinstance(call, PreAuth) for call in calls)
        assert any(isinstance(call, CheckUserInterfaceAuth) and call.perm == PERMISSIONS[key] for call in calls)
        assert 'evaluator_id' not in inspect.signature(route.endpoint).parameters


def build_app(permissions: list[str]) -> FastAPI:
    app = FastAPI()
    handle_exception(app)
    app.include_router(employee_controller)
    user = SimpleNamespace(
        user=SimpleNamespace(user_id=USER_ID, user_name='p6-user', dept=None), permissions=permissions
    )

    async def current_user() -> Any:
        return user

    async def database() -> Any:
        return object()

    @app.middleware('http')
    async def login_context(request: Any, call_next: Any) -> Any:
        token = RequestContext.set_current_user(user)
        try:
            return await call_next(request)
        finally:
            RequestContext.reset_current_user(token)

    for route in routes():
        for dependency in route.dependant.dependencies:
            if isinstance(dependency.call, PreAuth) or dependency.name == 'user':
                app.dependency_overrides[dependency.call] = current_user
            elif dependency.name == 'db':
                app.dependency_overrides[dependency.call] = database
    return app


@pytest.mark.asyncio
async def test_actual_http_uses_current_user_and_rejects_identity_query(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AsyncMock(
        return_value=PageModel[EmployeeProjectModel](rows=[], total=0, pageNum=1, pageSize=20, hasNext=False)
    )
    monkeypatch.setattr(FeedbackEmployeeService, 'list_projects', service)
    app = build_app(['feedback:task:view'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        result = await client.get('/feedback/employee/projects')
        assert result.status_code == status.HTTP_200_OK and result.json()['total'] == 0
        assert service.call_args.args[1] == USER_ID
        injected = await client.get('/feedback/employee/projects?evaluatorUserId=1')
        assert injected.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        denied = await client.get('/feedback/employee/history')
        assert denied.json()['code'] == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['conflict', 'not_found', 'unexpected'])
async def test_logged_submission_preserves_status_and_never_records_answer_body(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    secret = '这是不得写入日志的员工原始答案'
    errors = {
        'conflict': ConflictException(
            message='答卷已变更', data={'validationIssues': [{'code': 'REQUIRED', 'pageId': 1, 'questionId': 2}]}
        ),
        'not_found': HTTPException(status_code=404, detail='无权访问'),
        'unexpected': RuntimeError(secret),
    }
    service = AsyncMock(side_effect=errors[failure])
    logs = AsyncMock()
    monkeypatch.setattr(FeedbackAnswerService, 'submit', service)
    monkeypatch.setattr(LogQueueService, 'enqueue_operation_log', logs)
    app = build_app(['feedback:task:submit'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(
            '/feedback/employee/tasks/3/submit',
            json={
                'versionId': 1,
                'lockVersion': 0,
                'lastPageId': 1,
                'submissionId': '621e027c-016f-4603-b650-18020d826aa1',
                'answers': [{'questionId': 1, 'textValue': secret}],
            },
        )
    expected = {'conflict': 409, 'not_found': 404, 'unexpected': 500}
    assert response.status_code == expected[failure]
    assert service.call_args.args[1:3] == (3, USER_ID)
    log = logs.call_args.args[1]
    assert not log.oper_param and not log.json_result
    assert secret not in str(log.model_dump()) and secret not in response.text
    if failure == 'conflict':
        assert response.json()['data']['validationIssues'][0]['questionId'] == ERROR_QUESTION_ID
