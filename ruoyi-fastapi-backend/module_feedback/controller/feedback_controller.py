from typing import Annotated

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.db_session import DBSessionDependency
from common.aspect.pre_auth import PreAuthDependency
from common.router import APIRouterPro
from common.vo import DataResponseModel
from module_feedback.service.schema_service import FeedbackSchemaService
from utils.response_util import ResponseUtil

feedback_controller = APIRouterPro(prefix='/feedback', order_num=30, tags=['员工反馈模块'])


@feedback_controller.get(
    '/health',
    summary='获取评价模块状态',
    description='登录用户核验评价模块迁移版本与正式得分精度的只读探针，不返回业务数据',
    response_model=DataResponseModel[dict[str, str]],
    dependencies=[PreAuthDependency()],
)
async def get_feedback_module_health(db: Annotated[AsyncSession, DBSessionDependency()]) -> Response:
    """只读核验实际数据库；未升级的数据库不能报告为就绪。"""
    response = ResponseUtil.success(data=await FeedbackSchemaService.health(db))
    response.headers['Cache-Control'] = 'no-store'
    return response
