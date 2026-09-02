"""为P6真实浏览器验收创建、核验和清理隔离测试夹具，不触碰开发库。"""

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from anyio import Path as AsyncPath  # noqa: E402
from redis.asyncio import Redis  # noqa: E402
from sqlalchemy import delete, select, update  # noqa: E402

from common.enums import RedisInitKeyConfig  # noqa: E402
from config.env import RedisConfig  # noqa: E402
from module_admin.entity.do.menu_do import SysMenu  # noqa: E402
from module_admin.entity.do.role_do import SysRole, SysRoleMenu  # noqa: E402
from module_admin.entity.do.user_do import SysUser, SysUserRole  # noqa: E402
from module_feedback.dao.answer_dao import FeedbackAnswerDao  # noqa: E402
from module_feedback.entity.do import FbAssignment, FbProject  # noqa: E402
from tests.module_feedback.service.p6_helpers import cleanup_p6_project, create_p6_project  # noqa: E402
from tests.module_feedback.service.test_p5_publication_flow_postgresql import create_test_session_factory  # noqa: E402
from utils.pwd_util import PwdUtil  # noqa: E402

CAPTCHA_KEY = f'{RedisInitKeyConfig.SYS_CONFIG.key}:sys.account.captchaEnabled'
TEST_REDIS_DATABASE = 3


def redis_client() -> Redis:
    return Redis(
        host=RedisConfig.redis_host,
        port=RedisConfig.redis_port,
        db=TEST_REDIS_DATABASE,
        username=RedisConfig.redis_username or None,
        password=RedisConfig.redis_password or None,
        decode_responses=True,
    )


async def prepare(path: Path) -> None:
    async_path = AsyncPath(path)
    if await async_path.exists():
        raise RuntimeError('夹具状态文件已存在，请先核验或清理，不覆盖旧夹具')
    engine, factory = create_test_session_factory()
    state = None
    role_ids = []
    captcha_changed = False
    old_captcha = None
    try:
        state = await create_p6_project(factory, publish=False, long_text=True)
        password = 'P6-' + uuid.uuid4().hex
        async with factory() as db:
            permissions = {
                'hr': ['feedback:project:list', 'feedback:participant:manage', 'feedback:project:publish'],
                'employee': [
                    'feedback:task:view',
                    'feedback:task:answer',
                    'feedback:task:submit',
                    'feedback:history:view',
                ],
            }
            for index, (kind, allowed) in enumerate(permissions.items()):
                role = SysRole(
                    role_name=f'P6验收{kind}',
                    role_key=f'p6_e2e_{uuid.uuid4().hex}',
                    role_sort=1,
                    data_scope='1',
                    status='0',
                )
                db.add(role)
                await db.flush()
                role_ids.append(role.role_id)
                menus = list(
                    (await db.scalars(select(SysMenu).where(SysMenu.perms.in_(allowed), SysMenu.status == '0'))).all()
                )
                if {menu.perms for menu in menus} != set(allowed):
                    raise RuntimeError('评价平台菜单权限不完整，请先升级到P6迁移head')
                db.add_all([SysRoleMenu(role_id=role.role_id, menu_id=menu.menu_id) for menu in menus])
                db.add(SysUserRole(user_id=state['user_ids'][index], role_id=role.role_id))
            await db.execute(
                update(SysUser)
                .where(SysUser.user_id.in_(state['user_ids']))
                .values(password=PwdUtil.get_password_hash(password))
            )
            await db.execute(
                update(SysUser)
                .where(SysUser.user_id == state['user_ids'][0])
                .values(nick_name='验收被评价人甲跨部门协作与复杂任务负责人')
            )
            await db.execute(
                update(SysUser)
                .where(SysUser.user_id == state['user_ids'][2])
                .values(nick_name='验收被评价人乙跨部门协作与复杂任务负责人')
            )
            users = list((await db.scalars(select(SysUser).where(SysUser.user_id.in_(state['user_ids'])))).all())
            user_names = {user.user_id: user.user_name for user in users}
            await db.commit()
        old_captcha = await disable_captcha()
        captcha_changed = True
        result = {
            'database': 'ruoyi_feedback_test',
            'redisDatabase': TEST_REDIS_DATABASE,
            'project_id': state['project_id'],
            'user_ids': state['user_ids'],
            'role_ids': role_ids,
            'hr': user_names[state['user_ids'][0]],
            'employee': user_names[state['user_ids'][1]],
            'password': password,
            'oldCaptcha': old_captcha,
        }
        await async_path.parent.mkdir(parents=True, exist_ok=True)
        await async_path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        print(
            json.dumps({'prepared': True, 'projectId': state['project_id'], 'stateFile': str(path)}, ensure_ascii=False)
        )
    except Exception:
        if captcha_changed:
            await restore_captcha(old_captcha)
        if state:
            async with factory() as db:
                await db.execute(delete(SysUserRole).where(SysUserRole.user_id.in_(state['user_ids'])))
                await db.execute(delete(SysRoleMenu).where(SysRoleMenu.role_id.in_(role_ids)))
                await db.execute(delete(SysRole).where(SysRole.role_id.in_(role_ids)))
                await db.commit()
            await cleanup_p6_project(factory, state)
        raise
    finally:
        await engine.dispose()


async def inspect_or_cleanup(path: Path, *, cleanup: bool) -> None:
    async_path = AsyncPath(path)
    state = json.loads(await async_path.read_text(encoding='utf-8'))
    if state.get('database') != 'ruoyi_feedback_test' or state.get('redisDatabase') != TEST_REDIS_DATABASE:
        raise RuntimeError('只允许隔离测试库夹具')
    engine, factory = create_test_session_factory()
    try:
        async with factory() as db:
            project = await db.get(FbProject, state['project_id'])
            if (
                project is None
                or not project.project_name.startswith('P5闭环-')
                or project.owner_user_id not in state['user_ids']
            ):
                raise RuntimeError('项目与测试夹具身份不符，拒绝操作')
            tasks = list(
                (await db.scalars(select(FbAssignment).where(FbAssignment.project_id == project.project_id))).all()
            )
            summary = []
            for task in tasks:
                sheet = await FeedbackAnswerDao.get_by_assignment_id(db, task.assignment_id)
                summary.append(
                    {
                        'taskId': task.assignment_id,
                        'status': task.status,
                        'answerCount': len(sheet.answers) if sheet else 0,
                        'rawScore': str(sheet.raw_total_score) if sheet else None,
                    }
                )
            print(
                json.dumps(
                    {'projectId': project.project_id, 'projectStatus': project.status, 'tasks': summary},
                    ensure_ascii=False,
                )
            )
            if cleanup:
                role_keys = list(
                    (await db.scalars(select(SysRole.role_key).where(SysRole.role_id.in_(state['role_ids'])))).all()
                )
                if any(not key.startswith('p6_e2e_') for key in role_keys):
                    raise RuntimeError('存在不属于本夹具的角色，拒绝清理')
                await db.execute(delete(SysUserRole).where(SysUserRole.user_id.in_(state['user_ids'])))
                await db.execute(delete(SysRoleMenu).where(SysRoleMenu.role_id.in_(state['role_ids'])))
                await db.execute(delete(SysRole).where(SysRole.role_id.in_(state['role_ids'])))
                await db.commit()
        if cleanup:
            await cleanup_p6_project(factory, state)
            await restore_captcha(state['oldCaptcha'])
            await async_path.unlink()
            print('仅本次验收项目、账号和角色已清理，测试Redis验证码配置已恢复。')
    finally:
        await engine.dispose()


async def disable_captcha() -> str | None:
    redis = redis_client()
    try:
        previous = await redis.get(CAPTCHA_KEY)
        await redis.set(CAPTCHA_KEY, 'false')
        return previous
    finally:
        await redis.aclose()


async def restore_captcha(value: str | None) -> None:
    redis = redis_client()
    try:
        if value is None:
            await redis.delete(CAPTCHA_KEY)
        else:
            await redis.set(CAPTCHA_KEY, value)
    finally:
        await redis.aclose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'inspect', 'cleanup'])
    parser.add_argument('--state', type=Path, default=BACKEND_DIR / '.tmp' / 'p6-e2e-state.json')
    args = parser.parse_args()
    state_path = args.state.resolve()
    if not state_path.is_relative_to(BACKEND_DIR / '.tmp'):
        raise RuntimeError('夹具凭据仅允许写入后端.tmp目录')
    asyncio.run(
        prepare(state_path)
        if args.action == 'prepare'
        else inspect_or_cleanup(state_path, cleanup=args.action == 'cleanup')
    )
