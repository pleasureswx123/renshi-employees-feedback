import inspect
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.routing import APIRoute

from common.aspect.pre_auth import PreAuth
from common.constant import HttpStatusConstant
from exceptions.exception import AuthException
from module_admin.service.login_service import LoginService
from module_feedback.controller.feedback_controller import feedback_controller, get_feedback_module_health


def get_health_route() -> APIRoute:
    return next(
        route
        for route in feedback_controller.routes
        if isinstance(route, APIRoute) and route.path == '/feedback/health'
    )


def test_feedback_health_route_uses_fixed_prefix_and_pre_auth() -> None:
    route = get_health_route()

    assert route.methods == {'GET'}
    assert len(route.dependant.dependencies) == 1
    assert isinstance(route.dependant.dependencies[0].call, PreAuth)


@pytest.mark.asyncio
async def test_feedback_health_requires_login_token() -> None:
    auth_dependency = get_health_route().dependant.dependencies[0].call
    request = SimpleNamespace(
        url=SimpleNamespace(path='/feedback/health'),
        method='GET',
        headers={},
    )

    with pytest.raises(AuthException) as exc_info:
        await auth_dependency(request, object())

    assert exc_info.value.message == '用户未登录，请先完成登录'


@pytest.mark.asyncio
async def test_feedback_health_accepts_authenticated_user() -> None:
    auth_dependency = get_health_route().dependant.dependencies[0].call
    request = SimpleNamespace(
        url=SimpleNamespace(path='/feedback/health'),
        method='GET',
        headers={'Authorization': 'Bearer valid-token'},
    )
    current_user = object()

    with patch.object(LoginService, 'get_current_user', new=AsyncMock(return_value=current_user)):
        result = await auth_dependency(request, object())

    assert result is current_user


@pytest.mark.asyncio
async def test_feedback_health_response_is_read_only_phase_probe() -> None:
    response = await inspect.unwrap(get_feedback_module_health)()
    payload = json.loads(response.body)

    assert payload['code'] == HttpStatusConstant.SUCCESS
    assert payload['data'] == {
        'module': 'feedback',
        'status': 'ready',
        'phase': 'P1',
        'apiPrefix': '/feedback',
    }
