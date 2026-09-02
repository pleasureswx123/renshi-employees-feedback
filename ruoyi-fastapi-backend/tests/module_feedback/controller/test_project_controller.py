from fastapi.routing import APIRoute

from common.aspect.data_scope import GetDataScope
from common.aspect.interface_auth import CheckUserInterfaceAuth
from common.aspect.pre_auth import PreAuth
from module_feedback.controller.project_controller import project_controller

EXPECTED_ROUTES = {
    ('GET', '/feedback/projects'): 'feedback:project:list',
    ('POST', '/feedback/projects'): 'feedback:project:add',
    ('GET', '/feedback/projects/{project_id}'): 'feedback:project:list',
    ('PUT', '/feedback/projects/{project_id}'): 'feedback:project:edit',
    ('DELETE', '/feedback/projects/{project_id}'): 'feedback:project:remove',
    ('GET', '/feedback/projects/{project_id}/questionnaire-draft'): 'feedback:questionnaire:edit',
    ('PUT', '/feedback/projects/{project_id}/questionnaire-draft'): 'feedback:questionnaire:edit',
}


def test_project_routes_use_fixed_permissions_and_data_scope() -> None:
    routes = [item for item in project_controller.routes if isinstance(item, APIRoute)]
    actual = {(next(iter(route.methods)), route.path): route for route in routes}

    assert set(actual) == set(EXPECTED_ROUTES)
    for route_key, permission in EXPECTED_ROUTES.items():
        route = actual[route_key]
        dependencies = [item.call for item in route.dependant.dependencies]
        assert any(isinstance(item, PreAuth) for item in dependencies)
        assert any(isinstance(item, CheckUserInterfaceAuth) and item.perm == permission for item in dependencies)
        if route_key[0] != 'POST':
            assert any(isinstance(item, GetDataScope) for item in dependencies)


def test_project_routes_bind_feedback_project_data_scope_aliases() -> None:
    routes = [item for item in project_controller.routes if isinstance(item, APIRoute)]
    scoped_dependencies = [
        item.call for route in routes for item in route.dependant.dependencies if isinstance(item.call, GetDataScope)
    ]

    assert scoped_dependencies
    assert all(item.user_alias == 'owner_user_id' for item in scoped_dependencies)
    assert all(item.dept_alias == 'owner_dept_id' for item in scoped_dependencies)
