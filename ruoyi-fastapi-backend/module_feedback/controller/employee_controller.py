from typing import Annotated

from fastapi import Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_session import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import DataResponseModel, PageResponseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_feedback.entity.vo.employee_vo import (
    AnswerDraftSaveModel,
    AnswerSubmitModel,
    EmployeeAnswerDetailModel,
    EmployeePageQueryModel,
    EmployeeProjectDetailModel,
    EmployeeProjectModel,
    EmployeeTaskModel,
)
from module_feedback.service.answer_service import FeedbackAnswerService
from module_feedback.service.employee_service import FeedbackEmployeeService
from utils.response_util import ResponseUtil

employee_controller = APIRouterPro(
    prefix='/feedback/employee',
    order_num=32,
    tags=['员工反馈-我的评价'],
    dependencies=[PreAuthDependency()],
)

DbSession = Annotated[AsyncSession, DBSessionDependency()]
LoginUser = Annotated[CurrentUserModel, CurrentUserDependency()]
TaskId = Annotated[int, Path(ge=1, description='评价任务ID')]


@employee_controller.get(
    '/projects',
    summary='获取我的待办项目',
    response_model=PageResponseModel[EmployeeProjectModel],
    dependencies=[UserInterfaceAuthDependency('feedback:task:view')],
)
async def list_my_projects(
    request: Request, query: Annotated[EmployeePageQueryModel, Query()], db: DbSession, user: LoginUser
) -> Response:
    result = await FeedbackEmployeeService.list_projects(db, user.user.user_id, query)
    return ResponseUtil.success(model_content=result)


@employee_controller.get(
    '/projects/{project_id}',
    summary='获取本人项目任务和进度',
    response_model=DataResponseModel[EmployeeProjectDetailModel],
    dependencies=[UserInterfaceAuthDependency('feedback:task:view')],
)
async def get_my_project(
    request: Request, project_id: Annotated[int, Path(ge=1)], db: DbSession, user: LoginUser
) -> Response:
    result = await FeedbackEmployeeService.get_project(db, project_id, user.user.user_id)
    return ResponseUtil.success(data=result.model_dump(mode='json', by_alias=True))


@employee_controller.get(
    '/tasks/{assignment_id}',
    summary='获取本人的冻结问卷和草稿',
    response_model=DataResponseModel[EmployeeAnswerDetailModel],
    dependencies=[UserInterfaceAuthDependency('feedback:task:view')],
)
async def get_my_task(request: Request, assignment_id: TaskId, db: DbSession, user: LoginUser) -> Response:
    result = await FeedbackEmployeeService.get_task(db, assignment_id, user.user.user_id)
    return ResponseUtil.success(data=result.model_dump(mode='json', by_alias=True))


@employee_controller.put(
    '/tasks/{assignment_id}/draft',
    summary='暂存本人的当前任务答卷',
    response_model=DataResponseModel[EmployeeAnswerDetailModel],
    dependencies=[UserInterfaceAuthDependency('feedback:task:answer')],
)
@Log(title='评价答卷暂存', business_type=BusinessType.UPDATE, request_log_mode='none', response_log_mode='none')
async def save_my_draft(
    request: Request, assignment_id: TaskId, payload: AnswerDraftSaveModel, db: DbSession, user: LoginUser
) -> Response:
    result = await FeedbackAnswerService.save_draft(db, assignment_id, user.user.user_id, payload)
    return ResponseUtil.success(msg='答卷已暂存', data=result.model_dump(mode='json', by_alias=True))


@employee_controller.post(
    '/tasks/{assignment_id}/submit',
    summary='正式提交本人当前任务答卷',
    response_model=DataResponseModel[EmployeeAnswerDetailModel],
    dependencies=[UserInterfaceAuthDependency('feedback:task:submit')],
)
@Log(title='评价答卷提交', business_type=BusinessType.UPDATE, request_log_mode='none', response_log_mode='none')
async def submit_my_answer(
    request: Request, assignment_id: TaskId, payload: AnswerSubmitModel, db: DbSession, user: LoginUser
) -> Response:
    result = await FeedbackAnswerService.submit(db, assignment_id, user.user.user_id, payload)
    return ResponseUtil.success(msg='答卷已提交', data=result.model_dump(mode='json', by_alias=True))


@employee_controller.get(
    '/history',
    summary='获取我评价的提交记录',
    response_model=PageResponseModel[EmployeeTaskModel],
    dependencies=[UserInterfaceAuthDependency('feedback:history:view')],
)
async def list_my_history(
    request: Request, query: Annotated[EmployeePageQueryModel, Query()], db: DbSession, user: LoginUser
) -> Response:
    result = await FeedbackEmployeeService.list_history(db, user.user.user_id, query)
    return ResponseUtil.success(model_content=result)


@employee_controller.get(
    '/history/{assignment_id}',
    summary='只读查看本人已提交答案',
    response_model=DataResponseModel[EmployeeAnswerDetailModel],
    dependencies=[UserInterfaceAuthDependency('feedback:history:view')],
)
@Log(title='本人评价历史', business_type=BusinessType.OTHER, request_log_mode='none', response_log_mode='none')
async def get_my_history(request: Request, assignment_id: TaskId, db: DbSession, user: LoginUser) -> Response:
    result = await FeedbackEmployeeService.get_task(db, assignment_id, user.user.user_id, history=True)
    return ResponseUtil.success(data=result.model_dump(mode='json', by_alias=True))
