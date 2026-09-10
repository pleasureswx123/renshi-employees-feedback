from typing import Annotated

from fastapi import HTTPException, Path, Query, Request, Response, status
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
from middlewares.trace_middleware.ctx import TraceCtx
from module_admin.entity.do.user_do import SysUser
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_feedback.entity.do import FbProject, FbProjectTarget
from module_feedback.entity.vo import (
    CompletionPrecheckModel,
    ParticipantOptionModel,
    ParticipantOptionQueryModel,
    ProgressPageModel,
    ProgressQueryModel,
    ProjectCompleteRequestModel,
    ProjectCompleteResultModel,
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
from module_feedback.service import (
    FeedbackProgressService,
    FeedbackProjectService,
    FeedbackPublicationService,
    FeedbackQuestionnaireService,
    ProjectCompletionExecutionError,
)
from module_feedback.service.system_templates import list_system_templates
from utils.log_util import logger
from utils.response_util import ResponseUtil

project_controller = APIRouterPro(
    prefix='/feedback/projects',
    order_num=31,
    tags=['员工反馈-评价项目'],
    dependencies=[PreAuthDependency()],
)


@project_controller.get(
    '/system-templates', summary='查看系统问卷模板', dependencies=[UserInterfaceAuthDependency('feedback:project:add')]
)
async def system_templates(request: Request) -> Response:
    return ResponseUtil.success(data=list_system_templates())


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
@Log(
    title='评价项目',
    business_type=BusinessType.INSERT,
    request_log_mode='none',
    response_log_mode='include',
    response_include_fields=('code', 'data.projectId'),
)
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
@Log(
    title='问卷草稿',
    business_type=BusinessType.UPDATE,
    request_log_mode='include',
    response_log_mode='none',
    request_include_fields=('path_params.project_id', 'json_body.versionId', 'json_body.lockVersion'),
)
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
    '/{project_id}/participant-departments',
    summary='获取项目可选人员的组织架构',
    dependencies=[UserInterfaceAuthDependency('feedback:participant:manage')],
)
async def list_feedback_participant_departments(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    project_scope_sql: Annotated[
        ColumnElement, DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id')
    ],
    user_scope_sql: Annotated[ColumnElement, DataScopeDependency(SysUser, user_alias='user_id', dept_alias='dept_id')],
) -> Response:
    result = await FeedbackPublicationService.list_participant_departments(
        query_db, project_id, project_scope_sql, user_scope_sql
    )
    return ResponseUtil.success(data=result)


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
@Log(
    title='发布配置',
    business_type=BusinessType.UPDATE,
    request_log_mode='include',
    response_log_mode='none',
    request_include_fields=('path_params.project_id', 'json_body.versionId', 'json_body.projectLockVersion'),
)
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
@Log(
    title='评价项目发布',
    business_type=BusinessType.UPDATE,
    request_log_mode='include',
    response_log_mode='include',
    request_include_fields=('path_params.project_id', 'json_body.versionId', 'json_body.projectLockVersion'),
    response_include_fields=(
        'code',
        'data.projectId',
        'data.versionId',
        'data.assignmentCount',
        'data.alreadyPublished',
    ),
)
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
    '/{project_id}/progress',
    summary='获取评价项目回收进度',
    response_model=DataResponseModel[ProgressPageModel],
    dependencies=[UserInterfaceAuthDependency('feedback:progress:view')],
)
@Log(
    title='评价项目进度',
    business_type=BusinessType.OTHER,
    request_log_mode='include',
    response_log_mode='include',
    request_include_fields=(
        'path_params.project_id',
        'query_params.pageNum',
        'query_params.pageSize',
        'query_params.evaluatorUserId',
        'query_params.targetUserId',
        'query_params.relationId',
        'query_params.status',
    ),
    response_include_fields=('code', 'msg', 'data.projectId', 'data.projectStatus', 'data.summary'),
)
async def get_feedback_project_progress(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    query_object: Annotated[ProgressQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    project_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
    target_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProjectTarget, user_alias='target_user_id', dept_alias='target_dept_id'),
    ],
) -> Response:
    try:
        result = await FeedbackProgressService.get_progress(
            query_db, project_id, query_object, project_scope_sql, target_scope_sql
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.bind(exception_type=type(exc).__name__).error('读取评价项目进度失败，project_id={}', project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'code': 'PROJECT_PROGRESS_FAILED',
                'message': '项目进度读取失败，请稍后重试',
            },
        ) from exc
    return ResponseUtil.success(data=result.model_dump(by_alias=True, mode='json'))


@project_controller.get(
    '/{project_id}/completion-precheck',
    summary='预检评价项目完成影响',
    response_model=DataResponseModel[CompletionPrecheckModel],
    dependencies=[UserInterfaceAuthDependency('feedback:project:complete')],
)
@Log(
    title='评价项目完成预检',
    business_type=BusinessType.OTHER,
    request_log_mode='include',
    response_log_mode='include',
    request_include_fields=('path_params.project_id',),
    response_include_fields=(
        'code',
        'msg',
        'data.projectId',
        'data.projectStatus',
        'data.dataScopeComplete',
        'data.canComplete',
        'data.summary',
    ),
)
async def get_feedback_project_completion_precheck(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    project_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
    target_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProjectTarget, user_alias='target_user_id', dept_alias='target_dept_id'),
    ],
) -> Response:
    try:
        result = await FeedbackProgressService.get_precheck(query_db, project_id, project_scope_sql, target_scope_sql)
    except HTTPException:
        raise
    except Exception as exc:
        logger.bind(exception_type=type(exc).__name__).error('评价项目完成预检失败，project_id={}', project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'code': 'PROJECT_COMPLETION_PRECHECK_FAILED',
                'message': '项目完成预检失败，请稍后重试',
            },
        ) from exc
    return ResponseUtil.success(data=result.model_dump(by_alias=True, mode='json'))


@project_controller.post(
    '/{project_id}/complete',
    summary='手动完成评价项目',
    response_model=DataResponseModel[ProjectCompleteResultModel],
    dependencies=[UserInterfaceAuthDependency('feedback:project:complete')],
)
@Log(
    title='评价项目完成',
    business_type=BusinessType.UPDATE,
    request_log_mode='include',
    response_log_mode='include',
    request_include_fields=(
        'path_params.project_id',
        'json_body.projectLockVersion',
        'json_body.completionReason',
        'json_body.expectedSummary',
    ),
    response_include_fields=(
        'code',
        'msg',
        'data.code',
        'data.projectId',
        'data.projectStatus',
        'data.projectLockVersion',
        'data.completedBy',
        'data.completedTime',
        'data.completionReason',
        'data.alreadyCompleted',
        'data.summary',
    ),
)
async def complete_feedback_project(
    request: Request,
    project_id: Annotated[int, Path(ge=1, description='评价项目ID')],
    page_object: ProjectCompleteRequestModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    project_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id'),
    ],
    target_scope_sql: Annotated[
        ColumnElement,
        DataScopeDependency(FbProjectTarget, user_alias='target_user_id', dept_alias='target_dept_id'),
    ],
) -> Response:
    try:
        result = await FeedbackProgressService.complete_project(
            query_db,
            project_id,
            page_object,
            current_user.user.user_id,
            current_user.user.user_name,
            project_scope_sql,
            target_scope_sql,
            request_id=TraceCtx.get_request_id() or None,
            trace_id=TraceCtx.get_trace_id() or None,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        problem_code = str(detail.get('code') or 'PROJECT_COMPLETION_FAILED')
        failure_stage = {
            'PROJECT_NOT_FOUND': 'project_lock',
            'PROJECT_NOT_ACTIVE': 'project_state_check',
            'PROJECT_COMPLETION_SCOPE_FORBIDDEN': 'target_scope_check',
            'PROJECT_HAS_NO_ASSIGNMENTS': 'summary_before_completion',
            'PROJECT_VERSION_CONFLICT': 'version_check',
            'COMPLETION_PRECHECK_STALE': 'stale_precheck_build',
        }.get(problem_code, 'business_check')
        logger.bind(
            event='feedback_project_completion_failed',
            project_id=project_id,
            operator_user_id=current_user.user.user_id,
            problem_code=problem_code,
            failure_stage=failure_stage,
            request_id=TraceCtx.get_request_id() or None,
            trace_id=TraceCtx.get_trace_id() or None,
        ).warning('评价项目完成请求被拒绝')
        raise
    except ProjectCompletionExecutionError as exc:
        logger.bind(
            event='feedback_project_completion_failed',
            project_id=project_id,
            operator_user_id=current_user.user.user_id,
            problem_code=exc.problem_code,
            failure_stage=exc.stage,
            request_id=TraceCtx.get_request_id() or None,
            trace_id=TraceCtx.get_trace_id() or None,
            exception_type=type(exc.__cause__ or exc).__name__,
        ).error('评价项目完成失败')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'code': 'PROJECT_COMPLETION_FAILED',
                'message': '项目完成失败，事务已回滚',
            },
        ) from exc
    except Exception as exc:
        logger.bind(
            event='feedback_project_completion_failed',
            project_id=project_id,
            operator_user_id=current_user.user.user_id,
            problem_code='PROJECT_COMPLETION_FAILED',
            failure_stage='service_call',
            request_id=TraceCtx.get_request_id() or None,
            trace_id=TraceCtx.get_trace_id() or None,
            exception_type=type(exc).__name__,
        ).error('评价项目完成失败')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'code': 'PROJECT_COMPLETION_FAILED',
                'message': '项目完成失败，事务已回滚',
            },
        ) from exc
    return ResponseUtil.success(msg='项目已完成', data=result.model_dump(by_alias=True, mode='json'))


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
@Log(
    title='评价项目',
    business_type=BusinessType.UPDATE,
    request_log_mode='include',
    response_log_mode='none',
    request_include_fields=('path_params.project_id',),
)
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
@Log(
    title='评价项目',
    business_type=BusinessType.DELETE,
    request_log_mode='include',
    response_log_mode='none',
    request_include_fields=('path_params.project_id',),
)
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
