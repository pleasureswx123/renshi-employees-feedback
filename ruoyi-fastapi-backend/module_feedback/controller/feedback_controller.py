from fastapi import Response

from common.aspect.pre_auth import PreAuthDependency
from common.router import APIRouterPro
from common.vo import DataResponseModel
from utils.response_util import ResponseUtil

feedback_controller = APIRouterPro(prefix='/feedback', order_num=30, tags=['员工反馈模块'])


@feedback_controller.get(
    '/health',
    summary='获取评价模块状态',
    description='登录用户用于确认评价平台后端模块已接入的只读探针，不返回业务数据',
    response_model=DataResponseModel[dict[str, str]],
    dependencies=[PreAuthDependency()],
)
async def get_feedback_module_health() -> Response:
    """返回评价模块当前阶段和固定接口前缀。"""
    return ResponseUtil.success(
        data={
            'module': 'feedback',
            'status': 'ready',
            'phase': 'P1',
            'apiPrefix': '/feedback',
        }
    )
