"""从实际注册路由导出评价接口权限和范围清单，不连接数据库。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.routing import APIRoute  # noqa: E402

from common.aspect.data_scope import GetDataScope  # noqa: E402
from common.aspect.interface_auth import CheckUserInterfaceAuth  # noqa: E402
from common.aspect.pre_auth import PreAuth  # noqa: E402
from module_feedback.controller.employee_controller import employee_controller  # noqa: E402
from module_feedback.controller.feedback_controller import feedback_controller  # noqa: E402
from module_feedback.controller.project_controller import project_controller  # noqa: E402
from module_feedback.controller.report_controller import report_controller  # noqa: E402

CONTROLLERS = (feedback_controller, project_controller, employee_controller, report_controller)


def feedback_routes() -> list[APIRoute]:
    return [route for controller in CONTROLLERS for route in controller.routes if isinstance(route, APIRoute)]


def audit_routes() -> list[dict[str, Any]]:
    rows = []
    for route in feedback_routes():
        dependencies = [dependency.call for dependency in route.dependant.dependencies]
        authentication = [dependency for dependency in dependencies if isinstance(dependency, PreAuth)]
        permissions = [dependency for dependency in dependencies if isinstance(dependency, CheckUserInterfaceAuth)]
        scopes = [dependency for dependency in dependencies if isinstance(dependency, GetDataScope)]
        if not authentication or any(dependency.exclude_routes for dependency in authentication):
            raise RuntimeError(f'评价接口缺少完整登录保护：{route.path}')
        if route.path != '/feedback/health' and not permissions:
            raise RuntimeError(f'评价业务接口缺少权限码：{route.path}')
        for method in sorted(route.methods):
            rows.append(  # noqa: PERF401
                {
                    'method': method,
                    'path': route.path,
                    'permissions': [permission.perm for permission in permissions],
                    'scope': [
                        {'table': scope.query_alias.__tablename__, 'user': scope.user_alias, 'dept': scope.dept_alias}
                        for scope in scopes
                    ],
                    'currentEmployee': route.path.startswith('/feedback/employee/'),
                    'endpoint': f'{route.endpoint.__module__}.{route.endpoint.__name__}',
                }
            )
    return sorted(rows, key=lambda row: (row['path'], row['method']))


if __name__ == '__main__':
    print(json.dumps({'routes': audit_routes()}, ensure_ascii=False, indent=2))
