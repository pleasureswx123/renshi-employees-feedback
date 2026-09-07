import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, select, text

from common.aspect.data_scope import GetDataScope
from exceptions.exception import ServiceException
from module_admin.controller.user_controller import query_detail_system_user
from module_admin.dao.user_dao import UserDao
from module_admin.entity.do.dept_do import SysDept
from module_admin.entity.do.user_do import SysUser
from module_admin.service.user_service import UserService


@pytest.mark.parametrize(
    ('admin', 'scopes', 'expected'),
    [
        (False, ['1'], [100, 101]),
        (False, ['3'], [100]),
        (False, ['5'], [100]),
        (False, ['3', '1'], [100, 101]),
        (False, [], []),
        (True, [], [1, 100, 101]),
    ],
)
def test_user_scope_hides_builtin_admin(admin: bool, scopes: list[str], expected: list[int]) -> None:
    # 用真实 SQL 执行验证筛选结果，避免只断言 SQL 字符串。
    user = SimpleNamespace(
        admin=admin,
        user_id=1 if admin else 100,
        dept_id=10,
        role=[SimpleNamespace(role_id=index + 2, data_scope=scope) for index, scope in enumerate(scopes)],
    )
    with (
        patch('common.aspect.data_scope.DependencyUtil.check_exclude_routes'),
        patch('common.aspect.data_scope.RequestContext.get_current_user', return_value=SimpleNamespace(user=user)),
    ):
        condition = GetDataScope(SysUser)(SimpleNamespace())

    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE sys_user (user_id INTEGER, dept_id INTEGER)'))
        connection.execute(text('INSERT INTO sys_user VALUES (1, 10), (100, 10), (101, 20)'))
        assert list(connection.scalars(select(SysUser.user_id).where(condition).order_by(SysUser.user_id))) == expected
        # 猜测用户 ID 的详情查询也不能绕过该条件。
        visible_admin = connection.scalar(select(SysUser.user_id).where(condition, SysUser.user_id == 1))
        assert visible_admin == (1 if admin else None)
    engine.dispose()


def test_department_scope_does_not_hide_department_one() -> None:
    user = SimpleNamespace(admin=False, user_id=100, dept_id=1, role=[SimpleNamespace(role_id=2, data_scope='1')])
    with (
        patch('common.aspect.data_scope.DependencyUtil.check_exclude_routes'),
        patch('common.aspect.data_scope.RequestContext.get_current_user', return_value=SimpleNamespace(user=user)),
    ):
        condition = GetDataScope(SysDept)(SimpleNamespace())
    assert str(condition) == 'true'


@pytest.mark.asyncio
async def test_detail_endpoint_denies_invisible_user_before_loading_details() -> None:
    with (
        patch.object(UserDao, 'get_user_list', new=AsyncMock(return_value=[])),
        patch.object(UserService, 'user_detail_services', new_callable=AsyncMock) as load_details,
    ):
        with pytest.raises(ServiceException) as error:
            await inspect.unwrap(query_detail_system_user)(
                SimpleNamespace(),
                SimpleNamespace(),
                SimpleNamespace(user=SimpleNamespace(admin=False)),
                SysUser.user_id != 1,
                1,
            )
        assert error.value.message == '没有权限访问用户数据'
        load_details.assert_not_awaited()
