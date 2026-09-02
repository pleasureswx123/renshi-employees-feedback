import os
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from config.database import create_async_db_engine, create_async_session_factory
from config.env import DataSourceSettings
from module_admin.entity.do.user_do import SysUser
from module_feedback.constants import DEFAULT_RELATION_DEFINITIONS, SELF_RELATION_CODE
from module_feedback.entity.do import (
    FbAssignment,
    FbEvaluatorSelection,
    FbProject,
    FbProjectTarget,
    FbQuestionnaireVersion,
    FbRelation,
)
from module_feedback.entity.vo import ProjectCreateModel
from module_feedback.service import FeedbackProjectService
from scripts.feedback_p0_database_precheck import build_source_payload

RUN_POSTGRES_TESTS = os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') == '1'

pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES_TESTS,
    reason='仅在显式启用隔离PostgreSQL测试时运行',
)


@pytest.mark.asyncio
async def test_p5_project_defaults_and_evaluator_selection_persist_without_creating_tasks() -> None:
    source = DataSourceSettings(**build_source_payload('ruoyi_feedback_test'))
    engine = create_async_db_engine(config=source)
    session_factory = create_async_session_factory(engine)
    marker = f'P5发布配置基线-{uuid.uuid4()}'
    project_id: int | None = None

    try:
        async with session_factory() as db:
            user = (
                (
                    await db.execute(
                        select(SysUser).where(SysUser.del_flag == '0', SysUser.status == '0').order_by(SysUser.user_id)
                    )
                )
                .scalars()
                .first()
            )
            assert user is not None

            created = await FeedbackProjectService.create_project(
                db,
                ProjectCreateModel(projectName=marker, questionnaireTitle='P5发布配置基线问卷'),
                owner_user_id=user.user_id,
                owner_dept_id=user.dept_id,
                operator_name='p5-test',
            )
            project_id = created.project_id
            version_id = created.draft_version_id
            assert version_id is not None

            relations = list(
                (
                    await db.execute(
                        select(FbRelation)
                        .where(FbRelation.project_id == project_id, FbRelation.version_id == version_id)
                        .order_by(FbRelation.sort_order)
                    )
                )
                .scalars()
                .all()
            )
            assert [item.relation_code for item in relations] == [item.code for item in DEFAULT_RELATION_DEFINITIONS]
            assert all(item.weight == 0 for item in relations)
            self_relation = next(item for item in relations if item.relation_code == SELF_RELATION_CODE)
            assert self_relation.is_enabled is True
            assert self_relation.participates_in_score is False

            target = FbProjectTarget(
                project_id=project_id,
                version_id=version_id,
                target_user_id=user.user_id,
                target_user_name=user.nick_name,
                only_self_evaluation=True,
                create_by='p5-test',
                update_by='p5-test',
            )
            db.add(target)
            await db.flush()
            selection = FbEvaluatorSelection(
                project_id=project_id,
                version_id=version_id,
                target_id=target.target_id,
                target_user_id=user.user_id,
                relation_id=self_relation.relation_id,
                evaluator_user_id=user.user_id,
                create_by='p5-test',
                update_by='p5-test',
            )
            db.add(selection)
            await db.commit()

            persisted = await db.scalar(
                select(FbEvaluatorSelection).where(FbEvaluatorSelection.selection_id == selection.selection_id)
            )
            assert persisted is not None
            assert persisted.target_id == target.target_id
            task_count = await db.scalar(
                select(func.count()).select_from(FbAssignment).where(FbAssignment.project_id == project_id)
            )
            assert task_count == 0

            db.add(
                FbEvaluatorSelection(
                    project_id=project_id,
                    version_id=version_id,
                    target_id=target.target_id,
                    target_user_id=user.user_id,
                    relation_id=self_relation.relation_id,
                    evaluator_user_id=user.user_id,
                    create_by='p5-test',
                    update_by='p5-test',
                )
            )
            with pytest.raises(IntegrityError):
                await db.flush()
            await db.rollback()
    finally:
        if project_id is not None:
            async with session_factory() as cleanup_db:
                await cleanup_db.execute(
                    delete(FbEvaluatorSelection).where(FbEvaluatorSelection.project_id == project_id)
                )
                await cleanup_db.execute(delete(FbProjectTarget).where(FbProjectTarget.project_id == project_id))
                await cleanup_db.execute(
                    delete(FbQuestionnaireVersion).where(FbQuestionnaireVersion.project_id == project_id)
                )
                await cleanup_db.execute(delete(FbProject).where(FbProject.project_id == project_id))
                await cleanup_db.commit()
        await engine.dispose()
