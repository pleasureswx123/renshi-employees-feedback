import json

import pytest
from fastapi import FastAPI, status

from exceptions.exception import ConflictException
from exceptions.handle import handle_exception


@pytest.mark.asyncio
async def test_conflict_exception_uses_real_http_409_and_keeps_validation_issues() -> None:
    app = FastAPI()
    handle_exception(app)
    validation_issues = [
        {
            'code': 'TARGET_REQUIRED',
            'path': 'targets',
            'message': '至少选择一名被评价人',
        }
    ]

    handler = app.exception_handlers[ConflictException]
    response = await handler(
        None,
        ConflictException(message='发布前检查未通过', data={'validationIssues': validation_issues}),
    )
    payload = json.loads(response.body)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert payload['code'] == status.HTTP_409_CONFLICT
    assert payload['success'] is False
    assert payload['data']['validationIssues'] == validation_issues
