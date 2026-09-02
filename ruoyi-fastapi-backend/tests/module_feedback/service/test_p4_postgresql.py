import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, true

from config.database import create_async_db_engine, create_async_session_factory
from config.env import DataSourceSettings
from module_admin.entity.do.user_do import SysUser
from module_feedback.entity.do import (
    FbIndicator,
    FbIndicatorQuestion,
    FbProject,
    FbQuestion,
    FbQuestionnairePage,
    FbQuestionnaireVersion,
)
from module_feedback.entity.vo import ProjectCreateModel, QuestionnaireDraftSaveModel
from module_feedback.service import FeedbackProjectService, FeedbackQuestionnaireService
from scripts.feedback_p0_database_precheck import build_source_payload

RUN_POSTGRES_TESTS = os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') == '1'
EXPECTED_PAGE_COUNT = 2
EXPECTED_QUESTION_COUNT = 5
EXPECTED_INDICATOR_COUNT = 3
EXPECTED_BINDING_COUNT = 5

pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES_TESTS,
    reason='仅在显式启用隔离PostgreSQL测试时运行',
)


def build_full_save_payload(version_id: int, lock_version: int) -> QuestionnaireDraftSaveModel:
    return QuestionnaireDraftSaveModel(
        versionId=version_id,
        lockVersion=lock_version,
        title='P4完整问卷',
        description='不得信任这个前端摘要',
        descriptionDoc={
            'type': 'doc',
            'content': [
                {'type': 'heading', 'attrs': {'level': 2}, 'content': [{'type': 'text', 'text': '填写说明'}]},
                {'type': 'paragraph', 'content': [{'type': 'text', 'text': '请依据实际表现完成评价。'}]},
            ],
        },
        settings={'showProgress': True},
        pages=[
            {
                'pageCode': 'P_CORE',
                'pageTitle': '核心能力',
                'sortOrder': 1,
                'questions': [
                    {
                        'questionCode': 'Q_SINGLE',
                        'questionType': 'SINGLE_CHOICE',
                        'title': '目标是否清晰',
                        'isRequired': True,
                        'isScored': True,
                        'sortOrder': 1,
                        'options': [
                            {'optionCode': 'O_YES', 'optionLabel': '是', 'score': '5.0000', 'sortOrder': 1},
                            {'optionCode': 'O_NO', 'optionLabel': '否', 'score': '0.0000', 'sortOrder': 2},
                        ],
                    },
                    {
                        'questionCode': 'Q_STAR',
                        'questionType': 'STAR_RATING',
                        'title': '协作表现',
                        'isRequired': True,
                        'isScored': True,
                        'minScore': '0',
                        'maxScore': '4',
                        'decimalPlaces': 0,
                        'config': {},
                        'sortOrder': 2,
                        'options': [],
                    },
                ],
            },
            {
                'pageCode': 'P_MORE',
                'pageTitle': '补充评价',
                'sortOrder': 2,
                'questions': [
                    {
                        'questionCode': 'Q_NUMBER',
                        'questionType': 'NUMERIC_INPUT',
                        'title': '目标完成率',
                        'isScored': True,
                        'minScore': '0',
                        'maxScore': '100',
                        'decimalPlaces': 2,
                        'config': {'defaultValue': '80.25'},
                        'sortOrder': 1,
                        'options': [],
                    },
                    {
                        'questionCode': 'Q_SLIDER',
                        'questionType': 'SLIDER',
                        'title': '综合评分',
                        'isScored': True,
                        'minScore': '0.0',
                        'maxScore': '10.0',
                        'decimalPlaces': 1,
                        'config': {'step': '0.5', 'defaultValue': '5.0'},
                        'sortOrder': 2,
                        'options': [],
                    },
                    {
                        'questionCode': 'Q_TEXT',
                        'questionType': 'TEXT',
                        'title': '改进建议',
                        'isScored': False,
                        'config': {'maxLength': 1200},
                        'sortOrder': 3,
                        'options': [],
                    },
                ],
            },
        ],
        indicators=[
            {
                'indicatorCode': 'I_GOAL',
                'indicatorName': '目标与协作',
                'weight': '60.0000',
                'sortOrder': 1,
                'questionCodes': ['Q_SINGLE', 'Q_STAR'],
            },
            {
                'indicatorCode': 'I_RESULT',
                'indicatorName': '结果表现',
                'weight': '40.0000',
                'sortOrder': 2,
                'questionCodes': ['Q_NUMBER', 'Q_SLIDER'],
            },
            {
                'indicatorCode': 'I_COMMENT',
                'indicatorName': '定性建议',
                'weight': '0.0000',
                'sortOrder': 3,
                'questionCodes': ['Q_TEXT'],
            },
        ],
    )


@pytest.mark.asyncio
async def test_p4_full_questionnaire_round_trip_in_postgresql() -> None:
    source = DataSourceSettings(**build_source_payload('ruoyi_feedback_test'))
    engine = create_async_db_engine(config=source)
    session_factory = create_async_session_factory(engine)
    marker = f'P4闭环-{uuid.uuid4()}'
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
                ProjectCreateModel(projectName=marker, questionnaireTitle='P4初始问卷'),
                owner_user_id=user.user_id,
                owner_dept_id=user.dept_id,
                operator_name='p4-test',
            )
            project_id = created.project_id
            initial = await FeedbackQuestionnaireService.get_draft(db, project_id, true())
            assert initial.pages[0].page_code.startswith('P_')
            assert initial.is_publish_ready is False

            saved = await FeedbackQuestionnaireService.save_draft(
                db,
                project_id,
                build_full_save_payload(initial.version_id, initial.lock_version),
                'p4-test',
                true(),
            )
            assert saved.is_publish_ready is True
            assert saved.validation_issues == []
            assert saved.description == '填写说明\n请依据实际表现完成评价。'
            assert all(page.page_id is not None for page in saved.pages)
            assert all(question.question_id is not None for page in saved.pages for question in page.questions)
            assert all(indicator.indicator_id is not None for indicator in saved.indicators)

        async with session_factory() as db:
            restored = await FeedbackQuestionnaireService.get_draft(db, project_id, true())
            assert restored.is_publish_ready is True
            assert [page.page_code for page in restored.pages] == ['P_CORE', 'P_MORE']
            assert [question.question_type for page in restored.pages for question in page.questions] == [
                'SINGLE_CHOICE',
                'STAR_RATING',
                'NUMERIC_INPUT',
                'SLIDER',
                'TEXT',
            ]
            assert restored.pages[1].questions[0].config.default_value == Decimal('80.25')
            assert restored.pages[1].questions[1].config.step == Decimal('0.5')
            assert restored.indicators[0].question_codes == ['Q_SINGLE', 'Q_STAR']
            assert restored.indicators[2].question_codes == ['Q_TEXT']

            counts = {
                'pages': await db.scalar(
                    select(func.count())
                    .select_from(FbQuestionnairePage)
                    .where(FbQuestionnairePage.version_id == restored.version_id)
                ),
                'questions': await db.scalar(
                    select(func.count()).select_from(FbQuestion).where(FbQuestion.version_id == restored.version_id)
                ),
                'indicators': await db.scalar(
                    select(func.count()).select_from(FbIndicator).where(FbIndicator.version_id == restored.version_id)
                ),
                'bindings': await db.scalar(
                    select(func.count())
                    .select_from(FbIndicatorQuestion)
                    .where(FbIndicatorQuestion.version_id == restored.version_id)
                ),
            }
            assert counts == {
                'pages': EXPECTED_PAGE_COUNT,
                'questions': EXPECTED_QUESTION_COUNT,
                'indicators': EXPECTED_INDICATOR_COUNT,
                'bindings': EXPECTED_BINDING_COUNT,
            }
    finally:
        if project_id is not None:
            async with session_factory() as cleanup_db:
                await cleanup_db.execute(
                    delete(FbQuestionnaireVersion).where(FbQuestionnaireVersion.project_id == project_id)
                )
                await cleanup_db.execute(delete(FbProject).where(FbProject.project_id == project_id))
                await cleanup_db.commit()
        await engine.dispose()
