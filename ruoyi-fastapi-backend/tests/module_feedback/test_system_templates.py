from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.exception import ServiceException
from module_feedback.dao import FeedbackProjectDao, FeedbackQuestionnaireDao
from module_feedback.entity.vo.project_vo import ProjectCreateModel
from module_feedback.service.project_service import FeedbackProjectService
from module_feedback.service.system_templates import build_template, list_system_templates
from module_feedback.validators import get_publish_validation_issues

TOTAL_WEIGHT = 100
EMPLOYEE_PAGE_COUNT = 6


def test_templates_are_valid_independent_documents() -> None:
    for item in list_system_templates():
        a = build_template(item['templateKey'], 1, '项目甲')
        b = build_template(item['templateKey'], 2, '项目乙')
        assert sum(i.weight for i in a.indicators) == TOTAL_WEIGHT
        codes_a = {q.question_code for page in a.pages for q in page.questions}
        codes_b = {q.question_code for page in b.pages for q in page.questions}
        assert codes_a.isdisjoint(codes_b)
        assert all(set(i.question_codes) <= codes_a for i in a.indicators)
        assert a.pages[-1].questions[0].is_scored is False
        assert not get_publish_validation_issues(a)


@pytest.mark.asyncio
async def test_template_copy_failure_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    db = SimpleNamespace(add_all=MagicMock(), commit=AsyncMock(), rollback=AsyncMock())
    monkeypatch.setattr(FeedbackProjectDao, 'add_project', AsyncMock(return_value=SimpleNamespace(project_id=1)))
    monkeypatch.setattr(
        FeedbackProjectDao, 'add_questionnaire_version', AsyncMock(return_value=SimpleNamespace(version_id=2))
    )
    replace = AsyncMock(side_effect=RuntimeError('复制失败'))
    monkeypatch.setattr(FeedbackQuestionnaireDao, 'replace_draft_document', replace)
    with pytest.raises(RuntimeError):
        await FeedbackProjectService.create_project(
            db, ProjectCreateModel(projectName='测试', templateKey='employee-360-v1'), 1, 1, 'hr'
        )
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
    assert len(replace.call_args.args[2]) == EMPLOYEE_PAGE_COUNT


@pytest.mark.asyncio
async def test_unknown_template_rejected_before_inserts(monkeypatch: pytest.MonkeyPatch) -> None:
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    add = AsyncMock()
    monkeypatch.setattr(FeedbackProjectDao, 'add_project', add)
    with pytest.raises(ServiceException) as exc:
        await FeedbackProjectService.create_project(
            db, ProjectCreateModel(projectName='测试', templateKey='unknown'), 1, 1, 'hr'
        )
    assert '系统模板不存在' in exc.value.message
    add.assert_not_awaited()
