from fastapi import FastAPI, Request, Response
from fastapi.exceptions import HTTPException, RequestValidationError
from pydantic_validation_decorator import FieldValidationError

from common.context import RequestContext
from exceptions.exception import (
    AuthException,
    ConflictException,
    FileRangeNotSatisfiableException,
    LoginException,
    ModelValidatorException,
    PermissionException,
    ServiceException,
    ServiceWarning,
)
from middlewares.trace_middleware.ctx import TraceCtx
from utils.log_util import logger
from utils.response_util import JSONResponse, ResponseUtil, jsonable_encoder


def handle_exception(app: FastAPI) -> None:
    """
    全局异常处理
    """

    # 自定义token检验异常
    @app.exception_handler(AuthException)
    async def auth_exception_handler(request: Request, exc: AuthException) -> Response:
        return ResponseUtil.unauthorized(data=exc.data, msg=exc.message)

    # 自定义登录检验异常
    @app.exception_handler(LoginException)
    async def login_exception_handler(request: Request, exc: LoginException) -> Response:
        return ResponseUtil.failure(data=exc.data, msg=exc.message)

    # 自定义模型检验异常
    @app.exception_handler(ModelValidatorException)
    async def model_validator_exception_handler(request: Request, exc: ModelValidatorException) -> Response:
        logger.warning(exc.message)
        return ResponseUtil.failure(data=exc.data, msg=exc.message)

    # 自定义字段检验异常
    @app.exception_handler(FieldValidationError)
    async def field_validation_error_handler(request: Request, exc: FieldValidationError) -> Response:
        logger.warning(exc.message)
        return ResponseUtil.failure(msg=exc.message)

    # 自定义权限检验异常
    @app.exception_handler(PermissionException)
    async def permission_exception_handler(request: Request, exc: PermissionException) -> Response:
        return ResponseUtil.forbidden(data=exc.data, msg=exc.message)

    # 自定义服务异常
    @app.exception_handler(ServiceException)
    async def service_exception_handler(request: Request, exc: ServiceException) -> Response:
        logger.error(exc.message)
        return ResponseUtil.error(data=exc.data, msg=exc.message)

    # 自定义服务警告
    @app.exception_handler(ServiceWarning)
    async def service_warning_handler(request: Request, exc: ServiceWarning) -> Response:
        logger.warning(exc.message)
        return ResponseUtil.failure(data=exc.data, msg=exc.message)

    @app.exception_handler(ConflictException)
    async def conflict_exception_handler(request: Request, exc: ConflictException) -> Response:
        return ResponseUtil.conflict(data=exc.data, msg=exc.message)

    # 文件Range范围不可满足异常
    @app.exception_handler(FileRangeNotSatisfiableException)
    async def file_range_not_satisfiable_exception_handler(
        request: Request,
        exc: FileRangeNotSatisfiableException,
    ) -> Response:
        return Response(
            status_code=416,
            headers={
                'Accept-Ranges': 'bytes',
                'Content-Range': f'bytes */{exc.file_size}',
                'Content-Length': '0',
            },
        )

    # 处理其他http请求异常
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
        if isinstance(exc.detail, dict) and exc.detail.get('code'):
            detail = dict(exc.detail)
            message = str(detail.pop('message', detail['code']))
            return JSONResponse(
                content=jsonable_encoder(
                    {
                        'code': exc.status_code,
                        'msg': message,
                        'success': False,
                        'data': detail,
                    }
                ),
                status_code=exc.status_code,
                headers=exc.headers,
            )
        return JSONResponse(
            content=jsonable_encoder({'code': exc.status_code, 'msg': exc.detail}),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> Response:
        path = request.url.path
        is_p7_route = path.startswith('/feedback/projects/') and path.endswith(
            ('/progress', '/completion-precheck', '/complete')
        )
        if is_p7_route:
            safe_errors = [{'type': error['type'], 'loc': error['loc'], 'msg': error['msg']} for error in exc.errors()]
            if path.endswith('/complete'):
                try:
                    operator_user_id = RequestContext.get_current_user().user.user_id
                except Exception:
                    operator_user_id = None
                raw_project_id = request.path_params.get('project_id')
                project_id = (
                    int(raw_project_id) if str(raw_project_id).isascii() and str(raw_project_id).isdigit() else None
                )
                logger.bind(
                    event='feedback_project_completion_failed',
                    project_id=project_id,
                    operator_user_id=operator_user_id,
                    problem_code='VALIDATION_ERROR',
                    failure_stage='request_validation',
                    request_id=TraceCtx.get_request_id() or None,
                    trace_id=TraceCtx.get_trace_id() or None,
                ).warning('评价项目完成请求校验失败')
            return JSONResponse(
                content=jsonable_encoder(
                    {
                        'code': 422,
                        'msg': '请求参数校验失败',
                        'success': False,
                        'data': {'code': 'VALIDATION_ERROR', 'validationErrors': safe_errors},
                    }
                ),
                status_code=422,
            )
        return JSONResponse(content=jsonable_encoder({'detail': exc.errors()}), status_code=422)

    # 处理其他异常
    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception) -> Response:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))
