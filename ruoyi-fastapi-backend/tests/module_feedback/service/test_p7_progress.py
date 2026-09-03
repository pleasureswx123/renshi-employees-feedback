# ruff: noqa: PLC0415, PLR2004

from datetime import datetime
from decimal import Decimal
from inspect import getsource, signature
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy import true


def test_p7_slice_1_vo_camelcase_boundaries_identity_decimal_and_no_answers() -> None:
    from module_feedback.entity.vo.progress_vo import ProgressSummaryModel, ProjectCompleteRequestModel

    zero = ProgressSummaryModel.from_counts(PENDING=0, DRAFT=0, SUBMITTED=0, CLOSED_INCOMPLETE=0)
    rounded = ProgressSummaryModel.from_counts(PENDING=1, DRAFT=0, SUBMITTED=2, CLOSED_INCOMPLETE=0)
    assert zero.model_dump(by_alias=True)['completionRate'] == '0.00'
    assert rounded.completion_rate == '66.67'
    assert Decimal(rounded.completion_rate) == Decimal('66.67')
    assert (
        rounded.total_count
        == rounded.submitted_count + rounded.draft_count + rounded.pending_count + rounded.closed_incomplete_count
    )
    assert rounded.incomplete_count == rounded.draft_count + rounded.pending_count + rounded.closed_incomplete_count
    payload = rounded.model_dump(by_alias=True)
    assert set(payload) == {
        'totalCount',
        'submittedCount',
        'draftCount',
        'pendingCount',
        'closedIncompleteCount',
        'incompleteCount',
        'completionRate',
    }
    assert not any('answer' in key.lower() or 'score' in key.lower() for key in payload)

    request = ProjectCompleteRequestModel.model_validate(
        {
            'projectLockVersion': 0,
            'completionReason': '  截止完成  ',
            'expectedSummary': {
                key: payload[key]
                for key in ('totalCount', 'submittedCount', 'draftCount', 'pendingCount', 'closedIncompleteCount')
            },
        }
    )
    assert request.completion_reason == '截止完成'
    with pytest.raises(ValidationError):
        ProjectCompleteRequestModel.model_validate(
            {
                'projectLockVersion': -1,
                'completionReason': ' ',
                'expectedSummary': {
                    'totalCount': 2,
                    'submittedCount': 1,
                    'draftCount': 0,
                    'pendingCount': 0,
                    'closedIncompleteCount': 0,
                },
            }
        )

    valid_expected_summary = {
        'totalCount': 1,
        'submittedCount': 0,
        'draftCount': 0,
        'pendingCount': 1,
        'closedIncompleteCount': 0,
    }
    with pytest.raises(ValidationError):
        ProjectCompleteRequestModel.model_validate(
            {
                'projectLockVersion': True,
                'completionReason': '截止完成',
                'expectedSummary': valid_expected_summary,
            }
        )
    with pytest.raises(ValidationError):
        ProjectCompleteRequestModel.model_validate(
            {
                'projectLockVersion': 0,
                'completionReason': '截止完成',
                'expectedSummary': {**valid_expected_summary, 'pendingCount': True},
            }
        )

    trimmed = ProjectCompleteRequestModel.model_validate(
        {
            'projectLockVersion': 0,
            'completionReason': f'  {"完" * 500}  ',
            'expectedSummary': valid_expected_summary,
        }
    )
    assert len(trimmed.completion_reason) == 500


def test_p7_complete_has_no_production_failure_hook() -> None:
    from module_feedback.service.progress_service import FeedbackProgressService

    complete = FeedbackProgressService.complete_project
    assert 'failure_stage' not in signature(complete).parameters
    assert 'P7故障注入' not in getsource(complete)


def test_p7_large_visible_scope_uses_array_parameters_instead_of_expanding_asyncpg_bindings() -> None:
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg

    from module_feedback.dao.progress_dao import FeedbackProgressDao
    from module_feedback.entity.do import FbAssignment

    assignment_ids = tuple(range(1, 40001))
    assignment_statement = FeedbackProgressDao._base(9, 12, assignment_ids)
    target_statement = select(FbAssignment.assignment_id).where(
        FeedbackProgressDao._bigint_array_filter(
            FbAssignment.target_id,
            set(assignment_ids),
            'visible_target_ids',
        )
    )

    assignment_compiled = assignment_statement.compile(dialect=PGDialect_asyncpg())
    target_compiled = target_statement.compile(dialect=PGDialect_asyncpg())

    assert 'ANY' in str(assignment_compiled)
    assert 'ANY' in str(target_compiled)
    assert len(assignment_compiled.params) < 10
    assert len(target_compiled.params) == 1


@pytest.mark.asyncio
async def test_p7_slice_2_progress_uses_frozen_version_and_returns_complete_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from module_feedback.dao.progress_dao import FeedbackProgressDao
    from module_feedback.entity.vo.progress_vo import ProgressQueryModel
    from module_feedback.service.progress_service import FeedbackProgressService

    project = SimpleNamespace(
        project_id=9, project_name='年度反馈', status='ACTIVE', lock_version=3, current_questionnaire_version_id=77
    )
    rows = [
        SimpleNamespace(
            assignment_id=1,
            evaluator_user_id=2,
            evaluator_user_name='评委',
            evaluator_dept_name='研发',
            target_user_id=3,
            target_id=30,
            status='SUBMITTED',
            saved_time=None,
            submitted_time=datetime(2026, 9, 2),
            closed_time=None,
            target_user_name='目标',
            target_dept_id=4,
            target_dept_name='产品',
            relation_id=5,
            relation_code='REL_PEER',
            relation_name='同级',
            relation_sort_order=2,
        )
    ]
    monkeypatch.setattr(FeedbackProgressDao, 'get_project_scoped', AsyncMock(return_value=project))
    monkeypatch.setattr(FeedbackProgressDao, 'get_visible_target_ids', AsyncMock(return_value=({30}, 1)))
    monkeypatch.setattr(FeedbackProgressDao, 'lock_visible_assignments_for_share', AsyncMock())
    fetch = AsyncMock(return_value=(rows, 1))
    monkeypatch.setattr(FeedbackProgressDao, 'list_assignments', fetch)
    monkeypatch.setattr(
        FeedbackProgressDao, 'list_relation_options', AsyncMock(return_value=[(5, 'REL_PEER', '同级', 2)])
    )
    monkeypatch.setattr(FeedbackProgressDao, 'summarize_assignments', AsyncMock(return_value={'SUBMITTED': 1}))

    result = await FeedbackProgressService.get_progress(object(), 9, ProgressQueryModel(), true(), true())
    assert result.project_id == 9 and result.summary.submitted_count == 1
    assert result.summary.completion_rate == '100.00' and result.data_scope_complete
    assert result.rows[0].target_name == '目标' and result.filter_options.relations[0].relation_code == 'REL_PEER'
    assert fetch.await_args.args[2] == 77


def test_p7_progress_query_accepts_integer_query_strings_but_rejects_bool_and_decimal_forms() -> None:
    from module_feedback.entity.vo.progress_vo import ProgressQueryModel

    parsed = ProgressQueryModel.model_validate(
        {'pageNum': '2', 'pageSize': '50', 'evaluatorUserId': '7', 'targetUserId': '8', 'relationId': '9'}
    )
    assert (parsed.page_num, parsed.page_size, parsed.evaluator_user_id, parsed.target_user_id, parsed.relation_id) == (
        2,
        50,
        7,
        8,
        9,
    )
    for field, value in (
        ('pageNum', True),
        ('pageSize', 20.0),
        ('evaluatorUserId', '7.0'),
        ('targetUserId', False),
        ('relationId', 9.0),
    ):
        with pytest.raises(ValidationError):
            ProgressQueryModel.model_validate({field: value})


@pytest.mark.asyncio
async def test_p7_slice_3_scope_filters_relation_422_and_stable_paging(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    from module_feedback.dao.progress_dao import FeedbackProgressDao
    from module_feedback.entity.vo.progress_vo import ProgressQueryModel
    from module_feedback.service.progress_service import FeedbackProgressService

    project = SimpleNamespace(
        project_id=9, project_name='年度反馈', status='ACTIVE', lock_version=3, current_questionnaire_version_id=77
    )
    monkeypatch.setattr(FeedbackProgressDao, 'get_project_scoped', AsyncMock(return_value=project))
    monkeypatch.setattr(FeedbackProgressDao, 'get_visible_target_ids', AsyncMock(return_value=({30}, 2)))
    monkeypatch.setattr(FeedbackProgressDao, 'lock_visible_assignments_for_share', AsyncMock())
    monkeypatch.setattr(
        FeedbackProgressDao, 'list_relation_options', AsyncMock(return_value=[(5, 'REL_PEER', '同级', 2)])
    )
    relation_belongs = AsyncMock(side_effect=lambda db, project_id, version_id, relation_id: relation_id in {5, 6})
    monkeypatch.setattr(FeedbackProgressDao, 'relation_belongs_to_version', relation_belongs)
    monkeypatch.setattr(FeedbackProgressDao, 'list_assignments', AsyncMock(return_value=([], 0)))
    monkeypatch.setattr(FeedbackProgressDao, 'summarize_assignments', AsyncMock(return_value={'SUBMITTED': 101}))
    result = await FeedbackProgressService.get_progress(
        object(),
        9,
        ProgressQueryModel(
            evaluatorUserId=2,
            targetUserId=3,
            relationId=5,
            status='DRAFT',
            evaluatorKeyword=' 评 ',
            targetKeyword=' 目 ',
            pageNum=2,
            pageSize=10,
        ),
        true(),
        true(),
    )
    assert not result.data_scope_complete and result.scope_message == '当前数据范围仅覆盖部分被评价人'
    assert result.summary.total_count == 101
    filtered = FeedbackProgressDao.list_assignments.await_args_list[-1].args[-1]
    assert (filtered.evaluator_user_id, filtered.target_user_id, filtered.relation_id, filtered.status.value) == (
        2,
        3,
        5,
        'DRAFT',
    )
    assert (filtered.evaluator_keyword, filtered.target_keyword, filtered.page_num) == ('评', '目', 2)

    valid_but_not_visible = await FeedbackProgressService.get_progress(
        object(), 9, ProgressQueryModel(relationId=6), true(), true()
    )
    assert valid_but_not_visible.total == 0
    assert relation_belongs.await_args.args[2:] == (77, 6)

    with pytest.raises(HTTPException) as exc:
        await FeedbackProgressService.get_progress(object(), 9, ProgressQueryModel(relationId=999), true(), true())
    assert exc.value.status_code == 422 and exc.value.detail['code'] == 'VALIDATION_ERROR'


@pytest.mark.asyncio
async def test_p7_slice_4_precheck_status_missing_relations_impact_and_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException

    from module_feedback.dao.progress_dao import FeedbackProgressDao
    from module_feedback.service.progress_service import FeedbackProgressService

    project = SimpleNamespace(
        project_id=9, project_name='年度反馈', status='ACTIVE', lock_version=3, current_questionnaire_version_id=77
    )
    base = {
        'assignment_id': 1,
        'evaluator_user_id': 2,
        'evaluator_user_name': '评委',
        'evaluator_dept_name': None,
        'target_id': 30,
        'target_dept_id': 4,
        'target_dept_name': '产品',
        'relation_code': 'R',
        'relation_sort_order': 1,
        'saved_time': None,
        'submitted_time': None,
        'closed_time': None,
    }
    rows = [
        SimpleNamespace(
            **base, target_user_id=4, target_user_name='乙', relation_id=6, relation_name='下级', status='PENDING'
        ),
        SimpleNamespace(
            **base, target_user_id=3, target_user_name='甲', relation_id=5, relation_name='同级', status='DRAFT'
        ),
    ]
    monkeypatch.setattr(FeedbackProgressDao, 'get_project_scoped', AsyncMock(return_value=project))
    monkeypatch.setattr(FeedbackProgressDao, 'get_visible_target_ids', AsyncMock(return_value=({30}, 1)))
    monkeypatch.setattr(FeedbackProgressDao, 'lock_visible_assignments_for_share', AsyncMock())
    monkeypatch.setattr(FeedbackProgressDao, 'list_all_assignments', AsyncMock(return_value=rows))
    result = await FeedbackProgressService.get_precheck(object(), 9, true(), true())
    assert result.can_complete and result.summary.incomplete_count == 2
    assert [(item.target_name, item.relation_id) for item in result.missing_relations] == [('甲', 5), ('乙', 6)]
    assert '1项已暂存任务和1项未开始任务' in result.impact_messages[0]

    project.status = 'COMPLETED'
    assert not (await FeedbackProgressService.get_precheck(object(), 9, true(), true())).can_complete
    project.status = 'PREPARING'
    with pytest.raises(HTTPException) as exc:
        await FeedbackProgressService.get_precheck(object(), 9, true(), true())
    assert exc.value.status_code == 409 and exc.value.detail['code'] == 'PROJECT_NOT_ACTIVE'


@pytest.mark.asyncio
async def test_p7_zero_assignment_project_is_readable_but_cannot_be_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException

    from module_feedback.dao.progress_dao import FeedbackProgressDao
    from module_feedback.entity.vo.progress_vo import ProgressQueryModel, ProjectCompleteRequestModel
    from module_feedback.service.progress_service import FeedbackProgressService

    project = SimpleNamespace(
        project_id=9,
        project_name='零任务项目',
        status='ACTIVE',
        lock_version=3,
        current_questionnaire_version_id=77,
    )
    monkeypatch.setattr(FeedbackProgressDao, 'get_project_scoped', AsyncMock(return_value=project))
    monkeypatch.setattr(FeedbackProgressDao, 'get_visible_target_ids', AsyncMock(return_value=(set(), 0)))
    monkeypatch.setattr(FeedbackProgressDao, 'lock_visible_assignments_for_share', AsyncMock())
    monkeypatch.setattr(FeedbackProgressDao, 'list_relation_options', AsyncMock(return_value=[]))
    monkeypatch.setattr(FeedbackProgressDao, 'summarize_assignments', AsyncMock(return_value={}))
    monkeypatch.setattr(FeedbackProgressDao, 'list_assignments', AsyncMock(return_value=([], 0)))
    monkeypatch.setattr(FeedbackProgressDao, 'list_all_assignments', AsyncMock(return_value=[]))
    monkeypatch.setattr(FeedbackProgressDao, 'lock_assignments', AsyncMock(return_value=[]))

    progress = await FeedbackProgressService.get_progress(object(), 9, ProgressQueryModel(), true(), true())
    precheck = await FeedbackProgressService.get_precheck(object(), 9, true(), true())

    assert progress.summary.total_count == 0
    assert progress.summary.completion_rate == '0.00'
    assert progress.rows == [] and progress.total == 0
    assert precheck.summary.total_count == 0
    assert precheck.data_scope_complete
    assert not precheck.can_complete

    request = ProjectCompleteRequestModel.model_validate(
        {
            'projectLockVersion': 3,
            'completionReason': '不应完成',
            'expectedSummary': {
                'totalCount': 0,
                'submittedCount': 0,
                'draftCount': 0,
                'pendingCount': 0,
                'closedIncompleteCount': 0,
            },
        }
    )
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await FeedbackProgressService.complete_project(db, 9, request, 7, 'p7-user', true(), true())

    assert exc.value.status_code == 409
    assert exc.value.detail['code'] == 'PROJECT_HAS_NO_ASSIGNMENTS'
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_p7_reads_lock_project_then_visible_assignments_for_consistent_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from module_feedback.dao.progress_dao import FeedbackProgressDao
    from module_feedback.entity.vo.progress_vo import ProgressQueryModel
    from module_feedback.service.progress_service import FeedbackProgressService

    project = SimpleNamespace(
        project_id=9,
        project_name='一致快照项目',
        status='ACTIVE',
        lock_version=3,
        current_questionnaire_version_id=77,
    )
    calls: list[str] = []

    async def get_project(*args: object, **kwargs: object) -> object:
        calls.append(f'project:{kwargs}')
        return project

    async def get_targets(*args: object, **kwargs: object) -> tuple[set[int], int]:
        calls.append('targets')
        return {30}, 1

    locked_assignment_ids = (101, 102)

    async def lock_visible(*args: object, **kwargs: object) -> tuple[int, ...]:
        calls.append('assignments:share')
        return locked_assignment_ids

    async def options(*args: object, **kwargs: object) -> list[tuple[int, str, str, int]]:
        assert args[3] == locked_assignment_ids
        calls.append('options')
        return []

    async def summary(*args: object, **kwargs: object) -> dict[str, int]:
        assert args[3] == locked_assignment_ids
        calls.append('summary')
        return {}

    async def page(*args: object, **kwargs: object) -> tuple[list[object], int]:
        assert args[3] == locked_assignment_ids
        calls.append('page')
        return [], 0

    async def all_rows(*args: object, **kwargs: object) -> list[object]:
        assert args[3] == locked_assignment_ids
        calls.append('all')
        return []

    monkeypatch.setattr(FeedbackProgressDao, 'get_project_scoped', get_project)
    monkeypatch.setattr(FeedbackProgressDao, 'get_visible_target_ids', get_targets)
    monkeypatch.setattr(FeedbackProgressDao, 'lock_visible_assignments_for_share', lock_visible)
    monkeypatch.setattr(FeedbackProgressDao, 'list_relation_options', options)
    monkeypatch.setattr(FeedbackProgressDao, 'summarize_assignments', summary)
    monkeypatch.setattr(FeedbackProgressDao, 'list_assignments', page)
    monkeypatch.setattr(FeedbackProgressDao, 'list_all_assignments', all_rows)

    await FeedbackProgressService.get_progress(object(), 9, ProgressQueryModel(), true(), true())
    assert calls == ["project:{'for_share': True}", 'targets', 'assignments:share', 'options', 'summary', 'page']

    calls.clear()
    await FeedbackProgressService.get_precheck(object(), 9, true(), true())
    assert calls == ["project:{'for_share': True}", 'targets', 'assignments:share', 'all']


@pytest.mark.asyncio
async def test_p7_complete_builds_response_model_before_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    import module_feedback.service.progress_service as progress_service_module
    from module_feedback.dao.progress_dao import FeedbackProgressDao
    from module_feedback.entity.vo.progress_vo import ProjectCompleteRequestModel
    from module_feedback.service.progress_service import FeedbackProgressService

    project = SimpleNamespace(
        project_id=9,
        project_name='事务响应项目',
        status='ACTIVE',
        lock_version=3,
        current_questionnaire_version_id=77,
        completed_by=None,
        completed_time=None,
        completion_reason=None,
        update_by='old',
        update_time=datetime(2026, 9, 2),
    )
    task = SimpleNamespace(
        status='PENDING',
        closed_time=None,
        update_time=datetime(2026, 9, 2),
        lock_version=0,
    )
    request = ProjectCompleteRequestModel.model_validate(
        {
            'projectLockVersion': 3,
            'completionReason': '截止完成',
            'expectedSummary': {
                'totalCount': 1,
                'submittedCount': 0,
                'draftCount': 0,
                'pendingCount': 1,
                'closedIncompleteCount': 0,
            },
        }
    )
    monkeypatch.setattr(FeedbackProgressDao, 'get_project_scoped', AsyncMock(return_value=project))
    monkeypatch.setattr(FeedbackProgressDao, 'get_visible_target_ids', AsyncMock(return_value=({30}, 1)))
    monkeypatch.setattr(FeedbackProgressDao, 'lock_assignments', AsyncMock(return_value=[task]))
    monkeypatch.setattr(FeedbackProgressDao, 'add_completion_audit', AsyncMock())
    built = False
    expected_result = object()

    def build_result(**kwargs: object) -> object:
        nonlocal built
        built = True
        return expected_result

    async def commit() -> None:
        assert built, '响应模型必须在commit前构造'

    monkeypatch.setattr(progress_service_module, 'ProjectCompleteResultModel', build_result)
    db = AsyncMock()
    db.commit.side_effect = commit

    result = await FeedbackProgressService.complete_project(db, 9, request, 7, 'p7-user', true(), true())

    assert result is expected_result
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_p7_complete_writes_one_success_audit_in_the_completion_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from module_feedback.dao.progress_dao import FeedbackProgressDao
    from module_feedback.entity.vo.progress_vo import ProjectCompleteRequestModel
    from module_feedback.service.progress_service import FeedbackProgressService

    project = SimpleNamespace(
        project_id=9,
        project_name='审计项目',
        status='ACTIVE',
        lock_version=3,
        current_questionnaire_version_id=77,
        completed_by=None,
        completed_time=None,
        completion_reason=None,
        update_by='old',
        update_time=datetime(2026, 9, 2),
    )
    tasks = [
        SimpleNamespace(status='PENDING', closed_time=None, update_time=None, lock_version=0),
        SimpleNamespace(status='SUBMITTED', closed_time=None, update_time=None, lock_version=1),
    ]
    request = ProjectCompleteRequestModel.model_validate(
        {
            'projectLockVersion': 3,
            'completionReason': '审计截止完成',
            'expectedSummary': {
                'totalCount': 2,
                'submittedCount': 1,
                'draftCount': 0,
                'pendingCount': 1,
                'closedIncompleteCount': 0,
            },
        }
    )
    monkeypatch.setattr(FeedbackProgressDao, 'get_project_scoped', AsyncMock(return_value=project))
    monkeypatch.setattr(FeedbackProgressDao, 'get_visible_target_ids', AsyncMock(return_value=({30}, 1)))
    monkeypatch.setattr(FeedbackProgressDao, 'lock_assignments', AsyncMock(return_value=tasks))
    add_audit = AsyncMock()
    monkeypatch.setattr(FeedbackProgressDao, 'add_completion_audit', add_audit)
    db = AsyncMock()

    first = await FeedbackProgressService.complete_project(
        db,
        9,
        request,
        7,
        'p7-user',
        true(),
        true(),
        request_id='request-9',
        trace_id='trace-9',
    )
    audit = add_audit.await_args.args[1]
    assert audit.project_id == 9 and audit.version_id == 77
    assert audit.operator_user_id == 7 and audit.operator_name == 'p7-user'
    assert audit.request_id == 'request-9' and audit.trace_id == 'trace-9'
    assert (
        audit.before_total_count,
        audit.before_submitted_count,
        audit.before_draft_count,
        audit.before_pending_count,
        audit.before_closed_incomplete_count,
        audit.closed_assignment_count,
    ) == (2, 1, 0, 1, 0, 1)
    assert audit.completion_reason == '审计截止完成'
    assert audit.completed_time == first.completed_time
    add_audit.assert_awaited_once()
    db.commit.assert_awaited_once()

    repeated = await FeedbackProgressService.complete_project(
        db,
        9,
        request,
        7,
        'p7-user',
        true(),
        true(),
        request_id='request-repeat',
        trace_id='trace-repeat',
    )
    assert repeated.already_completed
    add_audit.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('failure_point', 'expected_stage'),
    [('assignment_lock', 'assignment_lock'), ('commit', 'commit')],
)
async def test_p7_completion_unknown_failures_keep_stable_failure_stage(
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
    expected_stage: str,
) -> None:
    from module_feedback.dao.progress_dao import FeedbackProgressDao
    from module_feedback.entity.vo.progress_vo import ProjectCompleteRequestModel
    from module_feedback.service.progress_service import (
        FeedbackProgressService,
        ProjectCompletionExecutionError,
    )

    project = SimpleNamespace(
        project_id=9,
        project_name='失败阶段项目',
        status='ACTIVE',
        lock_version=3,
        current_questionnaire_version_id=77,
        completed_by=None,
        completed_time=None,
        completion_reason=None,
        update_by='old',
        update_time=datetime(2026, 9, 2),
    )
    task = SimpleNamespace(status='PENDING', closed_time=None, update_time=None, lock_version=0)
    request = ProjectCompleteRequestModel.model_validate(
        {
            'projectLockVersion': 3,
            'completionReason': '失败测试',
            'expectedSummary': {
                'totalCount': 1,
                'submittedCount': 0,
                'draftCount': 0,
                'pendingCount': 1,
                'closedIncompleteCount': 0,
            },
        }
    )
    monkeypatch.setattr(FeedbackProgressDao, 'get_project_scoped', AsyncMock(return_value=project))
    monkeypatch.setattr(FeedbackProgressDao, 'get_visible_target_ids', AsyncMock(return_value=({30}, 1)))
    lock = AsyncMock(return_value=[task])
    if failure_point == 'assignment_lock':
        lock.side_effect = RuntimeError('锁任务失败')
    monkeypatch.setattr(FeedbackProgressDao, 'lock_assignments', lock)
    monkeypatch.setattr(FeedbackProgressDao, 'add_completion_audit', AsyncMock())
    db = AsyncMock()
    if failure_point == 'commit':
        db.commit.side_effect = RuntimeError('提交失败')

    with pytest.raises(ProjectCompletionExecutionError) as exc:
        await FeedbackProgressService.complete_project(db, 9, request, 7, 'p7-user', true(), true())

    assert exc.value.problem_code == 'PROJECT_COMPLETION_FAILED'
    assert exc.value.stage == expected_stage
    db.rollback.assert_awaited_once()
