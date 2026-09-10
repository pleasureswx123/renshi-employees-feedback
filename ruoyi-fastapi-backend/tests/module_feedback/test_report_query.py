from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from module_feedback.dao.report_dao import FeedbackReportDao
from module_feedback.entity.vo.report_vo import ReportQueryModel


@pytest.mark.asyncio
@pytest.mark.parametrize('direction', ['asc', 'desc'])
async def test_relation_sort_and_department_filter_before_pagination(direction: str) -> None:
    db = Mock(scalar=AsyncMock(return_value=0), execute=AsyncMock(return_value=Mock(mappings=list)))
    await FeedbackReportDao.team_rows(
        db,
        1,
        2,
        {3},
        ReportQueryModel(department='研发部', sortRelationId=8, sortOrder=direction, pageNum=2, pageSize=10),
    )
    sql = str(
        db.execute.call_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True})
    )
    assert 'avg(fb_score_result.score)' in sql
    assert 'count(fb_score_result.score) = count(*)' in sql
    assert "target_dept_name = '研发部'" in sql
    assert f'average {direction.upper()} NULLS LAST' in sql
    assert 'LIMIT 10 OFFSET 10' in sql
    assert 'rank() OVER (ORDER BY fb_score_result.score DESC NULLS LAST)' in sql


def test_sort_query_rejects_invalid_direction_and_relation() -> None:
    for query in [{'sortOrder': 'invalid'}, {'sortRelationId': 0}, {'pageSize': 101}]:
        with pytest.raises(ValidationError):
            ReportQueryModel(**query)
