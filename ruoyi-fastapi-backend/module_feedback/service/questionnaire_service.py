import uuid
from datetime import datetime

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.exception import ServiceException
from module_feedback.dao import FeedbackProjectDao, FeedbackQuestionnaireDao
from module_feedback.entity.do import (
    FbProject,
    FbQuestion,
    FbQuestionnairePage,
    FbQuestionnaireVersion,
    FbQuestionOption,
)
from module_feedback.entity.vo import (
    QuestionDraftModel,
    QuestionnaireDraftModel,
    QuestionnaireDraftSaveModel,
)
from module_feedback.enums import ProjectStatus, QuestionnaireVersionStatus


class FeedbackQuestionnaireService:
    """问卷草稿读取与原子保存服务。"""

    @staticmethod
    def _stable_code(prefix: str) -> str:
        return f'{prefix}_{uuid.uuid4().hex}'

    @classmethod
    def _to_model(
        cls,
        project: FbProject,
        version: FbQuestionnaireVersion,
    ) -> QuestionnaireDraftModel:
        return QuestionnaireDraftModel(
            projectId=project.project_id,
            projectName=project.project_name,
            projectStatus=project.status,
            versionId=version.version_id,
            versionNo=version.version_no,
            versionStatus=version.status,
            lockVersion=version.lock_version,
            title=version.title,
            description=version.description,
            settings=version.settings or {},
            pages=[
                {
                    'pageId': page.page_id,
                    'pageTitle': page.page_title,
                    'pageDescription': page.page_description,
                    'sortOrder': page.sort_order,
                    'questions': [
                        {
                            'questionId': question.question_id,
                            'questionCode': question.question_code,
                            'questionType': question.question_type,
                            'title': question.title,
                            'description': question.description,
                            'isRequired': question.is_required,
                            'isScored': question.is_scored,
                            'sortOrder': question.sort_order,
                            'options': [
                                {
                                    'optionId': option.option_id,
                                    'optionCode': option.option_code,
                                    'optionLabel': option.option_label,
                                    'score': option.score,
                                    'requiresReason': option.requires_reason,
                                    'sortOrder': option.sort_order,
                                }
                                for option in question.options
                            ],
                        }
                        for question in page.questions
                    ],
                }
                for page in version.pages
            ],
        )

    @classmethod
    def _build_question(
        cls,
        question: QuestionDraftModel,
        version_id: int,
        operator_name: str,
    ) -> FbQuestion:
        return FbQuestion(
            version_id=version_id,
            question_code=question.question_code or cls._stable_code('Q'),
            question_type='SINGLE_CHOICE',
            title=question.title,
            description=question.description,
            is_required=question.is_required,
            is_scored=question.is_scored,
            sort_order=question.sort_order,
            config={},
            create_by=operator_name,
            update_by=operator_name,
            options=[
                FbQuestionOption(
                    option_code=option.option_code or cls._stable_code('O'),
                    option_label=option.option_label,
                    score=option.score,
                    requires_reason=option.requires_reason,
                    sort_order=option.sort_order,
                    create_by=operator_name,
                    update_by=operator_name,
                )
                for option in question.options
            ],
        )

    @classmethod
    def _build_pages(
        cls,
        page_object: QuestionnaireDraftSaveModel,
        operator_name: str,
    ) -> list[FbQuestionnairePage]:
        return [
            FbQuestionnairePage(
                version_id=page_object.version_id,
                page_title=page.page_title,
                page_description=page.page_description,
                sort_order=page.sort_order,
                create_by=operator_name,
                update_by=operator_name,
                questions=[
                    cls._build_question(question, page_object.version_id, operator_name) for question in page.questions
                ],
            )
            for page in page_object.pages
        ]

    @classmethod
    async def get_draft(
        cls,
        query_db: AsyncSession,
        project_id: int,
        data_scope_sql: ColumnElement,
    ) -> QuestionnaireDraftModel:
        result = await FeedbackQuestionnaireDao.get_draft_by_project_id(query_db, project_id, data_scope_sql)
        if result is None:
            raise ServiceException(message='项目草稿不存在或不在当前数据范围内')
        project, version = result
        if project.status != ProjectStatus.PREPARING.value:
            raise ServiceException(message='只有准备阶段项目允许读取可编辑问卷草稿')
        return cls._to_model(project, version)

    @classmethod
    async def save_draft(
        cls,
        query_db: AsyncSession,
        project_id: int,
        page_object: QuestionnaireDraftSaveModel,
        operator_name: str,
        data_scope_sql: ColumnElement,
    ) -> QuestionnaireDraftModel:
        try:
            project = await FeedbackProjectDao.get_project_for_update_scoped(query_db, project_id, data_scope_sql)
            if project is None:
                raise ServiceException(message='项目不存在或不在当前数据范围内')
            if project.status != ProjectStatus.PREPARING.value:
                raise ServiceException(message='只有准备阶段项目允许保存问卷草稿')

            version = await FeedbackQuestionnaireDao.get_draft_for_update(
                query_db,
                project_id,
                page_object.version_id,
            )
            if version is None or version.status != QuestionnaireVersionStatus.DRAFT.value:
                raise ServiceException(message='问卷草稿版本不存在或已经冻结')
            if version.lock_version != page_object.lock_version:
                raise ServiceException(message='问卷草稿已被其他用户修改，请刷新后重试')

            version.title = page_object.title
            version.description = page_object.description
            version.settings = page_object.settings
            version.update_by = operator_name
            version.update_time = datetime.now()
            version.lock_version += 1
            project.update_by = operator_name
            project.update_time = datetime.now()
            project.lock_version += 1

            pages = cls._build_pages(page_object, operator_name)
            await FeedbackQuestionnaireDao.replace_draft_pages(query_db, version.version_id, pages)
            await query_db.commit()

            saved = await FeedbackQuestionnaireDao.get_draft_by_project_id(query_db, project_id, data_scope_sql)
            if saved is None:
                raise ServiceException(message='问卷草稿保存后读取失败')
            return cls._to_model(*saved)
        except Exception:
            await query_db.rollback()
            raise
