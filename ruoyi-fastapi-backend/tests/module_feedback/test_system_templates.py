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


def test_history_copy_rebuilds_bindings_and_keeps_source():
    source = build_template('employee-360-v1', 9, '原项目')
    before = source.model_dump()
    copied = FeedbackProjectService.clone_questionnaire(source)
    original_codes = {q.question_code for p in source.pages for q in p.questions}
    copied_codes = {q.question_code for p in copied.pages for q in p.questions}
    assert original_codes.isdisjoint(copied_codes)
    assert all(set(i.question_codes) <= copied_codes for i in copied.indicators)
    assert [i.weight for i in copied.indicators] == [i.weight for i in source.indicators]
    assert not get_publish_validation_issues(copied)
    copied.pages[0].questions[0].title = '新题目'
    assert source.model_dump() == before


def test_history_and_template_are_exclusive():
    with pytest.raises(ValueError):
        ProjectCreateModel(projectName='测试', templateKey='employee-360-v1', sourceProjectId=1)


@pytest.mark.asyncio
async def test_history_missing_or_out_of_scope_rejected(monkeypatch):
    load = AsyncMock(return_value=None)
    monkeypatch.setattr(FeedbackQuestionnaireDao, 'get_source_by_project_id', load)
    with pytest.raises(ServiceException):
        await FeedbackProjectService.get_questionnaire_source(None, 19, False)
    load.assert_awaited_once_with(None, 19, False)


@pytest.mark.asyncio
async def test_history_create_checks_scope_before_writing(monkeypatch):
    db = SimpleNamespace(rollback=AsyncMock())
    locked = AsyncMock(side_effect=ServiceException(message='无权限'))
    insert = AsyncMock()
    monkeypatch.setattr(FeedbackProjectDao, 'get_project_for_update_scoped', locked)
    monkeypatch.setattr(FeedbackProjectDao, 'add_project', insert)
    with pytest.raises(ServiceException):
        await FeedbackProjectService.create_project(
            db, ProjectCreateModel(projectName='测试', sourceProjectId=19), 1, 1, 'hr'
        )
    locked.assert_awaited_once_with(db, 19, False)
    insert.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('fail_copy', [False, True])
async def test_history_create_transaction(monkeypatch, fail_copy):
    db = SimpleNamespace(add_all=MagicMock(), commit=AsyncMock(), rollback=AsyncMock())
    source = build_template('employee-360-v1', 19, '历史问卷')
    version = SimpleNamespace(version_id=22)
    monkeypatch.setattr(FeedbackProjectService, '_get_locked_project', AsyncMock())
    monkeypatch.setattr(FeedbackProjectService, 'get_questionnaire_source', AsyncMock(return_value=source))
    monkeypatch.setattr(FeedbackProjectDao, 'add_project', AsyncMock(return_value=SimpleNamespace(project_id=21)))
    monkeypatch.setattr(FeedbackProjectDao, 'add_questionnaire_version', AsyncMock(return_value=version))
    monkeypatch.setattr(FeedbackProjectDao, 'get_project_by_id_scoped', AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(FeedbackProjectService, '_to_detail', lambda _project: 'created')
    replace = AsyncMock(side_effect=RuntimeError('写入失败') if fail_copy else None)
    monkeypatch.setattr(FeedbackQuestionnaireDao, 'replace_draft_document', replace)
    create = FeedbackProjectService.create_project(
        db, ProjectCreateModel(projectName='新项目', sourceProjectId=19), 1, 1, 'hr', True
    )
    if fail_copy:
        with pytest.raises(RuntimeError):
            await create
        db.commit.assert_not_awaited()
        db.rollback.assert_awaited_once()
    else:
        assert await create == 'created'
        db.commit.assert_awaited_once()
        db.rollback.assert_not_awaited()
    pages, indicators, bindings = replace.call_args.args[2:]
    codes = {q.question_code for page in pages for q in page.questions}
    assert all(set(bound) <= codes for bound in bindings.values())
    assert all(page.version_id == 22 for page in pages)
    assert all(i.version_id == 22 for i in indicators)
    assert version.settings['sourceProjectId'] == 19
    assert source.version_id == 19
