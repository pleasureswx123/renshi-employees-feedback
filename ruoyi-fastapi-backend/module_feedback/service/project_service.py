import math
import uuid
from datetime import datetime

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import PageModel
from exceptions.exception import ServiceException
from module_feedback.constants import DEFAULT_RELATION_DEFINITIONS
from module_feedback.dao import FeedbackProjectDao, FeedbackQuestionnaireDao
from module_feedback.entity.do import FbProject, FbQuestionnairePage, FbQuestionnaireVersion, FbRelation
from module_feedback.entity.vo import (
    ProjectCreateModel,
    ProjectDetailModel,
    ProjectPageQueryModel,
    ProjectSummaryModel,
    ProjectUpdateModel,
)
from module_feedback.enums import ProjectStatus, QuestionnaireVersionStatus
from module_feedback.service.questionnaire_service import FeedbackQuestionnaireService
from module_feedback.service.system_templates import build_template


class FeedbackProjectService:
    """准备阶段评价项目应用服务。"""

    @staticmethod
    def _draft_version_id(project: FbProject) -> int | None:
        return next(
            (
                item.version_id
                for item in project.questionnaire_versions
                if item.status == QuestionnaireVersionStatus.DRAFT.value
            ),
            None,
        )

    @staticmethod
    def _stable_code(prefix: str) -> str:
        return f'{prefix}_{uuid.uuid4().hex}'

    @staticmethod
    def _build_default_relations(project_id: int, version_id: int, operator_name: str) -> list[FbRelation]:
        """为新草稿构造没有组织权重假设的固定评价关系。"""
        return [
            FbRelation(
                project_id=project_id,
                version_id=version_id,
                relation_code=item.code,
                relation_type=item.relation_type.value,
                relation_name=item.name,
                is_enabled=item.is_enabled,
                participates_in_score=item.participates_in_score,
                weight=item.weight,
                sort_order=item.sort_order,
                create_by=operator_name,
                update_by=operator_name,
            )
            for item in DEFAULT_RELATION_DEFINITIONS
        ]

    @classmethod
    def _to_summary(cls, project: FbProject) -> ProjectSummaryModel:
        return ProjectSummaryModel(
            projectId=project.project_id,
            projectName=project.project_name,
            description=project.description,
            status=project.status,
            ownerUserId=project.owner_user_id,
            ownerDeptId=project.owner_dept_id,
            draftVersionId=cls._draft_version_id(project),
            lockVersion=project.lock_version,
            createBy=project.create_by,
            createTime=project.create_time,
            updateBy=project.update_by,
            updateTime=project.update_time,
        )

    @classmethod
    def _to_detail(cls, project: FbProject) -> ProjectDetailModel:
        summary = cls._to_summary(project)
        return ProjectDetailModel(
            **summary.model_dump(),
            currentQuestionnaireVersionId=project.current_questionnaire_version_id,
            publishedBy=project.published_by,
            publishedTime=project.published_time,
            completedBy=project.completed_by,
            completedTime=project.completed_time,
            completionReason=project.completion_reason,
        )

    @staticmethod
    def _ensure_preparing(project: FbProject) -> None:
        if project.status != ProjectStatus.PREPARING.value:
            raise ServiceException(message='只有准备阶段项目允许编辑或删除')

    @staticmethod
    async def _get_locked_project(
        query_db: AsyncSession,
        project_id: int,
        data_scope_sql: ColumnElement,
    ) -> FbProject:
        project = await FeedbackProjectDao.get_project_for_update_scoped(query_db, project_id, data_scope_sql)
        if project is None:
            raise ServiceException(message='项目不存在或不在当前数据范围内')
        return project

    @classmethod
    async def list_projects(
        cls,
        query_db: AsyncSession,
        query_object: ProjectPageQueryModel,
        data_scope_sql: ColumnElement,
    ) -> PageModel[ProjectSummaryModel]:
        projects, total = await FeedbackProjectDao.list_projects(query_db, query_object, data_scope_sql)
        return PageModel[ProjectSummaryModel](
            rows=[cls._to_summary(item) for item in projects],
            pageNum=query_object.page_num,
            pageSize=query_object.page_size,
            total=total,
            hasNext=math.ceil(total / query_object.page_size) > query_object.page_num,
        )

    @classmethod
    async def create_project(
        cls,
        query_db: AsyncSession,
        page_object: ProjectCreateModel,
        owner_user_id: int,
        owner_dept_id: int | None,
        operator_name: str,
    ) -> ProjectDetailModel:
        """在同一事务中创建项目、空白或模板草稿和固定评价关系。"""
        try:
            template = (
                build_template(page_object.template_key, 0, page_object.questionnaire_title or page_object.project_name)
                if page_object.template_key
                else None
            )
            project = await FeedbackProjectDao.add_project(
                query_db,
                FbProject(
                    project_name=page_object.project_name,
                    description=page_object.description,
                    owner_user_id=owner_user_id,
                    owner_dept_id=owner_dept_id,
                    create_by=operator_name,
                    update_by=operator_name,
                ),
            )
            version = await FeedbackProjectDao.add_questionnaire_version(
                query_db,
                FbQuestionnaireVersion(
                    project_id=project.project_id,
                    version_no=1,
                    title=page_object.questionnaire_title or page_object.project_name,
                    description=page_object.questionnaire_description,
                    create_by=operator_name,
                    update_by=operator_name,
                ),
            )
            query_db.add_all(cls._build_default_relations(project.project_id, version.version_id, operator_name))
            if template:
                template.version_id = version.version_id
                version.settings = {'systemTemplateKey': page_object.template_key}
                version.description = page_object.questionnaire_description or template.description
                pages = FeedbackQuestionnaireService._build_pages(template, operator_name)
                indicators, bindings = FeedbackQuestionnaireService._build_indicators(template, operator_name)
                await FeedbackQuestionnaireDao.replace_draft_document(
                    query_db, version.version_id, pages, indicators, bindings
                )
            else:
                query_db.add_all(
                    [
                        FbQuestionnairePage(
                            version_id=version.version_id,
                            page_code=cls._stable_code('P'),
                            page_title='第1页',
                            sort_order=1,
                            create_by=operator_name,
                            update_by=operator_name,
                        )
                    ]
                )
            await query_db.commit()
            loaded = await FeedbackProjectDao.get_project_by_id_scoped(query_db, project.project_id, True)
            if loaded is None:
                raise ServiceException(message='项目创建后读取失败')
            return cls._to_detail(loaded)
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def get_project_detail(
        cls,
        query_db: AsyncSession,
        project_id: int,
        data_scope_sql: ColumnElement,
    ) -> ProjectDetailModel:
        project = await FeedbackProjectDao.get_project_by_id_scoped(query_db, project_id, data_scope_sql)
        if project is None:
            raise ServiceException(message='项目不存在或不在当前数据范围内')
        return cls._to_detail(project)

    @classmethod
    async def update_project(
        cls,
        query_db: AsyncSession,
        project_id: int,
        page_object: ProjectUpdateModel,
        operator_name: str,
        data_scope_sql: ColumnElement,
    ) -> ProjectDetailModel:
        try:
            project = await cls._get_locked_project(query_db, project_id, data_scope_sql)
            cls._ensure_preparing(project)
            if project.lock_version != page_object.lock_version:
                raise ServiceException(message='项目已被其他用户修改，请刷新后重试')
            project.project_name = page_object.project_name
            project.description = page_object.description
            project.update_by = operator_name
            project.update_time = datetime.now()
            project.lock_version += 1
            await query_db.commit()
            loaded = await FeedbackProjectDao.get_project_by_id_scoped(query_db, project_id, data_scope_sql)
            if loaded is None:
                raise ServiceException(message='项目更新后读取失败')
            return cls._to_detail(loaded)
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def delete_project(
        cls,
        query_db: AsyncSession,
        project_id: int,
        lock_version: int,
        operator_name: str,
        data_scope_sql: ColumnElement,
    ) -> None:
        try:
            project = await cls._get_locked_project(query_db, project_id, data_scope_sql)
            cls._ensure_preparing(project)
            if project.lock_version != lock_version:
                raise ServiceException(message='项目已被其他用户修改，请刷新后重试')
            project.del_flag = '2'
            project.update_by = operator_name
            project.update_time = datetime.now()
            project.lock_version += 1
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            raise
