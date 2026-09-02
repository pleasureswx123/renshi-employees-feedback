import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.exception import ServiceException
from module_feedback.dao import FeedbackProjectDao, FeedbackQuestionnaireDao
from module_feedback.entity.do import (
    FbIndicator,
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
    ValidationIssueModel,
    question_config_to_json,
)
from module_feedback.enums import ProjectStatus, QuestionnaireVersionStatus
from module_feedback.validators import get_publish_validation_issues


class FeedbackQuestionnaireService:
    """问卷草稿读取与原子保存服务。"""

    @staticmethod
    def _stable_code(prefix: str) -> str:
        return f'{prefix}_{uuid.uuid4().hex}'

    @classmethod
    def _document_payload(cls, version: FbQuestionnaireVersion) -> dict[str, Any]:
        question_code_by_id = {
            question.question_id: question.question_code for page in version.pages for question in page.questions
        }
        question_order = {
            question.question_code: (page.sort_order, question.sort_order)
            for page in version.pages
            for question in page.questions
        }
        return {
            'versionId': version.version_id,
            'lockVersion': version.lock_version,
            'title': version.title,
            'description': version.description,
            'descriptionDoc': version.description_doc,
            'settings': version.settings or {},
            'pages': [
                {
                    'pageId': page.page_id,
                    'pageCode': page.page_code,
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
                            'minScore': question.min_score,
                            'maxScore': question.max_score,
                            'decimalPlaces': question.decimal_places,
                            'config': question.config or {},
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
            'indicators': [
                {
                    'indicatorId': indicator.indicator_id,
                    'indicatorCode': indicator.indicator_code,
                    'indicatorName': indicator.indicator_name,
                    'description': indicator.description,
                    'weight': indicator.weight,
                    'sortOrder': indicator.sort_order,
                    'questionCodes': sorted(
                        (
                            question_code_by_id[binding.question_id]
                            for binding in indicator.question_bindings
                            if binding.question_id in question_code_by_id
                        ),
                        key=lambda code: question_order[code],
                    ),
                }
                for indicator in version.indicators
            ],
        }

    @classmethod
    def _to_model(
        cls,
        project: FbProject,
        version: FbQuestionnaireVersion,
    ) -> QuestionnaireDraftModel:
        document = QuestionnaireDraftSaveModel.model_validate(cls._document_payload(version))
        issue_payloads = get_publish_validation_issues(document)
        return QuestionnaireDraftModel(
            **document.model_dump(),
            projectId=project.project_id,
            projectName=project.project_name,
            projectStatus=project.status,
            versionNo=version.version_no,
            versionStatus=version.status,
            isPublishReady=not issue_payloads,
            validationIssues=[ValidationIssueModel.model_validate(item) for item in issue_payloads],
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
            question_code=question.question_code,
            question_type=question.question_type,
            title=question.title,
            description=question.description,
            is_required=question.is_required,
            is_scored=question.is_scored,
            min_score=question.min_score,
            max_score=question.max_score,
            decimal_places=question.decimal_places,
            sort_order=question.sort_order,
            config=question_config_to_json(question),
            create_by=operator_name,
            update_by=operator_name,
            options=[
                FbQuestionOption(
                    option_code=option.option_code,
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
                page_code=page.page_code,
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

    @staticmethod
    def _build_indicators(
        page_object: QuestionnaireDraftSaveModel,
        operator_name: str,
    ) -> tuple[list[FbIndicator], dict[str, list[str]]]:
        indicators = [
            FbIndicator(
                version_id=page_object.version_id,
                indicator_code=indicator.indicator_code,
                indicator_name=indicator.indicator_name,
                description=indicator.description,
                weight=indicator.weight,
                sort_order=indicator.sort_order,
                create_by=operator_name,
                update_by=operator_name,
            )
            for indicator in page_object.indicators
        ]
        bindings = {indicator.indicator_code: list(indicator.question_codes) for indicator in page_object.indicators}
        return indicators, bindings

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
            version.description_doc = page_object.description_doc
            version.settings = page_object.settings
            version.update_by = operator_name
            version.update_time = datetime.now()
            version.lock_version += 1
            project.update_by = operator_name
            project.update_time = datetime.now()
            project.lock_version += 1

            pages = cls._build_pages(page_object, operator_name)
            indicators, bindings = cls._build_indicators(page_object, operator_name)
            await FeedbackQuestionnaireDao.replace_draft_document(
                query_db,
                version.version_id,
                pages,
                indicators,
                bindings,
            )
            await query_db.commit()

            saved = await FeedbackQuestionnaireDao.get_draft_by_project_id(query_db, project_id, data_scope_sql)
            if saved is None:
                raise ServiceException(message='问卷草稿保存后读取失败')
            return cls._to_model(*saved)
        except Exception:
            await query_db.rollback()
            raise
