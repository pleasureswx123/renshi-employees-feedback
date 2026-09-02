from typing import Annotated

from fastapi import Path, Query, Request, Response
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.data_scope import DataScopeDependency
from common.aspect.db_session import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel, PageResponseModel, ResponseBaseModel
from module_admin.entity.do.user_do import SysUser
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_feedback.entity.do import FbProject
from module_feedback.entity.vo import (
    ParticipantOptionModel,
    ParticipantOptionQueryModel,
    ProjectCreateModel,
    ProjectDetailModel,
    ProjectPageQueryModel,
    ProjectSummaryModel,
    ProjectUpdateModel,
    PublicationConfigModel,
    PublicationConfigSaveModel,
    PublishRequestModel,
    PublishResultModel,
    QuestionnaireDraftModel,
    QuestionnaireDraftSaveModel,
)
from module_feedback.service import FeedbackProjectService, FeedbackPublicationService, FeedbackQuestionnaireService
from utils.response_util import ResponseUtil

project_controller = APIRouterPro(
    prefix='/feedback/projects',
    order_num=31,
    tags=['员工反馈-评价项目'],
    dependencies=[PreAuthDependency()],
)


@project_controller.get(
    '',
    summary='获取评价项目分页列表',
    response_model=PageResponseModel[ProjectSummaryModel],
    dependencies=[UserInterfaceAuthDependency('feedback:project:list')],
)
async def list_feedback_projects(
    request: Request,
    query_object: Annotated[ProjectPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    data_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
) -> Response:
    result = await FeedbackProjectService.list_projects(query_db, query_object, data_scope_sql)
    return ResponseUtil.success(model_content=result)


@project_controller.post(
    '',
    summary='创建准备阶段评价项目',
    response_model=DataResponseModel[ProjectDetailModel],
    dependencies=[UserInterfaceAuthDependency('feedback:project:add')],
)
@Log(title='评价项目', business_type=BusinessType.INSERT)
async def create_feedback_project(
    request: Request,
    page_object: ProjectCreateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    result = await FeedbackProjectService.create_project(
        query_db,
        page_object,
        owner_user_id=current_user.user.user_id,
        owner_dept_id=current_user.user.dept_id,
        operator_name=current_user.user.user_name,
    )
    return ResponseUtil.success(msg='项目创建成功', data=result.model_dump(by_alias=True))


@project_controller.get(
    '/{project_id}/questionnaire-draft',
    summary='读取问卷草稿',
    response_model=DataResponseModel[QuestionnaireDraftModel],
    dependencies=[UserInterfaceAuthDependency('feedback:questionnaire:edit')],
)
async def get_feedback_questionnaire_draft(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    data_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
) -> Response:
    result = await FeedbackQuestionnaireService.get_draft(query_db, project_id, data_scope_sql)
    return ResponseUtil.success(data=result.model_dump(by_alias=True))


@project_controller.put(
    '/{project_id}/questionnaire-draft',
    summary='保存问卷草稿',
    response_model=DataResponseModel[QuestionnaireDraftModel],
    dependencies=[UserInterfaceAuthDependency('feedback:questionnaire:edit')],
)
@Log(title='问卷草稿', business_type=BusinessType.UPDATE)
async def save_feedback_questionnaire_draft(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    page_object: QuestionnaireDraftSaveModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
) -> Response:
    result = await FeedbackQuestionnaireService.save_draft(
        query_db,
        project_id,
        page_object,
        current_user.user.user_name,
        data_scope_sql,
    )
    return ResponseUtil.success(msg='问卷草稿已保存', data=result.model_dump(by_alias=True))


@project_controller.get(
    '/{project_id}/participant-options',
    summary='获取项目内候选人员',
    response_model=PageResponseModel[ParticipantOptionModel],
    dependencies=[UserInterfaceAuthDependency('feedback:participant:manage')],
)
async def list_feedback_participant_options(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    query_object: Annotated[ParticipantOptionQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    project_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
    user_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(SysUser, user_alias='user_id', dept_alias='dept_id'),
    ],
) -> Response:
    result = await FeedbackPublicationService.list_participant_options(
        query_db,
        project_id,
        query_object,
        project_scope_sql,
        user_scope_sql,
    )
    return ResponseUtil.success(model_content=result)


@project_controller.get(
    '/{project_id}/publication-config',
    summary='读取发布配置或冻结视图',
    response_model=DataResponseModel[PublicationConfigModel],
    dependencies=[UserInterfaceAuthDependency(['feedback:participant:manage', 'feedback:project:publish'])],
)
async def get_feedback_publication_config(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    project_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
) -> Response:
    result = await FeedbackPublicationService.get_config(query_db, project_id, project_scope_sql)
    return ResponseUtil.success(data=result.model_dump(by_alias=True))


@project_controller.put(
    '/{project_id}/publication-config',
    summary='整体保存发布配置',
    response_model=DataResponseModel[PublicationConfigModel],
    dependencies=[UserInterfaceAuthDependency('feedback:participant:manage')],
)
@Log(title='发布配置', business_type=BusinessType.UPDATE)
async def save_feedback_publication_config(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    page_object: PublicationConfigSaveModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    project_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
    user_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(SysUser, user_alias='user_id', dept_alias='dept_id'),
    ],
) -> Response:
    result = await FeedbackPublicationService.save_config(
        query_db,
        project_id,
        page_object,
        current_user.user.user_name,
        project_scope_sql,
        user_scope_sql,
    )
    return ResponseUtil.success(msg='发布配置已保存', data=result.model_dump(by_alias=True))


@project_controller.post(
    '/{project_id}/publish',
    summary='冻结配置并发布评价项目',
    response_model=DataResponseModel[PublishResultModel],
    dependencies=[UserInterfaceAuthDependency('feedback:project:publish')],
)
@Log(title='评价项目发布', business_type=BusinessType.UPDATE)
async def publish_feedback_project(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    page_object: PublishRequestModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    project_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
    user_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(SysUser, user_alias='user_id', dept_alias='dept_id'),
    ],
) -> Response:
    result = await FeedbackPublicationService.publish(
        query_db,
        project_id,
        page_object,
        current_user.user.user_id,
        current_user.user.user_name,
        project_scope_sql,
        user_scope_sql,
    )
    return ResponseUtil.success(msg='项目发布成功', data=result.model_dump(by_alias=True))


@project_controller.get(
    '/{project_id}',
    summary='获取评价项目详情',
    response_model=DataResponseModel[ProjectDetailModel],
    dependencies=[UserInterfaceAuthDependency('feedback:project:list')],
)
async def get_feedback_project_detail(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    data_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
) -> Response:
    result = await FeedbackProjectService.get_project_detail(query_db, project_id, data_scope_sql)
    return ResponseUtil.success(data=result.model_dump(by_alias=True))


@project_controller.put(
    '/{project_id}',
    summary='编辑准备阶段评价项目',
    response_model=DataResponseModel[ProjectDetailModel],
    dependencies=[UserInterfaceAuthDependency('feedback:project:edit')],
)
@Log(title='评价项目', business_type=BusinessType.UPDATE)
async def update_feedback_project(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    page_object: ProjectUpdateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
) -> Response:
    result = await FeedbackProjectService.update_project(
        query_db,
        project_id,
        page_object,
        current_user.user.user_name,
        data_scope_sql,
    )
    return ResponseUtil.success(msg='项目更新成功', data=result.model_dump(by_alias=True))


@project_controller.delete(
    '/{project_id}',
    summary='删除准备阶段评价项目',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('feedback:project:remove')],
)
@Log(title='评价项目', business_type=BusinessType.DELETE)
async def delete_feedback_project(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    lock_version: Annotated[int, Query(alias='lockVersion', ge=0, description='项目乐观锁版本')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
) -> Response:
    await FeedbackProjectService.delete_project(
        query_db,
        project_id,
        lock_version,
        current_user.user.user_name,
        data_scope_sql,
    )
    return ResponseUtil.success(msg='项目删除成功')
