import asyncio
import os
import uuid
from typing import Any

import pytest
from sqlalchemy import delete, false, func, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config.database import create_async_db_engine, create_async_session_factory
from config.env import DataSourceSettings
from exceptions.exception import ConflictException
from module_admin.entity.do.dept_do import SysDept
from module_admin.entity.do.user_do import SysUser
from module_feedback.dao import FeedbackAssignmentDao, FeedbackPublicationDao
from module_feedback.entity.do import (
    FbAssignment,
    FbEvaluatorSelection,
    FbProject,
    FbProjectTarget,
    FbQuestionnaireVersion,
)
from module_feedback.entity.vo import (
    ParticipantOptionQueryModel,
    ProjectCreateModel,
    PublicationConfigSaveModel,
    PublishRequestModel,
    QuestionnaireDraftSaveModel,
)
from module_feedback.service import (
    FeedbackProjectService,
    FeedbackPublicationService,
    FeedbackQuestionnaireService,
)
from scripts.feedback_p0_database_precheck import build_source_payload

RUN_POSTGRES_TESTS = os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') == '1'
EXPECTED_ASSIGNMENT_COUNT = 2
TEST_USER_COUNT = 3
PARTICIPANT_PAGE_SIZE = 2

pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES_TESTS,
    reason='仅在显式启用隔离PostgreSQL测试时运行',
)


def build_ready_questionnaire(version_id: int, lock_version: int) -> QuestionnaireDraftSaveModel:
    return QuestionnaireDraftSaveModel(
        versionId=version_id,
        lockVersion=lock_version,
        title='P5发布问卷',
        pages=[
            {
                'pageCode': 'P_PUBLISH',
                'pageTitle': '发布问卷',
                'sortOrder': 1,
                'questions': [
                    {
                        'questionCode': 'Q_SCORE',
                        'questionType': 'STAR_RATING',
                        'title': '协作表现',
                        'isRequired': True,
                        'isScored': True,
                        'minScore': '1',
                        'maxScore': '5',
                        'decimalPlaces': 0,
                        'config': {},
                        'sortOrder': 1,
                        'options': [],
                    }
                ],
            }
        ],
        indicators=[
            {
                'indicatorCode': 'I_SCORE',
                'indicatorName': '协作能力',
                'weight': '100.0000',
                'sortOrder': 1,
                'questionCodes': ['Q_SCORE'],
            }
        ],
    )


def build_config_payload(config: Any, target_user_id: int, evaluator_user_id: int) -> PublicationConfigSaveModel:
    relations = []
    for relation in config.relations:
        payload = {
            'relationCode': relation.relation_code,
            'relationType': relation.relation_type.value,
            'relationName': relation.relation_name,
            'isEnabled': relation.is_enabled,
            'participatesInScore': relation.participates_in_score,
            'weight': str(relation.weight),
            'sortOrder': relation.sort_order,
        }
        if relation.relation_code == 'REL_PEER':
            payload.update({'isEnabled': True, 'participatesInScore': True, 'weight': '100.0000'})
        relations.append(payload)
    return PublicationConfigSaveModel(
        projectLockVersion=config.project_lock_version,
        versionId=config.version_id,
        versionLockVersion=config.version_lock_version,
        targets=[{'targetUserId': target_user_id}],
        relations=relations,
        evaluatorSelections=[
            {
                'targetUserId': target_user_id,
                'relationCode': 'REL_PEER',
                'evaluatorUserIds': [evaluator_user_id],
            }
        ],
    )


async def create_test_users(db: AsyncSession, marker: str) -> tuple[list[int], int | None]:
    dept_id = await db.scalar(
        select(SysDept.dept_id).where(SysDept.del_flag == '0', SysDept.status == '0').order_by(SysDept.dept_id).limit(1)
    )
    users = [
        SysUser(
            dept_id=dept_id,
            user_name=f'{marker}-{index}',
            nick_name=f'P5测试用户{index}',
            status='0',
            del_flag='0',
        )
        for index in range(1, TEST_USER_COUNT + 1)
    ]
    db.add_all(users)
    await db.flush()
    user_ids = [int(item.user_id) for item in users]
    await db.commit()
    return user_ids, int(dept_id) if dept_id is not None else None


async def create_ready_project(
    session_factory: async_sessionmaker[AsyncSession],
    marker: str,
) -> dict[str, Any]:
    state: dict[str, Any] = {'user_ids': []}
    try:
        async with session_factory() as db:
            user_ids, _ = await create_test_users(db, marker)
            state['user_ids'] = user_ids
            created = await FeedbackProjectService.create_project(
                db,
                ProjectCreateModel(projectName=f'P5闭环-{marker}'),
                owner_user_id=user_ids[0],
                owner_dept_id=(await db.get(SysUser, user_ids[0])).dept_id,
                operator_name='p5-test',
            )
            state['project_id'] = created.project_id
            draft = await FeedbackQuestionnaireService.get_draft(db, created.project_id, true())
            await FeedbackQuestionnaireService.save_draft(
                db,
                created.project_id,
                build_ready_questionnaire(draft.version_id, draft.lock_version),
                'p5-test',
                true(),
            )
            config = await FeedbackPublicationService.get_config(db, created.project_id, true())
            payload = build_config_payload(config, user_ids[0], user_ids[1])
            with pytest.raises(ConflictException) as exc_info:
                await FeedbackPublicationService.save_config(
                    db,
                    created.project_id,
                    payload,
                    'p5-test',
                    true(),
                    false(),
                )
            assert '数据范围' in exc_info.value.message
            saved = await FeedbackPublicationService.save_config(
                db,
                created.project_id,
                payload,
                'p5-test',
                true(),
                true(),
            )
            state.update({'version_id': saved.version_id, 'config': saved})
            return state
    except Exception:
        if 'project_id' in state:
            await cleanup_project(session_factory, state)
        elif state['user_ids']:
            async with session_factory() as cleanup_db:
                await cleanup_db.execute(delete(SysUser).where(SysUser.user_id.in_(state['user_ids'])))
                await cleanup_db.commit()
        raise


async def cleanup_project(
    session_factory: async_sessionmaker[AsyncSession],
    state: dict[str, Any],
) -> None:
    async with session_factory() as db:
        project_id = state['project_id']
        await db.execute(delete(FbAssignment).where(FbAssignment.project_id == project_id))
        await db.execute(delete(FbEvaluatorSelection).where(FbEvaluatorSelection.project_id == project_id))
        await db.execute(delete(FbProjectTarget).where(FbProjectTarget.project_id == project_id))
        await db.execute(
            update(FbProject)
            .where(FbProject.project_id == project_id)
            .values(
                status='PREPARING',
                current_questionnaire_version_id=None,
                published_by=None,
                published_time=None,
            )
        )
        await db.execute(delete(FbQuestionnaireVersion).where(FbQuestionnaireVersion.project_id == project_id))
        await db.execute(delete(FbProject).where(FbProject.project_id == project_id))
        await db.execute(delete(SysUser).where(SysUser.user_id.in_(state['user_ids'])))
        await db.commit()


def create_test_session_factory() -> tuple[Any, async_sessionmaker[AsyncSession]]:
    source = DataSourceSettings(**build_source_payload('ruoyi_feedback_test'))
    engine = create_async_db_engine(config=source)
    return engine, create_async_session_factory(engine)


@pytest.mark.asyncio
async def test_p5_configuration_publish_snapshot_idempotency_and_read_only() -> None:  # noqa: PLR0915
    engine, session_factory = create_test_session_factory()
    state: dict[str, Any] | None = None
    try:
        state = await create_ready_project(session_factory, uuid.uuid4().hex[:12])
        config = state['config']
        target_user_id, evaluator_user_id, publisher_user_id = state['user_ids']
        assert config.is_publish_ready is True
        assert config.preview.assignment_count == EXPECTED_ASSIGNMENT_COUNT
        assert [item.relation_code for item in config.evaluator_selections] == ['REL_PEER', 'REL_SELF']

        async with session_factory() as db:
            assignment_count = await db.scalar(
                select(func.count()).select_from(FbAssignment).where(FbAssignment.project_id == state['project_id'])
            )
            assert assignment_count == 0
            visible = await FeedbackPublicationService.list_participant_options(
                db,
                state['project_id'],
                ParticipantOptionQueryModel(keyword='P5测试用户', pageSize=PARTICIPANT_PAGE_SIZE),
                true(),
                true(),
            )
            assert visible.total >= TEST_USER_COUNT
            assert len(visible.rows) == PARTICIPANT_PAGE_SIZE
            hidden = await FeedbackPublicationService.list_participant_options(
                db,
                state['project_id'],
                ParticipantOptionQueryModel(keyword='P5测试用户'),
                true(),
                false(),
            )
            assert hidden.total == 0

            request = PublishRequestModel(
                projectLockVersion=config.project_lock_version,
                versionId=config.version_id,
                versionLockVersion=config.version_lock_version,
            )
            with pytest.raises(ConflictException) as exc_info:
                await FeedbackPublicationService.publish(
                    db,
                    state['project_id'],
                    request,
                    publisher_user_id,
                    'p5-test',
                    true(),
                    false(),
                )
            assert {item['code'] for item in exc_info.value.data['validationIssues']} == {
                'TARGET_USER_UNAVAILABLE',
                'EVALUATOR_USER_UNAVAILABLE',
            }

            await db.execute(
                update(SysUser).where(SysUser.user_id == target_user_id).values(nick_name='发布时被评价人')
            )
            await db.execute(
                update(SysUser).where(SysUser.user_id == evaluator_user_id).values(nick_name='发布时评价人')
            )
            await db.commit()

            published = await FeedbackPublicationService.publish(
                db,
                state['project_id'],
                request,
                publisher_user_id,
                'p5-test',
                true(),
                true(),
            )
            assert published.already_published is False
            assert published.assignment_count == EXPECTED_ASSIGNMENT_COUNT

        async with session_factory() as db:
            project = await db.get(FbProject, state['project_id'])
            version = await db.get(FbQuestionnaireVersion, state['version_id'])
            assignments = await FeedbackPublicationDao.list_assignments(db, state['project_id'], state['version_id'])
            targets = await FeedbackPublicationDao.list_targets(db, state['project_id'], state['version_id'])
            assert project.status == 'ACTIVE'
            assert version.status == 'FROZEN'
            assert version.scoring_rule_snapshot['relationWeights'][1]['weight'] == '100.0000'
            assert targets[0].target_user_name == '发布时被评价人'
            peer_task = next(item for item in assignments if item.evaluator_user_id == evaluator_user_id)
            assert peer_task.evaluator_user_name == '发布时评价人'
            assert all(item.status == 'PENDING' for item in assignments)
            evaluator_tasks = await FeedbackAssignmentDao.list_evaluator_assignments(db, evaluator_user_id)
            assert [item.assignment_id for item in evaluator_tasks] == [peer_task.assignment_id]

            await db.execute(
                update(SysUser).where(SysUser.user_id == target_user_id).values(nick_name='发布后被评价人')
            )
            await db.execute(
                update(SysUser).where(SysUser.user_id == evaluator_user_id).values(nick_name='发布后评价人')
            )
            await db.commit()

            frozen = await FeedbackPublicationService.get_config(db, state['project_id'], true())
            assert frozen.editable is False
            assert frozen.project_status.value == 'ACTIVE'
            assert frozen.targets[0].nick_name == '发布时被评价人'
            participant_names = {item.user_id: item.nick_name for item in frozen.configured_participants}
            assert participant_names[target_user_id] == '发布时被评价人'
            assert participant_names[evaluator_user_id] == '发布时评价人'
            with pytest.raises(ConflictException) as exc_info:
                await FeedbackPublicationService.save_config(
                    db,
                    state['project_id'],
                    build_config_payload(frozen, target_user_id, evaluator_user_id),
                    'p5-test',
                    true(),
                    true(),
                )
            assert '不能修改' in exc_info.value.message

            repeated = await FeedbackPublicationService.publish(
                db,
                state['project_id'],
                request,
                publisher_user_id,
                'p5-test',
                true(),
                true(),
            )
            assert repeated.already_published is True
            assert repeated.assignment_count == published.assignment_count
    finally:
        if state is not None:
            await cleanup_project(session_factory, state)
        await engine.dispose()


@pytest.mark.asyncio
async def test_p5_publish_rolls_back_all_changes_when_task_materialization_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session_factory = create_test_session_factory()
    state: dict[str, Any] | None = None
    original_add = FeedbackPublicationDao.add_assignments

    async def fail_after_flush(db: AsyncSession, assignments: Any) -> None:
        await original_add(db, assignments)
        raise RuntimeError('注入任务物化失败')

    try:
        state = await create_ready_project(session_factory, uuid.uuid4().hex[:12])
        config = state['config']
        monkeypatch.setattr(FeedbackPublicationDao, 'add_assignments', fail_after_flush)
        async with session_factory() as db:
            with pytest.raises(RuntimeError, match='注入任务物化失败'):
                await FeedbackPublicationService.publish(
                    db,
                    state['project_id'],
                    PublishRequestModel(
                        projectLockVersion=config.project_lock_version,
                        versionId=config.version_id,
                        versionLockVersion=config.version_lock_version,
                    ),
                    state['user_ids'][2],
                    'p5-test',
                    true(),
                    true(),
                )
        async with session_factory() as db:
            project = await db.get(FbProject, state['project_id'])
            version = await db.get(FbQuestionnaireVersion, state['version_id'])
            count = await db.scalar(
                select(func.count()).select_from(FbAssignment).where(FbAssignment.project_id == state['project_id'])
            )
            assert project.status == 'PREPARING'
            assert project.current_questionnaire_version_id is None
            assert version.status == 'DRAFT'
            assert version.scoring_rule_snapshot == {}
            assert count == 0
    finally:
        if state is not None:
            await cleanup_project(session_factory, state)
        await engine.dispose()


@pytest.mark.asyncio
async def test_p5_two_sessions_publish_once_without_duplicate_tasks() -> None:
    engine, session_factory = create_test_session_factory()
    state: dict[str, Any] | None = None
    try:
        state = await create_ready_project(session_factory, uuid.uuid4().hex[:12])
        config = state['config']
        request = PublishRequestModel(
            projectLockVersion=config.project_lock_version,
            versionId=config.version_id,
            versionLockVersion=config.version_lock_version,
        )

        async def publish_once() -> Any:
            async with session_factory() as db:
                return await FeedbackPublicationService.publish(
                    db,
                    state['project_id'],
                    request,
                    state['user_ids'][2],
                    'p5-test',
                    true(),
                    true(),
                )

        results = await asyncio.gather(publish_once(), publish_once())
        assert sorted(item.already_published for item in results) == [False, True]
        async with session_factory() as db:
            count = await db.scalar(
                select(func.count()).select_from(FbAssignment).where(FbAssignment.project_id == state['project_id'])
            )
            assert count == EXPECTED_ASSIGNMENT_COUNT
    finally:
        if state is not None:
            await cleanup_project(session_factory, state)
        await engine.dispose()
