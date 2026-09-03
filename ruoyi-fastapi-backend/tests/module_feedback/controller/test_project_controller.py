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
    ('GET', '/feedback/projects/{project_id}/participant-options'): 'feedback:participant:manage',
    ('GET', '/feedback/projects/{project_id}/publication-config'): [
        'feedback:participant:manage',
        'feedback:project:publish',
    ],
    ('PUT', '/feedback/projects/{project_id}/publication-config'): 'feedback:participant:manage',
    ('POST', '/feedback/projects/{project_id}/publish'): 'feedback:project:publish',
    ('GET', '/feedback/projects/{project_id}/progress'): 'feedback:progress:view',
    ('GET', '/feedback/projects/{project_id}/completion-precheck'): 'feedback:project:complete',
    ('POST', '/feedback/projects/{project_id}/complete'): 'feedback:project:complete',
}
EXPECTED_USER_SCOPE_COUNT = 3
EXPECTED_TARGET_SCOPE_COUNT = 3


def test_project_routes_use_fixed_permissions_and_data_scope() -> None:
    routes = [item for item in project_controller.routes if isinstance(item, APIRoute)]
    actual = {(next(iter(route.methods)), route.path): route for route in routes}

    assert set(actual) == set(EXPECTED_ROUTES)
    for route_key, permission in EXPECTED_ROUTES.items():
        route = actual[route_key]
        dependencies = [item.call for item in route.dependant.dependencies]
        assert any(isinstance(item, PreAuth) for item in dependencies)
        assert any(isinstance(item, CheckUserInterfaceAuth) and item.perm == permission for item in dependencies)
        if route_key != ('POST', '/feedback/projects'):
            assert any(isinstance(item, GetDataScope) for item in dependencies)


def test_project_routes_bind_feedback_project_data_scope_aliases() -> None:
    routes = [item for item in project_controller.routes if isinstance(item, APIRoute)]
    scoped_dependencies = [
        item.call for route in routes for item in route.dependant.dependencies if isinstance(item.call, GetDataScope)
    ]

    assert scoped_dependencies
    project_scopes = [item for item in scoped_dependencies if item.query_alias.__tablename__ == 'fb_project']
    user_scopes = [item for item in scoped_dependencies if item.query_alias.__tablename__ == 'sys_user']
    target_scopes = [item for item in scoped_dependencies if item.query_alias.__tablename__ == 'fb_project_target']

    assert project_scopes
    assert all(item.user_alias == 'owner_user_id' for item in project_scopes)
    assert all(item.dept_alias == 'owner_dept_id' for item in project_scopes)
    assert len(user_scopes) == EXPECTED_USER_SCOPE_COUNT
    assert all(item.user_alias == 'user_id' and item.dept_alias == 'dept_id' for item in user_scopes)
    assert len(target_scopes) == EXPECTED_TARGET_SCOPE_COUNT
    assert all(item.user_alias == 'target_user_id' and item.dept_alias == 'target_dept_id' for item in target_scopes)
