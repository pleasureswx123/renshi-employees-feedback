import os
import uuid
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import create_async_db_engine, create_async_session_factory
from config.env import DataSourceSettings
from module_admin.entity.do.user_do import SysUser
from module_feedback.dao.answer_dao import FeedbackAnswerDao
from module_feedback.dao.assignment_dao import FeedbackAssignmentDao
from module_feedback.dao.project_dao import FeedbackProjectDao
from module_feedback.entity.do import (
    FbAnswer,
    FbAnswerSheet,
    FbAssignment,
    FbProject,
    FbProjectTarget,
    FbQuestion,
    FbQuestionnairePage,
    FbQuestionnaireVersion,
    FbQuestionOption,
    FbRelation,
)
from scripts.feedback_p0_database_precheck import build_source_payload

RUN_POSTGRES_TESTS = os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') == '1'

pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES_TESTS,
    reason='仅在显式启用隔离PostgreSQL测试时运行',
)


async def assert_integrity_error_in_savepoint(db: AsyncSession, operation: Callable[[], Awaitable[object]]) -> None:
    """断言数据库约束拒绝操作，同时保留外层验收事务。"""
    savepoint = await db.begin_nested()
    try:
        with pytest.raises(IntegrityError):
            await operation()
    finally:
        await savepoint.rollback()


@pytest.mark.asyncio
async def test_async_dao_loads_relationships_and_leaves_transaction_to_service() -> None:  # noqa: PLR0915
    """在隔离测试库证明异步DAO关系加载有效且回滚后不留下业务数据。"""
    source = DataSourceSettings(**build_source_payload('ruoyi_feedback_test'))
    engine = create_async_db_engine(config=source)
    session_factory = create_async_session_factory(engine)
    marker = f'P2-DAO-{uuid.uuid4()}'

    try:
        async with session_factory() as db:
            transaction = await db.begin()
            try:
                user_id = await db.scalar(
                    select(func.min(SysUser.user_id)).where(SysUser.del_flag == '0', SysUser.status == '0')
                )
                assert user_id is not None

                project = await FeedbackProjectDao.add_project(
                    db,
                    FbProject(project_name=marker, owner_user_id=user_id, create_by='p2-test', update_by='p2-test'),
                )
                version = await FeedbackProjectDao.add_questionnaire_version(
                    db,
                    FbQuestionnaireVersion(
                        project_id=project.project_id,
                        version_no=1,
                        title='P2异步DAO验证问卷',
                        create_by='p2-test',
                        update_by='p2-test',
                    ),
                )
                page = FbQuestionnairePage(
                    version_id=version.version_id,
                    page_code='P1',
                    page_title='第一页',
                    sort_order=1,
                    create_by='p2-test',
                    update_by='p2-test',
                )
                db.add(page)
                await db.flush()
                question = FbQuestion(
                    version_id=version.version_id,
                    page_id=page.page_id,
                    question_code='Q1',
                    question_type='SINGLE_CHOICE',
                    title='P2约束验证题',
                    sort_order=1,
                    create_by='p2-test',
                    update_by='p2-test',
                )
                db.add(question)
                await db.flush()
                option = FbQuestionOption(
                    question_id=question.question_id,
                    option_code='A',
                    option_label='选项A',
                    score=1,
                    sort_order=1,
                    create_by='p2-test',
                    update_by='p2-test',
                )
                relation = FbRelation(
                    project_id=project.project_id,
                    version_id=version.version_id,
                    relation_code='SELF',
                    relation_type='SELF',
                    relation_name='自评',
                    weight=0,
                    sort_order=1,
                    create_by='p2-test',
                    update_by='p2-test',
                )
                target = FbProjectTarget(
                    project_id=project.project_id,
                    version_id=version.version_id,
                    target_user_id=user_id,
                    target_user_name='P2测试用户',
                    only_self_evaluation=True,
                    create_by='p2-test',
                    update_by='p2-test',
                )
                db.add_all([option, relation, target])
                await db.flush()
                assignment = (
                    await FeedbackAssignmentDao.add_assignments(
                        db,
                        [
                            FbAssignment(
                                project_id=project.project_id,
                                version_id=version.version_id,
                                evaluator_user_id=user_id,
                                evaluator_user_name='P2测试用户',
                                target_id=target.target_id,
                                target_user_id=user_id,
                                relation_id=relation.relation_id,
                            )
                        ],
                    )
                )[0]
                answer_sheet = await FeedbackAnswerDao.add_answer_sheet(
                    db,
                    FbAnswerSheet(
                        assignment_id=assignment.assignment_id,
                        project_id=project.project_id,
                        version_id=version.version_id,
                    ),
                )
                db.add(
                    FbAnswer(
                        sheet_id=answer_sheet.sheet_id,
                        version_id=version.version_id,
                        question_id=question.question_id,
                        answer_type='OPTION',
                        option_id=option.option_id,
                        raw_score=1,
                    )
                )
                await db.flush()

                async def add_duplicate_assignment() -> object:
                    db.add(
                        FbAssignment(
                            project_id=project.project_id,
                            version_id=version.version_id,
                            evaluator_user_id=user_id,
                            evaluator_user_name='重复任务',
                            target_id=target.target_id,
                            target_user_id=user_id,
                            relation_id=relation.relation_id,
                        )
                    )
                    await db.flush()
                    return None

                await assert_integrity_error_in_savepoint(db, add_duplicate_assignment)

                async def add_duplicate_answer() -> object:
                    db.add(
                        FbAnswer(
                            sheet_id=answer_sheet.sheet_id,
                            version_id=version.version_id,
                            question_id=question.question_id,
                            answer_type='OPTION',
                            option_id=option.option_id,
                            raw_score=1,
                        )
                    )
                    await db.flush()
                    return None

                await assert_integrity_error_in_savepoint(db, add_duplicate_answer)

                async def write_invalid_status() -> object:
                    return await db.execute(
                        update(FbAssignment)
                        .where(FbAssignment.assignment_id == assignment.assignment_id)
                        .values(status='BROKEN')
                    )

                await assert_integrity_error_in_savepoint(db, write_invalid_status)

                db.expunge_all()
                loaded_project = await FeedbackProjectDao.get_project_by_id(db, project.project_id)
                assert loaded_project is not None
                assert [item.version_no for item in loaded_project.questionnaire_versions] == [1]
                assert [item.page_title for item in loaded_project.questionnaire_versions[0].pages] == ['第一页']
                assert [item.target_user_name for item in loaded_project.targets] == ['P2测试用户']

                assignments = await FeedbackAssignmentDao.list_evaluator_assignments(db, user_id)
                matching = [item for item in assignments if item.project_id == project.project_id]
                assert len(matching) == 1
                assert matching[0].relation.relation_type == 'SELF'
                assert matching[0].target_snapshot.target_user_name == 'P2测试用户'
            finally:
                await transaction.rollback()

        async with session_factory() as db:
            remaining = await db.scalar(
                select(func.count()).select_from(FbProject).where(FbProject.project_name == marker)
            )
            assert remaining == 0
    finally:
        await engine.dispose()
