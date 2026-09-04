import os
import uuid
from typing import Any

import pytest
from sqlalchemy import delete, func, select, true, update

from exceptions.exception import ConflictException
from module_admin.entity.do.user_do import SysUser, SysUserRole
from module_admin.entity.vo.user_vo import UserModel
from module_feedback.constants import BUILTIN_ADMIN_USER_ID
from module_feedback.dao import FeedbackPublicationDao
from module_feedback.entity.do import FbAssignment, FbEvaluatorSelection, FbProject, FbProjectTarget
from module_feedback.entity.vo import ParticipantOptionQueryModel, PublishRequestModel
from module_feedback.service import FeedbackPublicationService
from tests.module_feedback.service.test_p5_publication_flow_postgresql import (
    build_config_payload,
    cleanup_project,
    create_ready_project,
    create_test_session_factory,
)

pytestmark = pytest.mark.skipif(
    os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') != '1', reason='仅在显式启用隔离PostgreSQL测试时运行'
)


def publish_request(config: Any) -> PublishRequestModel:
    return PublishRequestModel(
        projectLockVersion=config.project_lock_version,
        versionId=config.version_id,
        versionLockVersion=config.version_lock_version,
    )


@pytest.mark.asyncio
async def test_candidates_exclude_builtin_identity_but_keep_same_department_admin_role_employee() -> None:
    engine, session_factory = create_test_session_factory()
    state = None
    try:
        state = await create_ready_project(session_factory, uuid.uuid4().hex[:12])
        employee_id = state['user_ids'][0]
        async with session_factory() as db:
            admin = await db.get(SysUser, BUILTIN_ADMIN_USER_ID)
            assert admin is not None
            assert UserModel(userId=admin.user_id).admin is True
            assert UserModel(userId=employee_id).admin is False
            # 同部门、同昵称且具有管理角色的普通员工仍可参评。
            employee = await db.get(SysUser, employee_id)
            employee.dept_id = admin.dept_id
            employee.nick_name = admin.nick_name
            role_ids = list(
                (await db.scalars(select(SysUserRole.role_id).where(SysUserRole.user_id == admin.user_id))).all()
            )
            assert role_ids
            db.add_all([SysUserRole(user_id=employee_id, role_id=role_id) for role_id in role_ids])
            await db.flush()
            scope = SysUser.user_id.in_([BUILTIN_ADMIN_USER_ID, employee_id])
            options = await FeedbackPublicationService.list_participant_options(
                db, state['project_id'], ParticipantOptionQueryModel(pageNum=1, pageSize=1), true(), scope
            )
            assert options.total == 1
            assert options.has_next is False
            assert [item.user_id for item in options.rows] == [employee_id]
            assert options.rows[0].available is True
            searched = await FeedbackPublicationService.list_participant_options(
                db, state['project_id'], ParticipantOptionQueryModel(keyword=admin.user_name), true(), scope
            )
            assert searched.total == 0
            for lock in (False, True):
                available = await FeedbackPublicationDao.get_available_participants(
                    db, {BUILTIN_ADMIN_USER_ID, employee_id}, true(), lock=lock
                )
                assert set(available) == {employee_id}
            # 内置账号改名也不能进入候选名单；事务回滚，不改写测试库既有账号。
            admin.user_name = f'maint-{uuid.uuid4().hex[:10]}'
            admin.nick_name = '维护专用账号'
            await db.flush()
            renamed = await FeedbackPublicationService.list_participant_options(
                db, state['project_id'], ParticipantOptionQueryModel(keyword=admin.user_name), true(), scope
            )
            assert renamed.total == 0
            await db.rollback()
    finally:
        if state:
            await cleanup_project(session_factory, state)
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('as_target', [True, False], ids=['被评价人', '评价人'])
async def test_save_and_legacy_draft_publish_reject_builtin_admin(as_target: bool) -> None:
    engine, session_factory = create_test_session_factory()
    state = None
    try:
        state = await create_ready_project(session_factory, uuid.uuid4().hex[:12])
        config = state['config']
        target_id = BUILTIN_ADMIN_USER_ID if as_target else state['user_ids'][0]
        evaluator_id = state['user_ids'][1] if as_target else BUILTIN_ADMIN_USER_ID
        path = 'targets' if as_target else 'evaluatorSelections'
        async with session_factory() as db:
            with pytest.raises(ConflictException, match='系统维护账号不能参与评价') as error:
                await FeedbackPublicationService.save_config(
                    db,
                    state['project_id'],
                    build_config_payload(config, target_id, evaluator_id),
                    'admin',
                    true(),
                    true(),
                )
            assert error.value.data['unavailableUserIds'] == [BUILTIN_ADMIN_USER_ID]
            assert error.value.data['validationIssues'][0]['path'] == path
            unchanged = await FeedbackPublicationService.get_config(db, state['project_id'], true())
            assert unchanged.model_dump() == config.model_dump()

            # 在本次创建的测试项目中构造旧版本曾允许保存的配置。
            await db.execute(delete(FbEvaluatorSelection).where(FbEvaluatorSelection.project_id == state['project_id']))
            await db.execute(
                update(FbProjectTarget)
                .where(FbProjectTarget.project_id == state['project_id'])
                .values(target_user_id=target_id, target_user_name='旧配置中的被评价人')
            )
            target = await db.scalar(select(FbProjectTarget).where(FbProjectTarget.project_id == state['project_id']))
            for relation in config.relations:
                if relation.relation_code in ('REL_SELF', 'REL_PEER'):
                    db.add(
                        FbEvaluatorSelection(
                            project_id=state['project_id'],
                            version_id=state['version_id'],
                            target_id=target.target_id,
                            target_user_id=target_id,
                            relation_id=relation.relation_id,
                            evaluator_user_id=target_id if relation.relation_code == 'REL_SELF' else evaluator_id,
                            create_by='legacy-test',
                            update_by='legacy-test',
                        )
                    )
            await db.commit()
            legacy = await FeedbackPublicationService.get_config(db, state['project_id'], true())
            assert legacy.is_publish_ready is False
            assert any(
                issue.code == 'SYSTEM_ACCOUNT_NOT_ALLOWED' and issue.path == path for issue in legacy.validation_issues
            )
            assert (
                next(item for item in legacy.configured_participants if item.user_id == BUILTIN_ADMIN_USER_ID).available
                is False
            )
            with pytest.raises(ConflictException, match='系统维护账号不能参与评价'):
                await FeedbackPublicationService.publish(
                    db,
                    state['project_id'],
                    publish_request(legacy),
                    BUILTIN_ADMIN_USER_ID,
                    'admin',
                    true(),
                    true(),
                )
            assert (await db.get(FbProject, state['project_id'])).status == 'PREPARING'
            assert (
                await db.scalar(
                    select(func.count()).select_from(FbAssignment).where(FbAssignment.project_id == state['project_id'])
                )
                == 0
            )
            # 移除系统账号后仍可正常保存；管理者本人是admin不影响操作。
            fixed = await FeedbackPublicationService.save_config(
                db,
                state['project_id'],
                build_config_payload(legacy, *state['user_ids'][:2]),
                'admin',
                true(),
                true(),
            )
            assert fixed.is_publish_ready is True
            published = await FeedbackPublicationService.publish(
                db,
                state['project_id'],
                publish_request(fixed),
                BUILTIN_ADMIN_USER_ID,
                'admin',
                true(),
                true(),
            )
            assert published.already_published is False
    finally:
        if state:
            await cleanup_project(session_factory, state)
        await engine.dispose()


@pytest.mark.asyncio
async def test_published_history_keeps_system_account_snapshot_and_idempotent_result() -> None:
    engine, session_factory = create_test_session_factory()
    state = None
    try:
        state = await create_ready_project(session_factory, uuid.uuid4().hex[:12])
        config = state['config']
        async with session_factory() as db:
            await FeedbackPublicationService.publish(
                db,
                state['project_id'],
                publish_request(config),
                BUILTIN_ADMIN_USER_ID,
                'admin',
                true(),
                true(),
            )
            # 只在隔离测试项目内构造历史快照，不修改任何既有项目。
            await db.execute(
                update(FbEvaluatorSelection)
                .where(
                    FbEvaluatorSelection.project_id == state['project_id'],
                    FbEvaluatorSelection.evaluator_user_id == state['user_ids'][1],
                )
                .values(evaluator_user_id=BUILTIN_ADMIN_USER_ID)
            )
            await db.execute(
                update(FbAssignment)
                .where(
                    FbAssignment.project_id == state['project_id'],
                    FbAssignment.evaluator_user_id == state['user_ids'][1],
                )
                .values(evaluator_user_id=BUILTIN_ADMIN_USER_ID, evaluator_user_name='历史维护账号')
            )
            await db.commit()
            frozen = await FeedbackPublicationService.get_config(db, state['project_id'], true())
            assert frozen.editable is False
            assert not any(issue.code == 'SYSTEM_ACCOUNT_NOT_ALLOWED' for issue in frozen.validation_issues)
            assert (
                next(item for item in frozen.configured_participants if item.user_id == BUILTIN_ADMIN_USER_ID).nick_name
                == '历史维护账号'
            )
            assert frozen.frozen_details.published_by == BUILTIN_ADMIN_USER_ID
            repeated = await FeedbackPublicationService.publish(
                db,
                state['project_id'],
                publish_request(config),
                BUILTIN_ADMIN_USER_ID,
                'admin',
                true(),
                true(),
            )
            assert repeated.already_published is True
            after = await FeedbackPublicationService.get_config(db, state['project_id'], true())
            assert after.model_dump() == frozen.model_dump()
    finally:
        if state:
            await cleanup_project(session_factory, state)
        await engine.dispose()
