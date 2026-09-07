from typing import Annotated, Any

from fastapi import Path, Query, Request, Response
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.data_scope import DataScopeDependency
from common.aspect.db_session import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel, PageResponseModel
from module_feedback.entity.do import FbProject, FbProjectTarget
from module_feedback.entity.vo.report_vo import (
    AnswerProjectModel,
    AnswerProjectQueryModel,
    PersonalReportModel,
    ReportCalculationModel,
    ReportProjectModel,
    ReportQueryModel,
    ScoreSourceModel,
    SubmittedAnswerDetailModel,
    SubmittedAnswerQueryModel,
    SubmittedAnswerRowModel,
    TeamReportModel,
)
from module_feedback.service.report_service import FeedbackReportService
from utils.response_util import ResponseUtil

report_controller = APIRouterPro(
    prefix='/feedback',
    order_num=33,
    tags=['员工反馈-计分与报告'],
    dependencies=[PreAuthDependency()],
)
Db = Annotated[AsyncSession, DBSessionDependency()]
ProjectId = Annotated[int, Path(ge=1)]
ProjectScope = Annotated[
    ColumnElement, DataScopeDependency(FbProject, user_alias='owner_user_id', dept_alias='owner_dept_id')
]
TargetScope = Annotated[
    ColumnElement, DataScopeDependency(FbProjectTarget, user_alias='target_user_id', dept_alias='target_dept_id')
]


def _response(result: Any, *, paged: bool = False) -> Response:
    response = (
        ResponseUtil.success(model_content=result)
        if paged
        else ResponseUtil.success(
            data=result.model_dump(by_alias=True, mode='json'),
        )
    )
    response.headers['Cache-Control'] = 'no-store'
    return response


@report_controller.get(
    '/reports/projects',
    response_model=PageResponseModel[ReportProjectModel],
    dependencies=[UserInterfaceAuthDependency('feedback:report:view')],
)
@Log(title='评价报告项目', business_type=BusinessType.OTHER, request_log_mode='none', response_log_mode='none')
async def report_projects(
    request: Request,
    query: Annotated[ReportQueryModel, Query()],
    db: Db,
    project_scope: ProjectScope,
    target_scope: TargetScope,
) -> Response:
    return _response(await FeedbackReportService.list_projects(db, query, project_scope, target_scope), paged=True)


@report_controller.post(
    '/projects/{project_id}/reports/calculate',
    response_model=DataResponseModel[ReportCalculationModel],
    dependencies=[UserInterfaceAuthDependency('feedback:report:view')],
)
@Log(
    title='评价报告生成',
    business_type=BusinessType.INSERT,
    request_log_mode='include',
    request_include_fields=('path_params.project_id',),
    response_log_mode='none',
)
async def calculate_report(
    request: Request, project_id: ProjectId, db: Db, project_scope: ProjectScope, target_scope: TargetScope
) -> Response:
    return _response(await FeedbackReportService.calculate(db, project_id, project_scope, target_scope))


@report_controller.get(
    '/projects/{project_id}/reports',
    response_model=DataResponseModel[TeamReportModel],
    dependencies=[UserInterfaceAuthDependency('feedback:report:view')],
)
@Log(
    title='评价团队报告',
    business_type=BusinessType.OTHER,
    request_log_mode='include',
    request_include_fields=('path_params.project_id',),
    response_log_mode='none',
)
async def team_report(
    request: Request,
    project_id: ProjectId,
    query: Annotated[ReportQueryModel, Query()],
    db: Db,
    project_scope: ProjectScope,
    target_scope: TargetScope,
) -> Response:
    return _response(await FeedbackReportService.team(db, project_id, query, project_scope, target_scope))


@report_controller.get(
    '/projects/{project_id}/reports/{target_user_id}',
    response_model=DataResponseModel[PersonalReportModel],
    dependencies=[UserInterfaceAuthDependency('feedback:report:view')],
)
@Log(
    title='评价个人报告',
    business_type=BusinessType.OTHER,
    request_log_mode='include',
    request_include_fields=('path_params.project_id', 'path_params.target_user_id'),
    response_log_mode='none',
)
async def personal_report(
    request: Request,
    project_id: ProjectId,
    target_user_id: Annotated[int, Path(ge=1)],
    db: Db,
    project_scope: ProjectScope,
    target_scope: TargetScope,
) -> Response:
    return _response(await FeedbackReportService.person(db, project_id, target_user_id, project_scope, target_scope))


@report_controller.get(
    '/projects/{project_id}/answers',
    response_model=PageResponseModel[SubmittedAnswerRowModel],
    dependencies=[UserInterfaceAuthDependency('feedback:answer:view')],
)
@Log(
    title='已提交评价答卷列表',
    business_type=BusinessType.OTHER,
    request_log_mode='include',
    request_include_fields=('path_params.project_id', 'query_params.targetUserId'),
    response_log_mode='none',
)
async def submitted_answers(
    request: Request,
    project_id: ProjectId,
    query: Annotated[SubmittedAnswerQueryModel, Query()],
    db: Db,
    project_scope: ProjectScope,
    target_scope: TargetScope,
) -> Response:
    return _response(
        await FeedbackReportService.answers(db, project_id, query, project_scope, target_scope), paged=True
    )


@report_controller.get(
    '/projects/{project_id}/answers/{assignment_id}',
    response_model=DataResponseModel[SubmittedAnswerDetailModel],
    dependencies=[UserInterfaceAuthDependency('feedback:answer:view')],
)
@Log(
    title='已提交评价原始答案',
    business_type=BusinessType.OTHER,
    request_log_mode='include',
    request_include_fields=('path_params.project_id', 'path_params.assignment_id'),
    response_log_mode='none',
)
async def submitted_answer(
    request: Request,
    project_id: ProjectId,
    assignment_id: Annotated[int, Path(ge=1)],
    db: Db,
    project_scope: ProjectScope,
    target_scope: TargetScope,
) -> Response:
    return _response(await FeedbackReportService.answer(db, project_id, assignment_id, project_scope, target_scope))


@report_controller.get(
    '/projects/{project_id}/reports/{target_user_id}/source',
    response_model=DataResponseModel[ScoreSourceModel],
    dependencies=[UserInterfaceAuthDependency('feedback:report:view')],
)
@Log(title='评价得分来源', business_type=BusinessType.OTHER, request_log_mode='none', response_log_mode='none')
async def score_source(
    request: Request,
    project_id: ProjectId,
    target_user_id: Annotated[int, Path(ge=1)],
    db: Db,
    project_scope: ProjectScope,
    target_scope: TargetScope,
) -> Response:
    return _response(await FeedbackReportService.source(db, project_id, target_user_id, project_scope, target_scope))


@report_controller.get(
    '/projects/{project_id}/reports/{target_user_id}/source/sheets',
    response_model=DataResponseModel[ScoreSourceModel],
    dependencies=[
        UserInterfaceAuthDependency('feedback:report:view'),
        UserInterfaceAuthDependency('feedback:answer:view'),
    ],
)
@Log(title='评价得分答卷依据', business_type=BusinessType.OTHER, request_log_mode='none', response_log_mode='none')
async def score_source_sheets(
    request: Request,
    project_id: ProjectId,
    target_user_id: Annotated[int, Path(ge=1)],
    indicator_id: Annotated[int, Query(alias='indicatorId', ge=1)],
    relation_id: Annotated[int, Query(alias='relationId', ge=1)],
    db: Db,
    project_scope: ProjectScope,
    target_scope: TargetScope,
) -> Response:
    return _response(
        await FeedbackReportService.source(
            db, project_id, target_user_id, project_scope, target_scope, detail=(indicator_id, relation_id)
        )
    )


@report_controller.get(
    '/answers/projects',
    response_model=PageResponseModel[AnswerProjectModel],
    dependencies=[UserInterfaceAuthDependency('feedback:answer:view')],
)
@Log(title='已提交答卷项目选择', business_type=BusinessType.OTHER, request_log_mode='none', response_log_mode='none')
async def answer_projects(
    request: Request,
    query: Annotated[AnswerProjectQueryModel, Query()],
    db: Db,
    project_scope: ProjectScope,
    target_scope: TargetScope,
) -> Response:
    return _response(await FeedbackReportService.answer_projects(db, query, project_scope, target_scope), paged=True)
