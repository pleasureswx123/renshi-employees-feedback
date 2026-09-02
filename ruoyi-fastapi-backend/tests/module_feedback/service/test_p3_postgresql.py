import os
import uuid
from datetime import datetime

import pytest
from sqlalchemy import delete, func, select, true

from config.database import create_async_db_engine, create_async_session_factory
from config.env import DataSourceSettings
from exceptions.exception import ServiceException
from module_admin.entity.do.user_do import SysUser
from module_feedback.entity.do import FbProject, FbQuestionnairePage, FbQuestionnaireVersion
from module_feedback.entity.vo import (
    ProjectCreateModel,
    ProjectPageQueryModel,
    ProjectUpdateModel,
    QuestionnaireDraftSaveModel,
)
from module_feedback.service import FeedbackProjectService, FeedbackQuestionnaireService
from scripts.feedback_p0_database_precheck import build_source_payload

RUN_POSTGRES_TESTS = os.getenv('RUN_FEEDBACK_POSTGRES_TESTS') == '1'
OPTION_COUNT = 3

pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES_TESTS,
    reason='仅在显式启用隔离PostgreSQL测试时运行',
)


@pytest.mark.asyncio
async def test_p3_project_and_single_choice_draft_round_trip_in_postgresql() -> None:  # noqa: PLR0915
    source = DataSourceSettings(**build_source_payload('ruoyi_feedback_test'))
    engine = create_async_db_engine(config=source)
    session_factory = create_async_session_factory(engine)
    marker = f'P3闭环-{uuid.uuid4()}'
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
                ProjectCreateModel(
                    projectName=marker,
                    description='P3真实PostgreSQL项目',
                    questionnaireTitle='P3真实问卷',
                ),
                owner_user_id=user.user_id,
                owner_dept_id=user.dept_id,
                operator_name='p3-test',
            )
            project_id = created.project_id
            assert created.status.value == 'PREPARING'
            assert created.draft_version_id is not None

            page_count = await db.scalar(
                select(func.count())
                .select_from(FbQuestionnairePage)
                .join(FbQuestionnaireVersion)
                .where(FbQuestionnaireVersion.project_id == project_id)
            )
            assert page_count == 1

            listed = await FeedbackProjectService.list_projects(
                db,
                ProjectPageQueryModel(projectName=marker, pageNum=1, pageSize=10),
                true(),
            )
            assert listed.total == 1
            assert listed.rows[0].project_id == project_id

            updated = await FeedbackProjectService.update_project(
                db,
                project_id,
                ProjectUpdateModel(
                    projectName=f'{marker}-已编辑',
                    description='准备阶段可编辑',
                    lockVersion=created.lock_version,
                ),
                'p3-test',
                true(),
            )
            assert updated.project_name.endswith('-已编辑')

            draft = await FeedbackQuestionnaireService.get_draft(db, project_id, true())
            saved = await FeedbackQuestionnaireService.save_draft(
                db,
                project_id,
                QuestionnaireDraftSaveModel(
                    versionId=draft.version_id,
                    lockVersion=draft.lock_version,
                    title='领导力反馈问卷',
                    description='保存后重新进入应完整恢复',
                    settings={'showProgress': True},
                    pages=[
                        {
                            'pageCode': 'P_CORE',
                            'pageTitle': '核心能力',
                            'sortOrder': 1,
                            'questions': [
                                {
                                    'questionCode': 'Q_GOAL',
                                    'questionType': 'SINGLE_CHOICE',
                                    'title': '能够清晰说明工作目标',
                                    'description': '请选择最符合实际情况的选项',
                                    'isRequired': True,
                                    'sortOrder': 1,
                                    'options': [
                                        {
                                            'optionCode': 'O_ALWAYS',
                                            'optionLabel': '始终如此',
                                            'score': '5.0000',
                                            'requiresReason': True,
                                            'sortOrder': 1,
                                        },
                                        {
                                            'optionCode': 'O_OFTEN',
                                            'optionLabel': '经常如此',
                                            'score': '4.0000',
                                            'sortOrder': 2,
                                        },
                                        {
                                            'optionCode': 'O_SOMETIMES',
                                            'optionLabel': '有时如此',
                                            'score': '3.0000',
                                            'sortOrder': 3,
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                ),
                'p3-test',
                true(),
            )
            assert saved.lock_version == draft.lock_version + 1
            assert saved.pages[0].questions[0].question_code.startswith('Q_')
            assert len(saved.pages[0].questions[0].options) == OPTION_COUNT
            assert saved.pages[0].questions[0].options[0].requires_reason is True

        async with session_factory() as db:
            restored = await FeedbackQuestionnaireService.get_draft(db, project_id, true())
            assert restored.title == '领导力反馈问卷'
            assert restored.settings == {'showProgress': True}
            assert restored.pages[0].page_title == '核心能力'
            assert restored.pages[0].questions[0].title == '能够清晰说明工作目标'
            assert [item.option_label for item in restored.pages[0].questions[0].options] == [
                '始终如此',
                '经常如此',
                '有时如此',
            ]

            with pytest.raises(ServiceException) as scope_error:
                await FeedbackProjectService.get_project_detail(db, project_id, False)
            assert '数据范围' in scope_error.value.message

            project = await db.get(FbProject, project_id)
            assert project is not None
            project.status = 'ACTIVE'
            project.current_questionnaire_version_id = restored.version_id
            project.published_by = user.user_id
            project.published_time = datetime.now()
            await db.commit()

            with pytest.raises(ServiceException) as state_error:
                await FeedbackProjectService.update_project(
                    db,
                    project_id,
                    ProjectUpdateModel(
                        projectName='进行阶段禁止编辑',
                        description=None,
                        lockVersion=project.lock_version,
                    ),
                    'p3-test',
                    true(),
                )
            assert '只有准备阶段' in state_error.value.message
            with pytest.raises(ServiceException) as draft_state_error:
                await FeedbackQuestionnaireService.get_draft(db, project_id, true())
            assert '只有准备阶段' in draft_state_error.value.message

            project = await db.get(FbProject, project_id)
            assert project is not None
            project.status = 'PREPARING'
            project.current_questionnaire_version_id = None
            project.published_by = None
            project.published_time = None
            await db.commit()

            with pytest.raises(ServiceException) as stale_error:
                await FeedbackProjectService.update_project(
                    db,
                    project_id,
                    ProjectUpdateModel(
                        projectName='过期写入',
                        description=None,
                        lockVersion=0,
                    ),
                    'p3-test',
                    true(),
                )
            assert '刷新后重试' in stale_error.value.message

            latest = await FeedbackProjectService.get_project_detail(db, project_id, true())
            await FeedbackProjectService.delete_project(
                db,
                project_id,
                latest.lock_version,
                'p3-test',
                true(),
            )
            with pytest.raises(ServiceException) as deleted_error:
                await FeedbackProjectService.get_project_detail(db, project_id, true())
            assert '项目不存在' in deleted_error.value.message
    finally:
        if project_id is not None:
            async with session_factory() as cleanup_db:
                await cleanup_db.execute(
                    delete(FbQuestionnaireVersion).where(FbQuestionnaireVersion.project_id == project_id)
                )
                await cleanup_db.execute(delete(FbProject).where(FbProject.project_id == project_id))
                await cleanup_db.commit()
        await engine.dispose()
