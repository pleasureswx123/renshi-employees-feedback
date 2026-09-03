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
from module_admin.entity.do.dept_do import SysDept  # noqa: E402
from module_admin.entity.do.menu_do import SysMenu  # noqa: E402
from module_admin.entity.do.role_do import SysRole, SysRoleMenu  # noqa: E402
from module_admin.entity.do.user_do import SysUser, SysUserRole  # noqa: E402
from module_feedback.dao.answer_dao import FeedbackAnswerDao  # noqa: E402
from module_feedback.entity.do import FbAssignment, FbProject, FbProjectCompletionAudit, FbScoreResult  # noqa: E402
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


def iso_or_none(value: object) -> str | None:
    return value.isoformat() if value is not None else None


def answer_sheet_snapshot(sheet: object) -> dict | None:
    if sheet is None:
        return None
    return {
        'sheetId': sheet.sheet_id,
        'versionId': sheet.version_id,
        'status': sheet.status,
        'lastPageId': sheet.last_page_id,
        'answeredCount': sheet.answered_count,
        'rawTotalScore': str(sheet.raw_total_score) if sheet.raw_total_score is not None else None,
        'submissionSnapshot': sheet.submission_snapshot,
        'savedTime': iso_or_none(sheet.saved_time),
        'submittedTime': iso_or_none(sheet.submitted_time),
        'lockVersion': sheet.lock_version,
        'answers': [
            {
                'answerId': answer.answer_id,
                'questionId': answer.question_id,
                'answerType': answer.answer_type,
                'optionId': answer.option_id,
                'numericValue': str(answer.numeric_value) if answer.numeric_value is not None else None,
                'textValue': answer.text_value,
                'reason': answer.reason,
                'rawScore': str(answer.raw_score) if answer.raw_score is not None else None,
                'valueSnapshot': answer.value_snapshot,
                'createTime': iso_or_none(answer.create_time),
                'updateTime': iso_or_none(answer.update_time),
            }
            for answer in sorted(sheet.answers, key=lambda row: row.question_id)
        ],
    }


async def prepare(path: Path) -> None:  # noqa: PLR0915
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
            owner = await db.get(SysUser, state['user_ids'][0])
            other_dept_id = await db.scalar(
                select(SysDept.dept_id)
                .where(SysDept.del_flag == '0', SysDept.status == '0', SysDept.dept_id != owner.dept_id)
                .order_by(SysDept.dept_id)
                .limit(1)
            )
            if other_dept_id is None:
                raise RuntimeError('真实数据范围验收至少需要两个启用部门')
            await db.execute(
                update(SysUser).where(SysUser.user_id == state['user_ids'][2]).values(dept_id=other_dept_id)
            )
            full_hr = SysUser(
                dept_id=owner.dept_id,
                user_name=f'p7hr-{uuid.uuid4().hex[:16]}',
                nick_name='P7全量范围验收HR',
                password=PwdUtil.get_password_hash(password),
                status='0',
                del_flag='0',
            )
            db.add(full_hr)
            await db.flush()
            state['user_ids'].append(int(full_hr.user_id))
            report_hr = SysUser(
                dept_id=owner.dept_id,
                user_name=f'p8report-{uuid.uuid4().hex[:14]}',
                nick_name='P8仅报告权限验收HR',
                password=PwdUtil.get_password_hash(password),
                status='0',
                del_flag='0',
            )
            db.add(report_hr)
            await db.flush()
            state['user_ids'].append(int(report_hr.user_id))
            role_specs = [
                (
                    'partial_hr',
                    0,
                    '3',
                    [
                        'feedback:project:list',
                        'feedback:progress:view',
                        'feedback:project:complete',
                        'feedback:task:view',
                        'feedback:task:answer',
                        'feedback:task:submit',
                    ],
                ),
                (
                    'employee',
                    1,
                    '5',
                    [
                        'feedback:task:view',
                        'feedback:task:answer',
                        'feedback:task:submit',
                        'feedback:history:view',
                    ],
                ),
                (
                    'hr',
                    3,
                    '1',
                    [
                        'feedback:project:list',
                        'feedback:participant:manage',
                        'feedback:project:publish',
                        'feedback:progress:view',
                        'feedback:project:complete',
                        'feedback:report:view',
                        'feedback:answer:view',
                    ],
                ),
                ('report_hr', 4, '1', ['feedback:report:view']),
            ]
            role_specs[0][3].append('feedback:report:view')
            for kind, user_index, data_scope, allowed in role_specs:
                role = SysRole(
                    role_name=f'P6验收{kind}',
                    role_key=f'p6_e2e_{uuid.uuid4().hex}',
                    role_sort=1,
                    data_scope=data_scope,
                    status='0',
                )
                db.add(role)
                await db.flush()
                role_ids.append(role.role_id)
                menus = list(
                    (await db.scalars(select(SysMenu).where(SysMenu.perms.in_(allowed), SysMenu.status == '0'))).all()
                )
                if {menu.perms for menu in menus} != set(allowed):
                    raise RuntimeError('评价平台菜单权限不完整，请先升级到P7迁移head')
                db.add_all([SysRoleMenu(role_id=role.role_id, menu_id=menu.menu_id) for menu in menus])
                db.add(SysUserRole(user_id=state['user_ids'][user_index], role_id=role.role_id))
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
            'hr': user_names[state['user_ids'][3]],
            'report_hr': user_names[state['user_ids'][4]],
            'partial_hr': user_names[state['user_ids'][0]],
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
            completion_audits = list(
                (
                    await db.scalars(
                        select(FbProjectCompletionAudit)
                        .where(FbProjectCompletionAudit.project_id == project.project_id)
                        .order_by(FbProjectCompletionAudit.audit_id)
                    )
                ).all()
            )
            summary = []
            for task in tasks:
                sheet = await FeedbackAnswerDao.get_by_assignment_id(db, task.assignment_id)
                summary.append(
                    {
                        'taskId': task.assignment_id,
                        'status': task.status,
                        'lockVersion': task.lock_version,
                        'savedTime': iso_or_none(task.saved_time),
                        'submittedTime': iso_or_none(task.submitted_time),
                        'closedTime': iso_or_none(task.closed_time),
                        'answerCount': len(sheet.answers) if sheet else 0,
                        'rawScore': str(sheet.raw_total_score) if sheet else None,
                        'answerSheet': answer_sheet_snapshot(sheet),
                    }
                )
            print(
                json.dumps(
                    {
                        'projectId': project.project_id,
                        'projectStatus': project.status,
                        'projectCompletedBy': project.completed_by,
                        'projectCompletedTime': iso_or_none(project.completed_time),
                        'projectCompletionReason': project.completion_reason,
                        'tasks': summary,
                        'scoreResults': [
                            {
                                'targetUserId': row.target_user_id,
                                'resultType': row.result_type,
                                'score': str(row.score) if row.score is not None else None,
                                'calculationVersion': row.calculation_version,
                            }
                            for row in await db.scalars(
                                select(FbScoreResult)
                                .where(
                                    FbScoreResult.project_id == project.project_id,
                                )
                                .order_by(FbScoreResult.result_id)
                            )
                        ],
                        'completionAudits': [
                            {
                                'result': audit.result,
                                'operatorUserId': audit.operator_user_id,
                                'beforeTotalCount': audit.before_total_count,
                                'beforeSubmittedCount': audit.before_submitted_count,
                                'beforeDraftCount': audit.before_draft_count,
                                'beforePendingCount': audit.before_pending_count,
                                'beforeClosedIncompleteCount': audit.before_closed_incomplete_count,
                                'closedIncompleteCount': audit.closed_assignment_count,
                                'completionReason': audit.completion_reason,
                                'completedTime': iso_or_none(audit.completed_time),
                            }
                            for audit in completion_audits
                        ],
                    },
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
